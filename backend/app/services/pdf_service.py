import logging
from typing import Tuple, List, Dict, Any
import pymupdf as fitz  # PyMuPDF

logger = logging.getLogger(__name__)

class PDFService:
    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extracts text from PDF bytes page by page.
        Returns (full_combined_text, list_of_pages_dict).
        """
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = []
            full_text_list = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                raw_text = page.get_text("text")
                page_text = str(raw_text) if raw_text is not None else ""
                pages.append({
                    "page_number": page_num + 1,
                    "text": page_text
                })
                if page_text.strip():
                    full_text_list.append(f"--- Page {page_num + 1} ---\n{page_text}")

            full_text = "\n\n".join(full_text_list)
            return full_text, pages
        except Exception as e:
            logger.error(f"Error reading PDF bytes: {e}")
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

pdf_service = PDFService()
