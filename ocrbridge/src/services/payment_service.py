import uuid
from typing import Dict, Any, Optional

from config import get_logger
from src.core.enums import PaymentStatus
from src.storage import PaymentRepository
from src.payments import RazorpayProvider


logger = get_logger(__name__)


class PaymentService:
    """Create/track payment links and process Razorpay webhook events."""

    def __init__(self, provider: RazorpayProvider, repository: PaymentRepository = None):
        self.provider = provider
        self.repository = repository or PaymentRepository()

    @property
    def configured(self) -> bool:
        return self.provider.configured

    def create_payment_link(
        self,
        telegram_user_id: str,
        amount_inr: float,
        description: str = "OCRBridge receipt processing payment",
    ) -> Dict[str, Any]:
        if amount_inr <= 0:
            raise ValueError("Amount must be greater than 0")

        payment_id = str(uuid.uuid4())
        amount_paise = int(round(amount_inr * 100))

        link = self.provider.create_upi_payment_link(
            amount_paise=amount_paise,
            reference_id=payment_id,
            description=description,
            telegram_user_id=telegram_user_id,
        )

        self.repository.create(
            payment_id=payment_id,
            telegram_user_id=telegram_user_id,
            amount_inr=amount_inr,
            status=PaymentStatus.CREATED,
            razorpay_payment_link_id=link.get("id", ""),
            short_url=link.get("short_url", ""),
            description=description,
        )

        return {
            "payment_id": payment_id,
            "amount_inr": amount_inr,
            "currency": "INR",
            "link_id": link.get("id"),
            "short_url": link.get("short_url"),
            "status": link.get("status", "created"),
        }

    def process_webhook(self, body: bytes, signature: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.provider.verify_webhook_signature(body, signature):
            raise ValueError("Invalid Razorpay webhook signature")

        event = payload.get("event", "")
        payment_link = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
        link_id = payment_link.get("id")
        if not link_id:
            return None

        record = self.repository.get_by_link_id(link_id)
        if not record:
            return None

        raw_status = str(payment_link.get("status", "")).lower()
        status_map = {
            "paid": PaymentStatus.PAID,
            "partially_paid": PaymentStatus.PARTIALLY_PAID,
            "cancelled": PaymentStatus.CANCELLED,
            "expired": PaymentStatus.EXPIRED,
            "created": PaymentStatus.CREATED,
            "failed": PaymentStatus.FAILED,
        }
        mapped_status = status_map.get(raw_status, PaymentStatus.CREATED)

        if event == "payment_link.paid":
            mapped_status = PaymentStatus.PAID

        amount_paid_paise = payment_link.get("amount_paid")
        amount_paid_inr = (amount_paid_paise / 100.0) if isinstance(amount_paid_paise, (int, float)) else None

        updated = self.repository.update_status(
            payment_id=record.id,
            status=mapped_status,
            amount_paid_inr=amount_paid_inr,
        )
        if not updated:
            return None

        return {
            "payment_id": updated.id,
            "telegram_user_id": updated.telegram_user_id,
            "status": updated.status.value,
            "amount": updated.amount,
            "amount_paid": updated.amount_paid,
            "razorpay_link_id": updated.razorpay_payment_link_id,
        }
