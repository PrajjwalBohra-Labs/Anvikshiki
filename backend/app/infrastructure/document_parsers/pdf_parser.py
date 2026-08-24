import fitz  # PyMuPDF
from typing import List, Dict
import structlog

logger = structlog.get_logger(__name__)

class PdfDocumentParser:
    @staticmethod
    def parse_pdf(content: bytes) -> List[Dict]:
        """
        Parses a PDF from bytes.
        Extracts text blocks preserving reading order and page numbers.
        Flags any page with minimal text (scanned, diagrams, or blank) for OCR.
        """
        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception as e:
            logger.error("Failed to open PDF stream", error=str(e))
            raise ValueError(f"Invalid PDF content: {str(e)}")

        passages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            raw_text = page.get_text("text").strip()
            
            # Heuristic: If a page yields fewer than 10 characters, it is 
            # likely a scanned image, diagram, or blank page.
            is_uncertain = len(raw_text) < 10
            
            if is_uncertain:
                passages.append({
                    "content": raw_text if raw_text else "[UNREADABLE OR BLANK PAGE - PENDING OCR]",
                    "page_number": page_num + 1,
                    "extraction_uncertainty": True,
                    "language": "en"
                })
                continue

            # Extract text blocks (x0, y0, x1, y1, "text", block_no, block_type)
            blocks = page.get_text("blocks")
            
            # Sort by vertical (y0) then horizontal (x0) to preserve reading order
            blocks.sort(key=lambda b: (b[1], b[0]))
            
            for block in blocks:
                if block[6] == 0:  # 0 indicates text block
                    block_text = block[4].strip()
                    if block_text:
                        passages.append({
                            "content": block_text,
                            "page_number": page_num + 1,
                            "extraction_uncertainty": False,
                            "language": "en"
                        })
                        
        doc.close()
        return passages