import uuid
import asyncio
from typing import Optional, List
from config import get_logger
from src.core.models import ProcessingResult, ExtractedReceipt
from src.core.enums import ProcessingStatus
from src.interfaces import (
    IVLMProvider, IDocumentProcessor, IReceiptParser, 
    IExportProvider, IChannelHandler
)
from src.storage import ReceiptRepository


logger = get_logger(__name__)


class ReceiptProcessingService:
    """
    Main orchestration service
    SOLID: Depends on abstractions, not concrete implementations
    """
    
    def __init__(
        self,
        vlm_provider: IVLMProvider,
        doc_processor: IDocumentProcessor,
        parser: IReceiptParser,
        export_provider: IExportProvider,
        repository: ReceiptRepository = None
    ):
        self.vlm = vlm_provider
        self.doc_processor = doc_processor
        self.parser = parser
        self.exporter = export_provider
        self.repository = repository
        self._export_lock = asyncio.Lock()
        self.logger = logger
    
    async def process_document(
        self,
        document_bytes: bytes,
        source_channel: str = "unknown",
        source_user: str = "unknown"
    ) -> ProcessingResult:
        """Main processing pipeline"""
        result_id = str(uuid.uuid4())
        self.logger.info(f"[{result_id}] 🚀 Starting processing, size: {len(document_bytes)} bytes")
        
        try:
            # 1. Document preprocessing
            self.logger.info(f"[{result_id}] 📄 Step 1: Document preprocessing...")
            pages = self.doc_processor.process(document_bytes)
            self.logger.info(f"[{result_id}] ✅ Preprocessing done: {len(pages)} pages")
            
            pages = self.doc_processor.detect_duplicates(pages)
            self.logger.info(f"[{result_id}] 🔍 After dedup: {len(pages)} pages")
            
            # 2. VLM Extraction
            self.logger.info(f"[{result_id}] 🤖 Step 2: Gemini OCR extraction...")
            extraction = await self.vlm.extract_from_document(pages)
            self.logger.info(f"[{result_id}] ✅ OCR done: type={extraction.receipt_type}, fields={len(extraction.fields)}")
            
            # 3. Parse and normalize
            self.logger.info(f"[{result_id}] 🔧 Step 3: Parsing...")
            parsed = self.parser.parse(extraction)
            self.logger.info(f"[{result_id}] ✅ Parsing done")
            
            # 4. Determine status based on confidence
            confidence = self.vlm.estimate_confidence(parsed)
            status = ProcessingStatus.NEEDS_REVIEW if confidence < 0.8 else ProcessingStatus.COMPLETED
            self.logger.info(f"[{result_id}] 📊 Confidence: {confidence:.2f}, Status: {status}")
            
            # 5. Build result
            result = ProcessingResult(
                id=result_id,
                status=status,
                extracted_receipt=parsed
            )
            
            # 6. Persist
            self.logger.info(f"[{result_id}] 💾 Step 4: Saving to database...")
            repository = self.repository or ReceiptRepository()
            repository.save(result)
            self.logger.info(f"[{result_id}] ✅ Saved to DB")
            
            # 7. Export to sheets
            self.logger.info(f"[{result_id}] 📤 Step 5: Exporting to Google Sheets...")
            async with self._export_lock:
                export_success = await self.exporter.append_single(result)
            self.logger.info(f"[{result_id}] ✅ Export success: {export_success}")
            
            self.logger.info(f"[{result_id}] 🎉 Processing complete!")
            return result
            
        except Exception as e:
            self.logger.error(f"[{result_id}] 💥 Processing failed: {e}", exc_info=True)
            return ProcessingResult(
                id=result_id,
                status=ProcessingStatus.FAILED,
                error_message=str(e)
            )
