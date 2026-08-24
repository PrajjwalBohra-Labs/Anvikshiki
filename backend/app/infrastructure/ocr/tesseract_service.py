import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import structlog
from typing import Dict
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)

class TesseractOcrService:
    def __init__(self):
        # We can configure tesseract cmd path here if needed for Windows
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        self.enabled = settings.ENABLE_OCR

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def process_pdf_page(self, pdf_bytes: bytes, page_num: int, language: str = "eng") -> Dict:
        """
        Renders a specific PDF page to an image and extracts text + confidence via Tesseract.
        page_num is 1-indexed.
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            # 0-indexed for PyMuPDF
            page = doc[page_num - 1]
            
            # Render page to high-res image for better OCR
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes()))
            
            # Run OCR with data output
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
            
            text_parts = []
            conf_sum = 0
            conf_count = 0
            
            for i in range(len(data['text'])):
                conf = int(data['conf'][i])
                if conf > -1:  # -1 means no text/bounding box only
                    text = data['text'][i].strip()
                    if text:
                        text_parts.append(text)
                        conf_sum += conf
                        conf_count += 1
                        
            final_text = " ".join(text_parts).strip()
            # Convert confidence to a 0.0 - 1.0 scale
            avg_conf = (conf_sum / conf_count / 100.0) if conf_count > 0 else 0.0
            
            doc.close()
            
            return {
                "content": final_text,
                "confidence": avg_conf,
                "success": True
            }
            
        except Exception as e:
            logger.error("OCR failed for page", page_num=page_num, error=str(e))
            return {
                "content": "[OCR FAILED]",
                "confidence": 0.0,
                "success": False
            }