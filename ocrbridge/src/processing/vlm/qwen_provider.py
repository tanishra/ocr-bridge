from typing import List
from src.core.models import ExtractedReceipt
from src.interfaces import IVLMProvider


class QwenProvider(IVLMProvider):
    """Placeholder for local Qwen implementation"""
    
    async def extract_from_document(
        self,
        image_bytes: List[bytes],
        prompt_template: str
    ) -> ExtractedReceipt:
        raise NotImplementedError("Qwen provider not yet implemented")
    
    def estimate_confidence(self, extraction: ExtractedReceipt) -> float:
        return 0.0