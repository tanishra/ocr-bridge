from enum import Enum


class ReceiptType(str, Enum):
    WEIGHT_SLIP = "weight_slip"
    TAX_INVOICE = "tax_invoice"
    TRANSIT_PASS = "transit_pass"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"
