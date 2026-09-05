import mimetypes
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from backend.app.application.use_cases.embedding_indexing import EmbeddingIndexService
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    PageModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.document_parsers.pdf_parser import (
    HtmlDocumentParser,
    PdfDocumentParser,
    TextDocumentParser,
)
from backend.app.infrastructure.ocr.tesseract_service import TesseractOcrService
from backend.app.infrastructure.storage.local_storage import LocalStorageService

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/html",
    "application/xhtml+xml",
    "text/markdown",
    "text/plain",
}


class DocumentIngestionService:
    def __init__(self, session: AsyncSession, storage_service: LocalStorageService):
        self.session = session
        self.storage = storage_service
        self.ocr_service = TesseractOcrService()

    @staticmethod
    def _resolve_mime_type(filename: str, mime_type: str | None) -> str:
        supplied = (mime_type or "").split(";", 1)[0].strip().lower()
        guessed = (mimetypes.guess_type(filename)[0] or "").lower()
        resolved = guessed if supplied in {"", "application/octet-stream"} else supplied
        if resolved not in SUPPORTED_MIME_TYPES:
            raise AnvikshikiDomainError(
                f"Unsupported document MIME type: {resolved or 'unknown'}.", status_code=415
            )
        return resolved

    @staticmethod
    def _extraction_metadata(
        mime_type: str,
        parsed_data: list[dict],
        page_data: list[dict] | None = None,
        additional_warnings: list[str] | None = None,
    ) -> tuple[str, str, list[str]]:
        if mime_type == "application/pdf":
            method = PdfDocumentParser.EXTRACTION_METHOD
        elif mime_type in {"text/html", "application/xhtml+xml"}:
            method = "html_text"
        elif mime_type == "text/markdown":
            method = "markdown_text"
        else:
            method = "utf8_text"
        warnings = list(additional_warnings or [])
        pages = page_data or []
        methods = {item.get("extraction_method") for item in pages}
        has_ocr = any("tesseract_ocr" in method for method in methods if method)
        has_native = any("pymupdf_text" in method for method in methods if method)
        if has_ocr and has_native:
            method = "pymupdf_text+tesseract_ocr"
        elif has_ocr:
            method = "tesseract_ocr"
        for page in pages:
            warnings.extend(page.get("extraction_warnings") or [])
        partial_extraction = any(
            item.get("extraction_status") == "partial" for item in parsed_data + pages
        )
        if partial_extraction or additional_warnings:
            warnings.append("One or more extracted regions are partial or uncertain.")
        if any(page.get("ocr_status") not in {None, "success", "partial"} for page in pages):
            warnings.append("One or more OCR page attempts did not produce usable text.")
        unique_warnings = list(dict.fromkeys(warnings))
        status = "partial" if partial_extraction or additional_warnings else "success"
        return method, status, unique_warnings

    def _apply_ocr_to_pages(self, page_data: list[dict], pdf_content: bytes) -> None:
        """Apply OCR only to uncertain pages and retain native page metadata."""
        for page in page_data:
            if not page.get("passages") or not any(
                passage.get("extraction_uncertainty") for passage in page["passages"]
            ):
                continue

            page["native_extracted_text"] = page.get("extracted_text", "")
            if not self.ocr_service.is_available():
                error = self.ocr_service.availability_error() or "OCR is unavailable."
                page["ocr_status"] = "disabled" if not self.ocr_service.enabled else "unavailable"
                page["ocr_language"] = self.ocr_service.languages
                page["ocr_dpi"] = self.ocr_service.dpi
                page["ocr_text_length"] = 0
                page["ocr_text"] = None
                page["ocr_confidence"] = 0.0
                page["ocr_processed_at"] = datetime.now(timezone.utc)
                page["ocr_error"] = error
                page.setdefault("extraction_warnings", []).append(error)
                page["extraction_status"] = "partial"
                continue

            page_number = page["page_number"]
            result = self.ocr_service.process_pdf_page(
                pdf_content, page_number, language=self.ocr_service.languages
            )
            content = (result.get("content") or "").strip()
            confidence = float(result.get("confidence") or 0.0)
            status = result.get("status") or (
                "partial" if confidence < self.ocr_service.min_confidence else "success"
            )
            page["ocr_status"] = status
            page["ocr_language"] = result.get("language", self.ocr_service.languages)
            page["ocr_dpi"] = result.get("dpi", self.ocr_service.dpi)
            page["ocr_text_length"] = result.get("text_length", len(content))
            page["ocr_text"] = content or None
            page["ocr_confidence"] = confidence
            processed_at = result.get("processed_at")
            page["ocr_processed_at"] = (
                datetime.fromisoformat(processed_at)
                if isinstance(processed_at, str)
                else datetime.now(timezone.utc)
            )
            page["ocr_error"] = result.get("error")

            if result.get("success") and content:
                uncertainty = status == "partial" or confidence < self.ocr_service.min_confidence
                if uncertainty:
                    # Keep low-confidence OCR available for explicitly marked
                    # review/retrieval, but never promote it to the page's
                    # authoritative extracted_text field.
                    page["extracted_text"] = page["native_extracted_text"]
                    page["extraction_method"] = "pymupdf_text+tesseract_ocr"
                    page.setdefault("extraction_warnings", []).append(
                        "OCR confidence is below the acceptance threshold; OCR text is not authoritative."
                    )
                else:
                    page["extracted_text"] = content
                    page["extraction_method"] = TesseractOcrService.EXTRACTION_METHOD
                page["extraction_status"] = "partial" if uncertainty else "success"
                page["extraction_warnings"] = list(page.get("extraction_warnings") or [])
                page["passages"] = TextDocumentParser.parse_ocr_text(
                    content,
                    page_number,
                    extraction_status=page["extraction_status"],
                    extraction_uncertainty=uncertainty,
                    language=result.get("language", self.ocr_service.languages),
                )
                for passage in page["passages"]:
                    passage["ocr_confidence"] = confidence
                continue

            error = result.get("error") or "OCR did not produce usable text."
            page.setdefault("extraction_warnings", []).append(error)
            page["extraction_status"] = "partial"

    async def ingest_file(
        self,
        source_id: str,
        filename: str,
        content: bytes,
        mime_type: str | None = None,
        owner_id: str | None = None,
    ) -> tuple[DocumentModel, list[PassageModel]]:
        source_stmt = select(SourceModel).where(SourceModel.id == source_id)
        if owner_id:
            source_stmt = source_stmt.where(
                or_(SourceModel.user_id == owner_id, SourceModel.user_id.is_(None))
            )
        source_result = await self.session.execute(source_stmt)
        source = source_result.scalars().first()
        if not source:
            raise AnvikshikiDomainError(f"Source {source_id} not found.", status_code=404)

        if not content or not content.strip():
            raise AnvikshikiDomainError("Document content cannot be empty.", status_code=422)
        resolved_mime_type = self._resolve_mime_type(filename, mime_type)

        metadata = await self.storage.store_original(content, filename, mime_type=resolved_mime_type)
        existing_result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.checksum_sha256 == metadata.checksum_sha256)
        )
        if existing_result.scalars().first():
            raise AnvikshikiDomainError(
                f"Document with checksum {metadata.checksum_sha256} already ingested.", status_code=409
            )

        try:
            page_data: list[dict] = []
            if resolved_mime_type == "application/pdf":
                page_data = PdfDocumentParser.parse_pages(content)
                self._apply_ocr_to_pages(page_data, content)
                parsed_data = [passage for page in page_data for passage in page["passages"]]
            elif resolved_mime_type in {"text/html", "application/xhtml+xml"}:
                parsed_data = HtmlDocumentParser.parse_html(content)
            elif resolved_mime_type == "text/markdown":
                parsed_data = TextDocumentParser.parse_markdown(content)
            else:
                parsed_data = TextDocumentParser.parse_text(content)
        except ValueError as exc:
            raise AnvikshikiDomainError("Document extraction failed.", status_code=422) from exc

        if not parsed_data:
            raise AnvikshikiDomainError("Document extraction produced no passages.", status_code=422)

        decoding_warnings = (
            TextDocumentParser.decode_warnings(content)
            if resolved_mime_type in {"text/markdown", "text/plain"}
            else []
        )
        extraction_method, extraction_status, extraction_warnings = self._extraction_metadata(
            resolved_mime_type, parsed_data, page_data, decoding_warnings
        )
        try:
            new_document = DocumentModel(
                source_id=source_id,
                checksum_sha256=metadata.checksum_sha256,
                mime_type=resolved_mime_type,
                total_pages=len(page_data) if page_data else 1,
                original_filename=metadata.original_filename,
                storage_path=metadata.storage_path,
                size_bytes=metadata.size_bytes,
                language=source.original_language,
                extraction_method=extraction_method,
                extraction_status=extraction_status,
                extraction_warnings=extraction_warnings or None,
            )
            self.session.add(new_document)
            await self.session.flush()

            version = DocumentVersionModel(
                document_id=new_document.id,
                version_number=1,
                checksum_sha256=metadata.checksum_sha256,
                original_filename=metadata.original_filename,
                mime_type=resolved_mime_type,
                storage_path=metadata.storage_path,
                size_bytes=metadata.size_bytes,
                extraction_method=extraction_method,
                extraction_status=extraction_status,
                extraction_warnings=extraction_warnings or None,
            )
            self.session.add(version)
            await self.session.flush()

            page_models: dict[int, PageModel] = {}
            for page in page_data:
                page_model = PageModel(
                    document_version_id=version.id,
                    page_number=page["page_number"],
                    page_order=page["page_order"],
                    extracted_text=page["extracted_text"],
                    native_extracted_text=page.get("native_extracted_text", page["extracted_text"]),
                    extraction_method=page["extraction_method"],
                    extraction_status=page["extraction_status"],
                    extraction_warnings=page["extraction_warnings"] or None,
                    ocr_status=page.get("ocr_status"),
                    ocr_language=page.get("ocr_language"),
                    ocr_dpi=page.get("ocr_dpi"),
                    ocr_text_length=page.get("ocr_text_length"),
                    ocr_text=page.get("ocr_text"),
                    ocr_confidence=page.get("ocr_confidence"),
                    ocr_processed_at=page.get("ocr_processed_at"),
                    ocr_error=page.get("ocr_error"),
                )
                self.session.add(page_model)
                page_models[page["page_number"]] = page_model
            if page_models:
                await self.session.flush()

            passage_models = []
            for passage_order, passage_data in enumerate(parsed_data):
                page_model = page_models.get(passage_data.get("page_number"))
                passage = PassageModel(
                    document_id=new_document.id,
                    document_version_id=version.id,
                    page_id=page_model.id if page_model else None,
                    page_number=passage_data.get("page_number"),
                    passage_order=passage_order,
                    content=passage_data["content"],
                    extraction_method=passage_data.get("extraction_method", extraction_method),
                    section_heading=passage_data.get("section_heading"),
                    ocr_confidence=passage_data.get(
                        "ocr_confidence", 0.0 if passage_data.get("extraction_uncertainty") else 1.0
                    ),
                    extraction_uncertainty=passage_data.get("extraction_uncertainty", False),
                    language=passage_data.get("language") or source.original_language or "unknown",
                    embedding_status="PENDING",
                )
                self.session.add(passage)
                passage_models.append(passage)

            await ProvenanceService(self.session).record_document_ancestry(
                new_document,
                version,
                page_models.values(),
                passage_models,
            )
            await self.session.commit()
            await EmbeddingIndexService(self.session).index_passages(
                passage_ids=[passage.id for passage in passage_models]
            )
            await self.session.refresh(new_document)
            for passage in passage_models:
                await self.session.refresh(passage)
            return new_document, passage_models
        except Exception:
            await self.session.rollback()
            raise
