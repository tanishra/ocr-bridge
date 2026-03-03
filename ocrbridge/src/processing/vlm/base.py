from abc import ABC
from src.core.models import ExtractedReceipt


class BaseVLMProvider(ABC):
    """Base class for VLM providers with common functionality"""
    
    def _build_consolidation_prompt(self, num_pages: int) -> str:
        """Build prompt for multi-page receipt consolidation"""
        return f"""
You are analyzing a multi-page receipt document with {num_pages} pages.
Your task is to extract ALL relevant fields and consolidate them into a single logical record.

IMPORTANT RULES:
1. If the same field appears on multiple pages with the same value, extract it once
2. If different pages have different values for the same field (e.g., different dates, amounts), extract all unique values
3. Identify the receipt type: WEIGHT_SLIP, TAX_INVOICE, or TRANSIT_PASS
4. Return data in this exact JSON format:

{{
    "receipt_type": "WEIGHT_SLIP|TRANSIT_PASS|TAX_INVOICE",
    "confidence": 0.95,
    "fields": {{
        "field_name": {{
            "value": "extracted_value",
            "confidence": 0.95,
            "page_number": 1
        }}
    }},
    "consolidation_notes": "Any special handling done"
}}

Extract these standard fields if present:
- vehicle_number, driver_name, date, gross_weight, tare_weight, net_weight
- invoice_number, amount, tax_amount, total_amount
- transit_pass_number, origin, destination, distance
- party_name, item_name, quantity

Be precise with numbers and dates. Flag any unclear text.
"""