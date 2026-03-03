from sqlalchemy import Column, String, Float, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from src.core.enums import ProcessingStatus, ReceiptType, PaymentStatus


Base = declarative_base()


class ReceiptRecord(Base):
    __tablename__ = "receipts"
    
    id = Column(String, primary_key=True)
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    receipt_type = Column(SQLEnum(ReceiptType))
    
    # Extracted fields stored as JSON
    extracted_data = Column(JSON, default=dict)
    confidence_scores = Column(JSON, default=dict)
    
    # Metadata
    source_channel = Column(String)  # telegram, whatsapp, etc.
    source_user_id = Column(String)
    raw_file_paths = Column(JSON, default=list)  # Stored file references
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Validation
    needs_review = Column(String)  # Reason if needs manual review
    reviewed_by = Column(String)
    corrected_data = Column(JSON)


class PaymentRecord(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    telegram_user_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)  # In INR
    amount_paid = Column(Float, default=0.0)
    currency = Column(String, default="INR")
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.CREATED)

    razorpay_payment_link_id = Column(String, unique=True, index=True)
    short_url = Column(String)
    description = Column(String)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    paid_at = Column(DateTime)
