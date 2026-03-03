from abc import ABC, abstractmethod
from typing import List, Union
import io


class IDocumentProcessor(ABC):
    """Contract for document preprocessing"""
    
    @abstractmethod
    def process(self, document: Union[bytes, io.BytesIO]) -> List[bytes]:
        """
        Convert document to list of image bytes (one per page)
        Returns: List of PNG/JPEG bytes
        """
        pass
    
    @abstractmethod
    def detect_duplicates(self, pages: List[bytes]) -> List[bytes]:
        """Remove duplicate pages (e.g., same receipt printed twice)"""
        pass