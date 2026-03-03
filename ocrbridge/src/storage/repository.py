from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from src.core.models import ProcessingResult
from src.core.enums import ProcessingStatus, PaymentStatus
from .models import ReceiptRecord, PaymentRecord
from .database import db_manager


class ReceiptRepository:
    """Repository pattern for receipt data access"""
    
    def __init__(self, session: Session = None):
        self.session = session or db_manager.get_session()
    
    def save(self, result: ProcessingResult) -> str:
        record = ReceiptRecord(
            id=result.id,
            status=result.status,
            receipt_type=result.extracted_receipt.receipt_type if result.extracted_receipt else None,
            extracted_data={
                name: {
                    "value": field.value,
                    "confidence": field.confidence
                }
                for name, field in (result.extracted_receipt.fields.items() if result.extracted_receipt else {})
            },
            confidence_scores={
                name: field.confidence
                for name, field in (result.extracted_receipt.fields.items() if result.extracted_receipt else {})
            }
        )
        self.session.merge(record)
        self.session.commit()
        return record.id
    
    def get_by_id(self, receipt_id: str) -> Optional[ReceiptRecord]:
        return self.session.query(ReceiptRecord).filter_by(id=receipt_id).first()
    
    def get_pending_review(self, limit: int = 10) -> List[ReceiptRecord]:
        return self.session.query(ReceiptRecord).filter(
            ReceiptRecord.status == ProcessingStatus.NEEDS_REVIEW
        ).limit(limit).all()
    
    def update_status(self, receipt_id: str, status: ProcessingStatus):
        record = self.get_by_id(receipt_id)
        if record:
            record.status = status
            self.session.commit()


class PaymentRepository:
    """Repository for payment tracking."""

    def __init__(self, session: Session = None):
        self.session = session or db_manager.get_session()

    def create(
        self,
        payment_id: str,
        telegram_user_id: str,
        amount_inr: float,
        status: PaymentStatus,
        razorpay_payment_link_id: str,
        short_url: str,
        description: str,
    ) -> PaymentRecord:
        record = PaymentRecord(
            id=payment_id,
            telegram_user_id=telegram_user_id,
            amount=amount_inr,
            status=status,
            razorpay_payment_link_id=razorpay_payment_link_id,
            short_url=short_url,
            description=description,
        )
        self.session.merge(record)
        self.session.commit()
        return record

    def get_by_link_id(self, link_id: str) -> Optional[PaymentRecord]:
        return self.session.query(PaymentRecord).filter_by(razorpay_payment_link_id=link_id).first()

    def get_by_id(self, payment_id: str) -> Optional[PaymentRecord]:
        return self.session.query(PaymentRecord).filter_by(id=payment_id).first()

    def update_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        amount_paid_inr: Optional[float] = None,
    ) -> Optional[PaymentRecord]:
        record = self.get_by_id(payment_id)
        if not record:
            return None

        record.status = status
        if amount_paid_inr is not None:
            record.amount_paid = amount_paid_inr
        if status == PaymentStatus.PAID:
            record.paid_at = datetime.utcnow()
        self.session.commit()
        return record
