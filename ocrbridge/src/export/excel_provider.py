from typing import List
from src.core.models import ProcessingResult
from src.interfaces import IExportProvider


class ExcelProvider(IExportProvider):
    """Placeholder for local Excel export"""
    
    async def export(self, results: List[ProcessingResult]) -> str:
        raise NotImplementedError("Excel provider not yet implemented")
    
    async def append_single(self, result: ProcessingResult) -> bool:
        raise NotImplementedError("Excel provider not yet implemented")