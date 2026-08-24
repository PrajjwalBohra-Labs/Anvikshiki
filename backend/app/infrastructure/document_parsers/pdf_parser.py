import fitz  # PyMuPDF
from typing import List, Dict, Any
from pathlib import Path

class ExtractedPage:
    def __init__(self, page_number: int, text: str, has_images: bool, is_uncertain: bool):
        self.page_number = page_number
        self.text = text
        self.has_images = has_images
        self.is_uncertain = is_uncertain

class PDFParser:
    @staticmethod
    def extract_pages(pdf_path: str) -> List[ExtractedPage]:
        doc = fitz.open(pdf_path)
        extracted = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text").strip()
            images = page.get_images()
            
            # If text length is minimal despite images existing, mark extraction uncertainty
            is_uncertain = len(text) < 50 and len(images) > 0

            extracted.append(
                ExtractedPage(
                    page_number=page_idx + 1,
                    text=text,
                    has_images=len(images) > 0,
                    is_uncertain=is_uncertain
                )
            )
            
        doc.close()
        return extracted