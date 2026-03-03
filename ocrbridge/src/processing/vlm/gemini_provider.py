import json
import base64
import re
from typing import List
import google.generativeai as genai
from config import get_settings, get_logger
from src.core.models import ExtractedReceipt, ExtractedField
from src.core.enums import ReceiptType
from src.interfaces import IVLMProvider
from src.core.exceptions import OCRFailedException
from .base import BaseVLMProvider


logger = get_logger(__name__)


class GeminiProvider(BaseVLMProvider, IVLMProvider):
    """Gemini Flash VLM implementation"""
    
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.settings = settings
    
    async def extract_from_document(
        self,
        image_bytes: List[bytes],
        prompt_template: str = None
    ) -> ExtractedReceipt:
        try:
            prompt = prompt_template or self._build_consolidation_prompt(len(image_bytes))
            
            # Prepare content parts
            content_parts = [prompt]
            for img_bytes in image_bytes:
                image_part = {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(img_bytes).decode('utf-8')
                }
                content_parts.append(image_part)
            
            # Call Gemini
            response = await self.model.generate_content_async(content_parts)
            raw_text = response.text
            
            # Parse JSON response
            json_str = self._extract_json(raw_text)
            data = json.loads(json_str)
            
            # Build ExtractedReceipt
            receipt_type = self._normalize_receipt_type(data.get("receipt_type", "UNKNOWN"))
            fields = {}
            
            for field_name, field_data in data.get("fields", {}).items():
                fields[field_name] = ExtractedField(
                    name=field_name,
                    value=field_data.get("value"),
                    confidence=field_data.get("confidence", 0.5),
                    raw_text=str(field_data.get("value", "")),
                    needs_review=field_data.get("confidence", 1.0) < 0.8
                )
            
            return ExtractedReceipt(
                receipt_type=receipt_type,
                fields=fields,
                raw_pages=image_bytes,
                consolidated=len(image_bytes) > 1
            )
            
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            raise OCRFailedException(f"OCR failed: {e}")
    
    def estimate_confidence(self, extraction: ExtractedReceipt) -> float:
        return extraction.get_overall_confidence()
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from markdown code blocks or raw text"""
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()

    def _normalize_receipt_type(self, raw_type) -> ReceiptType:
        """Handle noisy model output and map safely to known receipt types."""
        if isinstance(raw_type, list):
            candidate_text = " ".join(str(v) for v in raw_type)
        else:
            candidate_text = str(raw_type or "")

        text = candidate_text.upper()
        # Handles values like "WEIGHT_SLIP, TAX_INVOICE, TRANSIT_PASS"
        tokens = set(re.findall(r"[A-Z_]+", text))

        for token in ("WEIGHT_SLIP", "TAX_INVOICE", "TRANSIT_PASS"):
            if token in tokens:
                return ReceiptType[token]

        return ReceiptType.UNKNOWN
