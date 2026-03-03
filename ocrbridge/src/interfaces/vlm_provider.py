from abc import ABC, abstractmethod
from typing import List
from src.core.models import ExtractedReceipt


class IVLMProvider(ABC):
    """Contract for Vision-Language Model providers"""
    
    @abstractmethod
    async def extract_from_document(
        self,
        image_bytes: List[bytes],
        prompt_template: str
    ) -> ExtractedReceipt:
        """Extract structured data from document images"""
        pass
    
    @abstractmethod
    def estimate_confidence(self, extraction: ExtractedReceipt) -> float:
        """Calculate confidence score (0.0-1.0)"""
        pass