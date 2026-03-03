from abc import ABC


class BaseExportProvider(ABC):
    """Base class for export providers"""
    
    def _normalize_for_sheets(self, value) -> str:
        """Convert value to string safe for Sheets"""
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)