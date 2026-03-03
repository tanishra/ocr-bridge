import hmac
import hashlib
from typing import Dict, Any

import requests

from config import get_logger, get_settings


logger = get_logger(__name__)


class RazorpayProvider:
    """Razorpay client for creating UPI payment links and webhook validation."""

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self):
        settings = get_settings()
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def create_upi_payment_link(
        self,
        amount_paise: int,
        reference_id: str,
        description: str,
        telegram_user_id: str,
    ) -> Dict[str, Any]:
        if not self.configured:
            raise ValueError("Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")

        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "reference_id": reference_id,
            "upi_link": True,
            "reminder_enable": True,
            "notes": {
                "telegram_user_id": str(telegram_user_id),
                "local_payment_id": reference_id,
            },
        }

        response = requests.post(
            f"{self.BASE_URL}/payment_links",
            json=payload,
            auth=(self.key_id, self.key_secret),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            raise ValueError("RAZORPAY_WEBHOOK_SECRET is not configured.")

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
