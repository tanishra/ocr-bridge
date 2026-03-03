from typing import List
from src.core.models import ProcessingResult, ExtractedField
from src.core.enums import ProcessingStatus
from src.storage import ReceiptRepository


class ValidationService:
    """Service for manual validation workflows"""
    
    def __init__(self, repository: ReceiptRepository = None):
        self.repository = repository or ReceiptRepository()
    
    def get_pending_reviews(self, limit: int = 10) -> List[ProcessingResult]:
        """Get items needing manual review"""
        records = self.repository.get_pending_review(limit)
        # Convert records back to ProcessingResult objects
        return []  # Implementation depends on your needs
    
    def submit_correction(
        self,
        receipt_id: str,
        corrected_fields: dict,
        reviewer: str
    ) -> bool:
        """Submit corrected data"""
        record = self.repository.get_by_id(receipt_id)
        if not record:
            return False
        
        record.corrected_data = corrected_fields
        record.reviewed_by = reviewer
        record.status = ProcessingStatus.COMPLETED
        # Commit handled by repository
        
        return True
    
    def calculate_confidence(self, fields: dict) -> float:
        """Recalculate confidence after corrections"""
        if not fields:
            return 0.0
        return sum(
            1.0 if not f.get("corrected") else 0.5 
            for f in fields.values()
        ) / len(fields)