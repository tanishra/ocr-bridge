from abc import ABC, abstractmethod
from typing import List
from src.core.models import ProcessingResult


class IExportProvider(ABC):
    """Contract for export destinations"""
    
    @abstractmethod
    async def export(self, results: List[ProcessingResult]) -> str:
        """
        Export results to destination
        Returns: Export reference/URL
        """
        pass
    
    @abstractmethod
    async def append_single(self, result: ProcessingResult) -> bool:
        """Append single result to existing export"""
        pass