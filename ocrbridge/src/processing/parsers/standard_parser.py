from src.core.models import ExtractedReceipt
from src.core.enums import ReceiptType
from src.core.models import ExtractedField
from config import get_logger
from .base import BaseReceiptParser


logger = get_logger(__name__)


class StandardParser(BaseReceiptParser):
    """Parser for mining/logistics receipts"""
    
    KEY_INDICATORS = {
        ReceiptType.WEIGHT_SLIP: ["FINAL WEIGHT SLIP", "Gross", "Tare", "Net Weight"],
        ReceiptType.TAX_INVOICE: ["Tax Invoice", "GSTIN", "HSN/SAC", "IGST"],
        ReceiptType.TRANSIT_PASS: ["Transit Pass", "Directorate of Geology", "ISTP", "e-Transit"]
    }
    
    def can_parse(self, raw_text: str) -> bool:
        """Check if any known indicator is present"""
        text_upper = raw_text.upper()
        for indicators in self.KEY_INDICATORS.values():
            if any(ind.upper() in text_upper for ind in indicators):
                return True
        return False
    
    def parse(self, extracted_receipt: ExtractedReceipt) -> ExtractedReceipt:
        """Normalize and validate extracted fields"""
        fields = extracted_receipt.fields
        
        # Normalize vehicle number
        if "vehicle_number" in fields:
            raw = fields["vehicle_number"].value
            fields["vehicle_number"].value = self._clean_vehicle_number(raw)
        
        # Normalize weights
        for weight_field in ["gross_weight", "tare_weight", "net_weight"]:
            if weight_field in fields:
                raw = fields[weight_field].value
                fields[weight_field].value = self._clean_weight(raw)
        
        # Normalize amounts
        for amount_field in ["amount", "tax_amount", "total_amount"]:
            if amount_field in fields:
                raw = fields[amount_field].value
                fields[amount_field].value = self._clean_amount(raw)
        
        # Cross-validate: net_weight should equal gross - tare
        self._validate_weights(fields)
        
        logger.info(f"Parsed receipt: {extracted_receipt.receipt_type}")
        return extracted_receipt
    
    def _validate_weights(self, fields: dict) -> None:
        """Validate weight calculations"""
        empty = ExtractedField(name="", value=0.0, confidence=0.0)
        gross = fields.get("gross_weight", empty).value or 0
        tare = fields.get("tare_weight", empty).value or 0
        net = fields.get("net_weight", empty).value or 0
        
        if gross and tare and net:
            calculated_net = gross - tare
            if abs(calculated_net - net) > 1.0:  # Allow 1kg tolerance
                fields["net_weight"].needs_review = True
                fields["net_weight"].confidence = 0.5
