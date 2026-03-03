from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from .enums import ReceiptType, ProcessingStatus


@dataclass
class ExtractedField:
    name: str
    value: Any
    confidence: float
    raw_text: str = ""
    needs_review: bool = False


@dataclass
class ExtractedReceipt:
    receipt_type: ReceiptType
    fields: Dict[str, ExtractedField] = field(default_factory=dict)
    raw_pages: List[bytes] = field(default_factory=list)
    consolidated: bool = False
    
    def get_field_value(self, name: str, default: Any = None) -> Any:
        field = self.fields.get(name)
        return field.value if field else default
    
    def get_overall_confidence(self) -> float:
        if not self.fields:
            return 0.0
        return sum(f.confidence for f in self.fields.values()) / len(self.fields)


@dataclass
class ProcessingResult:
    id: str
    status: ProcessingStatus
    extracted_receipt: Optional[ExtractedReceipt] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)