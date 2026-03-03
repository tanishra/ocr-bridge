import os
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import requests
import uvicorn

from config import setup_logging, get_logger, get_settings
from src.services import ReceiptProcessingService, PaymentService
from src.core.enums import ProcessingStatus, PaymentStatus
from src.processing.vlm import GeminiProvider
from src.processing import DocumentProcessor
from src.processing.parsers import StandardParser
from src.export import GoogleSheetsProvider
from src.storage import db_manager
from src.payments import RazorpayProvider


logger = get_logger(__name__)


# Global service instance
processing_service: ReceiptProcessingService = None
payment_service: PaymentService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global processing_service, payment_service
    
    setup_logging()
    logger.info("🚀 Starting OCRBridge API...")
    
    # Initialize database
    db_manager.create_tables()
    logger.info("✅ Database ready")
    
    # Initialize services (Singleton pattern)
    processing_service = ReceiptProcessingService(
        vlm_provider=GeminiProvider(),
        doc_processor=DocumentProcessor(),
        parser=StandardParser(),
        export_provider=GoogleSheetsProvider()
    )
    logger.info("✅ Processing service ready")

    payment_service = PaymentService(provider=RazorpayProvider())
    if payment_service.configured:
        logger.info("✅ Payment service ready")
    else:
        logger.warning("⚠️ Payment service not configured (Razorpay keys missing)")
    
    yield
    
    logger.info("🛑 Shutting down OCRBridge API...")


app = FastAPI(
    title="OCRBridge API",
    description="AI-powered receipt processing for Indian logistics",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PaymentLinkRequest(BaseModel):
    telegram_user_id: str
    amount_inr: float
    description: str = "OCRBridge receipt processing payment"


@app.post("/process")
async def process_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Process a receipt (PDF or image)
    Returns immediately with receipt ID, processes in background
    """
    _validate_upload(file)
    try:
        contents = await file.read()
        logger.info(f"📥 Received file: {file.filename}, size: {len(contents)} bytes")
        
        result = await processing_service.process_document(
            document_bytes=contents,
            source_channel="api",
            source_user="web_upload"
        )
        
        return _serialize_result(result)
        
    except Exception as e:
        logger.error(f"💥 API error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/process-batch")
async def process_batch(files: List[UploadFile] = File(...)):
    """Process multiple receipts in parallel with per-file isolation."""
    if not files:
        raise HTTPException(400, "No files provided")

    for file in files:
        _validate_upload(file)

    semaphore = asyncio.Semaphore(3)

    async def _process_one(file: UploadFile) -> Dict[str, Any]:
        try:
            async with semaphore:
                contents = await file.read()
                logger.info(f"📥 Batch file: {file.filename}, size: {len(contents)} bytes")
                result = await processing_service.process_document(
                    document_bytes=contents,
                    source_channel="api_batch",
                    source_user="web_upload"
                )
                payload = _serialize_result(result)
                payload["filename"] = file.filename
                return payload
        except Exception as e:
            logger.error(f"💥 Batch item failed ({file.filename}): {e}", exc_info=True)
            return {
                "filename": file.filename,
                "success": False,
                "status": "failed",
                "error": str(e),
                "data": {"receipt_type": None, "confidence": 0, "fields": {}}
            }

    results = await asyncio.gather(*[_process_one(file) for file in files], return_exceptions=False)
    success_count = sum(1 for r in results if r.get("success"))

    return {
        "total": len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "results": results
    }


@app.post("/payments/create-link")
async def create_payment_link(request: PaymentLinkRequest):
    if not payment_service or not payment_service.configured:
        raise HTTPException(503, "Payments are not configured on server")
    try:
        return payment_service.create_payment_link(
            telegram_user_id=request.telegram_user_id,
            amount_inr=request.amount_inr,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Failed creating payment link: {e}", exc_info=True)
        raise HTTPException(500, "Could not create payment link")


@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
):
    if not payment_service:
        raise HTTPException(503, "Payment service unavailable")

    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid webhook JSON payload")

    try:
        result = payment_service.process_webhook(body, x_razorpay_signature, payload)
        if not result:
            return {"ok": True, "message": "Webhook accepted (no matching payment record)"}

        if result["status"] == PaymentStatus.PAID.value:
            _notify_telegram_payment_success(
                telegram_user_id=result["telegram_user_id"],
                payment_id=result["payment_id"],
                amount=result["amount_paid"] or result["amount"],
            )

        return {"ok": True, "payment": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(500, "Webhook processing failed")


def _validate_upload(file: UploadFile) -> None:
    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
        "image/webp",
    }
    allowed_ext = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}

    content_type = (file.content_type or "").lower()
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if content_type in allowed_types or ext in allowed_ext:
        return

    raise HTTPException(
        400,
        f"Invalid file type: {file.content_type or filename}. Allowed: PDF, JPEG, PNG, WEBP"
    )


def _serialize_result(result):
    return {
        "success": result.status == ProcessingStatus.COMPLETED,
        "receipt_id": result.id,
        "status": result.status.value,
        "error": result.error_message,
        "data": {
            "receipt_type": result.extracted_receipt.receipt_type.name if result.extracted_receipt else None,
            "confidence": result.extracted_receipt.get_overall_confidence() if result.extracted_receipt else 0,
            "fields": {
                name: {
                    "value": field.value,
                    "confidence": field.confidence
                }
                for name, field in (result.extracted_receipt.fields.items() if result.extracted_receipt else {})
            }
        }
    }


def _notify_telegram_payment_success(telegram_user_id: str, payment_id: str, amount: float) -> None:
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": telegram_user_id,
                "text": (
                    "✅ Payment received successfully.\n"
                    f"Amount: INR {amount:.2f}\n"
                    f"Payment ID: {payment_id}"
                ),
            },
            timeout=10,
        )
    except Exception:
        logger.exception("Failed sending Telegram payment success message")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OCRBridge API",
        "version": "0.1.0"
    }


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
