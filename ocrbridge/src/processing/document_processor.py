import io
from typing import List, Union
from PIL import Image
import fitz  # PyMuPDF
from src.interfaces import IDocumentProcessor
from config import get_logger


logger = get_logger(__name__)


class DocumentProcessor(IDocumentProcessor):
    """PDF/Image preprocessing for VLM consumption"""
    
    def __init__(self, dpi: int = 200):
        self.dpi = dpi
    
    def process(self, document: Union[bytes, io.BytesIO]) -> List[bytes]:
        """Convert document to list of page images"""
        logger.info(f"📝 Processing document, type: {'PDF' if document[:4] == b'%PDF' else 'Image'}")
        
        if isinstance(document, io.BytesIO):
            document = document.getvalue()
        
        # Try PDF first
        if document[:4] == b'%PDF':
            return self._process_pdf(document)
        
        # Single image
        logger.info("📷 Single image detected")
        return [self._optimize_image(document)]
    
    def detect_duplicates(self, pages: List[bytes]) -> List[bytes]:
        """Remove visually duplicate pages"""
        seen_hashes = set()
        unique_pages = []
        
        for page in pages:
            img_hash = hash(page[:1024])
            if img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                unique_pages.append(page)
        
        logger.info(f"🔄 Deduplication: {len(pages)} -> {len(unique_pages)} pages")
        return unique_pages
    
    def _process_pdf(self, pdf_bytes: bytes) -> List[bytes]:
        """Convert PDF pages to images"""
        pages = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        logger.info(f"📑 PDF has {len(doc)} pages")
        
        for page_num in range(len(doc)):
            logger.info(f"  Rendering page {page_num + 1}...")
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(self.dpi/72, self.dpi/72))
            img_bytes = pix.tobytes("png")
            pages.append(self._optimize_image(img_bytes))
            logger.info(f"  Page {page_num + 1} done: {len(pages[-1])} bytes")
        
        doc.close()
        logger.info(f"✅ PDF processing complete: {len(pages)} pages")
        return pages
    
    def _optimize_image(self, image_bytes: bytes) -> bytes:
        """Optimize image for VLM"""
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        max_size = 2048
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"  Resized image to {new_size}")
        
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()