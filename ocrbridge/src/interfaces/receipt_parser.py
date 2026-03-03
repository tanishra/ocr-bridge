from abc import ABC, abstractmethod
from src.core.models import ExtractedReceipt


class IReceiptParser(ABC):
    """Contract for parsing specific receipt types"""
    
    @abstractmethod
    def can_parse(self, raw_text: str) -> bool:
        """Check if this parser can handle the receipt"""
        pass
    
    @abstractmethod
    def parse(self, extracted_receipt: ExtractedReceipt) -> ExtractedReceipt:
        """Parse and normalize the extracted data"""
        pass