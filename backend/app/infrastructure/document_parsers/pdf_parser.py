import re
from typing import Dict, List

import fitz  # PyMuPDF
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class PdfDocumentParser:
    """Deterministic, page-preserving text extraction for normal PDFs."""

    EXTRACTION_METHOD = "pymupdf_text"

    @staticmethod
    def parse_pages(content: bytes) -> List[Dict]:
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            logger.error("Failed to open PDF stream", error=str(exc))
            raise ValueError(f"Invalid PDF content: {exc}") from exc

        pages: List[Dict] = []
        try:
            for page_index in range(len(document)):
                page = document[page_index]
                raw_text = page.get_text("text")
                extracted_text = raw_text.strip()
                warnings: List[str] = []
                page_passages: List[Dict] = []

                # A short or empty page is preserved as a partial extraction.
                # OCR is deliberately not invoked here; that belongs to STEP 08.
                if len(extracted_text) < 10:
                    warnings.append("Page contains fewer than 10 extracted characters.")
                    page_passages.append(
                        {
                            "content": extracted_text,
                            "page_number": page_index + 1,
                            "extraction_method": PdfDocumentParser.EXTRACTION_METHOD,
                            "extraction_status": "partial",
                            "extraction_uncertainty": True,
                            "language": None,
                            "section_heading": None,
                        }
                    )
                else:
                    blocks = list(page.get_text("blocks"))
                    blocks.sort(key=lambda block: (block[1], block[0]))
                    for block in blocks:
                        if block[6] != 0:
                            continue
                        block_text = block[4].strip()
                        if block_text:
                            page_passages.append(
                                {
                                    "content": block_text,
                                    "page_number": page_index + 1,
                                    "extraction_method": PdfDocumentParser.EXTRACTION_METHOD,
                                    "extraction_status": "success",
                                    "extraction_uncertainty": False,
                                    "language": None,
                                    "section_heading": None,
                                }
                            )
                    if not page_passages:
                        page_passages.append(
                            {
                                "content": extracted_text,
                                "page_number": page_index + 1,
                                "extraction_method": PdfDocumentParser.EXTRACTION_METHOD,
                                "extraction_status": "success",
                                "extraction_uncertainty": False,
                                "language": None,
                                "section_heading": None,
                            }
                        )

                pages.append(
                    {
                        "page_number": page_index + 1,
                        "page_order": page_index,
                        "extracted_text": extracted_text,
                        "extraction_method": PdfDocumentParser.EXTRACTION_METHOD,
                        "extraction_status": "success" if not warnings else "partial",
                        "extraction_warnings": warnings,
                        "passages": page_passages,
                    }
                )
        finally:
            document.close()

        if not pages:
            raise ValueError("PDF contains no pages.")
        return pages

    @staticmethod
    def parse_pdf(content: bytes) -> List[Dict]:
        """Compatibility projection retaining the previous flat parser API."""
        return [passage for page in PdfDocumentParser.parse_pages(content) for passage in page["passages"]]


class TextDocumentParser:
    """Deterministic paragraph extraction for plain text and Markdown."""

    @staticmethod
    def _decode(content: bytes) -> tuple[str, List[str]]:
        text = content.decode("utf-8", errors="replace")
        warnings = ["Invalid UTF-8 bytes were replaced."] if "\ufffd" in text else []
        return text, warnings

    @staticmethod
    def decode_warnings(content: bytes) -> List[str]:
        """Return decoding warnings without changing the parser output."""
        return TextDocumentParser._decode(content)[1]

    @staticmethod
    def segment_text(
        text: str,
        extraction_method: str,
        page_number: int = 1,
        extraction_status: str = "success",
        extraction_uncertainty: bool = False,
        section_heading: str | None = None,
        language: str | None = None,
    ) -> List[Dict]:
        """Split text deterministically while retaining its page and method."""
        passages = []
        for chunk in re.split(r"\n\s*\n", text):
            cleaned = chunk.strip()
            if cleaned:
                passages.append(
                    {
                        "content": cleaned,
                        "page_number": page_number,
                        "extraction_method": extraction_method,
                        "extraction_status": extraction_status,
                        "extraction_uncertainty": extraction_uncertainty,
                        "language": language,
                        "section_heading": section_heading,
                    }
                )
        return passages


    @staticmethod
    def parse_text(content: bytes) -> List[Dict]:
        text, _ = TextDocumentParser._decode(content)
        return TextDocumentParser.segment_text(text, "utf8_text")

    @staticmethod
    def parse_ocr_text(
        text: str,
        page_number: int,
        extraction_status: str = "success",
        extraction_uncertainty: bool = False,
        language: str | None = None,
    ) -> List[Dict]:
        return TextDocumentParser.segment_text(
            text,
            "tesseract_ocr",
            page_number=page_number,
            extraction_status=extraction_status,
            extraction_uncertainty=extraction_uncertainty,
            section_heading=None,
            language=language,
        )

    @staticmethod
    def parse_markdown(content: bytes) -> List[Dict]:
        text, _ = TextDocumentParser._decode(content)
        passages: List[Dict] = []
        current_heading = None
        buffer: List[str] = []

        def flush() -> None:
            if not buffer:
                return
            cleaned = "\n".join(buffer).strip()
            buffer.clear()
            if cleaned:
                passages.append(
                    {
                        "content": cleaned,
                        "page_number": 1,
                        "extraction_method": "markdown_text",
                        "extraction_status": "success",
                        "extraction_uncertainty": False,
                        "language": None,
                        "section_heading": current_heading,
                    }
                )

        for line in text.splitlines():
            heading_match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if heading_match:
                flush()
                current_heading = heading_match.group(2).strip()
                continue
            if not line.strip() and buffer:
                flush()
                continue
            buffer.append(line)
        flush()

        if not passages and current_heading:
            passages.append(
                {
                    "content": current_heading,
                    "page_number": 1,
                    "extraction_method": "markdown_text",
                    "extraction_status": "success",
                    "extraction_uncertainty": False,
                    "language": None,
                    "section_heading": current_heading,
                }
            )
        return passages


class HtmlDocumentParser:
    """Deterministic, non-executing extraction for acquired HTML."""

    REMOVED_ELEMENTS = ("script", "style", "nav", "footer", "header", "form")

    @classmethod
    def parse_html(cls, content: bytes) -> List[Dict]:
        text = content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(text, "html.parser")
        for element in soup(cls.REMOVED_ELEMENTS):
            element.decompose()
        paragraphs = [paragraph.get_text(" ", strip=True) for paragraph in soup.find_all("p")]
        selected = [paragraph for paragraph in paragraphs if paragraph]
        if not selected:
            body = soup.body or soup
            fallback = body.get_text("\n", strip=True)
            selected = [fallback] if fallback else []
        return [
            {
                "content": paragraph,
                "page_number": 1,
                "extraction_method": "html_text",
                "extraction_status": "success",
                "extraction_uncertainty": False,
                "language": soup.html.get("lang") if soup.html else None,
                "section_heading": None,
            }
            for paragraph in selected
            if paragraph.strip()
        ]
