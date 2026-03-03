from src.interfaces import IReceiptParser


class BaseReceiptParser(IReceiptParser):
    """Base parser with common validation logic"""
    
    def _clean_vehicle_number(self, raw: str) -> str:
        """Standardize vehicle number format"""
        if not raw:
            return ""
        # Remove spaces, uppercase
        cleaned = raw.upper().replace(" ", "").replace("-", "")
        return cleaned
    
    def _clean_weight(self, raw: str) -> float:
        """Extract numeric weight value"""
        if not raw:
            return 0.0
        try:
            return float(str(raw).replace(",", "").split()[0])
        except (ValueError, IndexError):
            return 0.0
    
    def _clean_amount(self, raw: str) -> float:
        """Extract numeric amount"""
        if not raw:
            return 0.0
        try:
            cleaned = str(raw).replace("₹", "").replace(",", "").replace("INR", "").strip()
            return float(cleaned.split()[0])
        except (ValueError, IndexError):
            return 0.0