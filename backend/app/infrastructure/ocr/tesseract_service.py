"""Local, page-level OCR using the configured Tesseract executable."""

import io
import re
from datetime import datetime, timezone
from typing import Dict, Optional

import fitz  # PyMuPDF
import pytesseract
import structlog
from PIL import Image

from backend.app.core.config import settings


logger = structlog.get_logger(__name__)


class TesseractOcrService:
    """Render and OCR only the PDF pages selected by the ingestion service."""

    EXTRACTION_METHOD = "tesseract_ocr"

    def __init__(self):
        self.enabled = settings.ENABLE_OCR
        self.languages = settings.OCR_LANGUAGES.strip() or "eng"
        self.dpi = settings.OCR_DPI
        self.timeout_seconds = settings.OCR_TIMEOUT_SECONDS
        if settings.OCR_TESSERACT_CMD:
            # The executable is deployment configuration, never client input.
            pytesseract.pytesseract.tesseract_cmd = settings.OCR_TESSERACT_CMD

    @staticmethod
    def _language_parts(language: str) -> list[str]:
        return [part for part in re.split(r"[+,\s]+", language.strip()) if part]

    def availability_error(self, language: Optional[str] = None) -> Optional[str]:
        """Return a diagnostic string, or None when Tesseract can run."""
        if not self.enabled:
            return "OCR is disabled by configuration."
        requested_language = language or self.languages
        try:
            pytesseract.get_tesseract_version()
        except FileNotFoundError:
            return "Tesseract executable is not available."
        except Exception as exc:
            return f"Tesseract executable is unavailable: {exc}"

        try:
            installed_languages = set(pytesseract.get_languages(config=""))
        except Exception as exc:
            return f"Tesseract languages could not be inspected: {exc}"
        missing_languages = [
            part for part in self._language_parts(requested_language) if part not in installed_languages
        ]
        if missing_languages:
            return "Unsupported OCR language(s): " + ", ".join(missing_languages)
        return None

    def is_available(self, language: Optional[str] = None) -> bool:
        return self.availability_error(language) is None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _result(
        self,
        page_num: int,
        language: str,
        status: str,
        content: str = "",
        confidence: float = 0.0,
        error: Optional[str] = None,
    ) -> Dict:
        return {
            "content": content,
            "confidence": confidence,
            "success": status in {"success", "partial"},
            "status": status,
            "extraction_method": self.EXTRACTION_METHOD,
            "page_number": page_num,
            "language": language,
            "dpi": self.dpi,
            "text_length": len(content),
            "processed_at": self._timestamp(),
            "error": error,
        }

    def process_pdf_page(
        self, pdf_bytes: bytes, page_num: int, language: Optional[str] = None
    ) -> Dict:
        """Render one 1-indexed page and return structured OCR outcome metadata."""
        requested_language = language or self.languages
        availability_error = self.availability_error(requested_language)
        if availability_error:
            return self._result(
                page_num, requested_language, "unavailable", error=availability_error
            )
        if page_num < 1:
            return self._result(
                page_num, requested_language, "invalid_page", error="PDF page numbers are 1-indexed."
            )

        document = None
        image = None
        try:
            try:
                document = fitz.open(stream=pdf_bytes, filetype="pdf")
                if page_num > len(document):
                    return self._result(
                        page_num,
                        requested_language,
                        "invalid_page",
                        error=f"PDF has only {len(document)} page(s).",
                    )
                page = document[page_num - 1]
                pixmap = page.get_pixmap(dpi=self.dpi, alpha=False)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            except Exception as exc:
                return self._result(
                    page_num, requested_language, "render_failed", error=f"PDF page rendering failed: {exc}"
                )

            try:
                data = pytesseract.image_to_data(
                    image,
                    lang="+".join(self._language_parts(requested_language)),
                    output_type=pytesseract.Output.DICT,
                    timeout=self.timeout_seconds,
                )
            except FileNotFoundError:
                return self._result(
                    page_num,
                    requested_language,
                    "unavailable",
                    error="Tesseract executable is not available.",
                )
            except RuntimeError as exc:
                message = str(exc)
                status = "timeout" if "timeout" in message.lower() else "failed"
                return self._result(
                    page_num, requested_language, status, error=f"Tesseract OCR failed: {message}"
                )
            except Exception as exc:
                return self._result(
                    page_num, requested_language, "failed", error=f"Tesseract OCR failed: {exc}"
                )

            text_parts = []
            confidence_values = []
            for raw_text, raw_confidence in zip(data.get("text", []), data.get("conf", [])):
                text = raw_text.strip()
                try:
                    confidence = float(raw_confidence)
                except (TypeError, ValueError):
                    continue
                if text and confidence >= 0:
                    text_parts.append(text)
                    confidence_values.append(confidence)

            final_text = " ".join(text_parts).strip()
            if not final_text:
                return self._result(
                    page_num,
                    requested_language,
                    "empty",
                    error="Tesseract returned no text for the rendered page.",
                )
            average_confidence = sum(confidence_values) / len(confidence_values) / 100.0
            status = "partial" if average_confidence < 0.60 else "success"
            return self._result(
                page_num,
                requested_language,
                status,
                content=final_text,
                confidence=average_confidence,
            )
        except Exception as exc:
            logger.error("OCR failed for page", page_num=page_num, error=str(exc))
            return self._result(
                page_num, requested_language, "failed", error=f"Unexpected OCR failure: {exc}"
            )
        finally:
            if image is not None:
                image.close()
            if document is not None:
                document.close()
