import asyncio
from config import setup_logging, get_logger
from src.channels.telegram.handler import TelegramChannelHandler
from src.services import ReceiptProcessingService, PaymentService
from src.core.enums import ProcessingStatus


logger = get_logger(__name__)


class OCRBridgeBot:
    """Main bot orchestrator"""
    
    def __init__(self, processing_service: ReceiptProcessingService, payment_service: PaymentService = None):
        self.telegram = TelegramChannelHandler()
        self.processor = processing_service
        self.payment_service = payment_service
        self.max_parallel = 3
        self.display_fields = [
            "date", "vehicle_number", "driver_name", "party_name",
            "item_name", "gross_weight", "tare_weight", "net_weight",
            "quantity", "amount", "tax_amount", "total_amount",
            "transit_pass_number", "origin", "destination", "distance"
        ]
    
    async def _on_message(self, message):
        """Handle incoming messages"""
        logger.info(f"📨 Received message from {message.user_id}, type: {message.metadata.get('type')}")

        if message.metadata.get("type") == "command":
            command = message.metadata.get("command")
            if command == "pay":
                await self._handle_pay_command(message)
                return
        
        if not message.attachments:
            await self.telegram.send_response(
                message.user_id,
                "Please send a receipt photo or PDF."
            )
            return
        
        semaphore = asyncio.Semaphore(self.max_parallel)
        tasks = [
            self._process_attachment(message, attachment, idx + 1, len(message.attachments), semaphore)
            for idx, attachment in enumerate(message.attachments)
        ]
        await asyncio.gather(*tasks, return_exceptions=False)
    
    async def _process_attachment(self, message, attachment, current, total, semaphore):
        async with semaphore:
            logger.info(f"🔄 Processing attachment {current}/{total}, size: {len(attachment)} bytes")
            stop_event = asyncio.Event()
            progress_task = asyncio.create_task(
                self._send_progress_updates(message.user_id, current, total, stop_event)
            )
            try:
                result = await self.processor.process_document(
                    attachment,
                    source_channel="telegram",
                    source_user=message.user_id
                )
                
                logger.info(f"✅ Result: ID={result.id}, Status={result.status}, Error={result.error_message}")
                
                if result.status == ProcessingStatus.COMPLETED:
                    await self._send_success(message.user_id, result)
                elif result.status == ProcessingStatus.NEEDS_REVIEW:
                    await self._send_needs_review(message.user_id, result)
                else:
                    await self.telegram.send_response(
                        message.user_id,
                        f"❌ Processing failed: {result.error_message}"
                    )
                    
            except Exception as e:
                logger.error(f"💥 Exception during processing: {e}", exc_info=True)
                await self.telegram.send_response(
                    message.user_id,
                    f"❌ Error: {str(e)}"
                )
            finally:
                stop_event.set()
                await progress_task
    
    async def _send_success(self, user_id: str, result):
        """Send success message with extracted data"""
        fields = result.extracted_receipt.fields
        summary = "✅ Receipt Processed\n\n"

        for field in self.display_fields:
            if field in fields:
                summary += f"{field.replace('_', ' ').title()}: {fields[field].value}\n"

        summary += f"Receipt Type: {result.extracted_receipt.receipt_type.name}\n"
        summary += f"Confidence: {result.extracted_receipt.get_overall_confidence():.2f}\n"
        summary += f"Status: {result.status.name}\n"
        
        await self.telegram.send_response(user_id, summary)
    
    async def _send_needs_review(self, user_id: str, result):
        """Send message for low confidence extraction"""
        await self.telegram.send_response(
            user_id,
            "⚠️ Receipt processed but needs manual review.\n"
            f"ID: {result.id}\n"
            "Please check the dashboard to verify."
        )

    async def _send_progress_updates(self, user_id: str, current: int, total: int, stop_event: asyncio.Event):
        """
        Send non-technical progress pings while processing is ongoing.
        Stops automatically when processing completes.
        """
        steps = [
            "🔎 Working on your file...",
            "🤖 Extracting receipt details...",
            "🧾 Validating fields and totals...",
            "📤 Finalizing result..."
        ]

        for text in steps:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=6)
                return
            except asyncio.TimeoutError:
                try:
                    prefix = f"({current}/{total}) " if total > 1 else ""
                    await self.telegram.send_response(user_id, f"{prefix}{text}")
                except Exception:
                    # Never fail main processing if a progress ping fails.
                    logger.exception("Failed to send Telegram progress update")

    async def _handle_pay_command(self, message):
        """Create UPI payment link from `/pay <amount>` command."""
        if not self.payment_service or not self.payment_service.configured:
            await self.telegram.send_response(
                message.user_id,
                "⚠️ Payments are not configured right now."
            )
            return

        args = message.metadata.get("args", [])
        if not args:
            await self.telegram.send_response(
                message.user_id,
                "Usage: /pay <amount_in_inr>\nExample: /pay 99"
            )
            return

        try:
            amount = float(args[0])
        except ValueError:
            await self.telegram.send_response(
                message.user_id,
                "❌ Invalid amount. Example: /pay 99"
            )
            return

        if amount <= 0:
            await self.telegram.send_response(
                message.user_id,
                "❌ Amount must be greater than 0."
            )
            return

        try:
            payment = await asyncio.to_thread(
                self.payment_service.create_payment_link,
                message.user_id,
                amount,
                "OCRBridge payment via Telegram",
            )
            await self.telegram.send_response(
                message.user_id,
                "💳 UPI Payment Link\n"
                f"Amount: INR {amount:.2f}\n"
                f"Pay here: {payment['short_url']}\n"
                f"Payment ID: {payment['payment_id']}\n"
                "You will receive a confirmation message after payment."
            )
        except Exception as e:
            logger.error(f"Failed to create payment link: {e}", exc_info=True)
            await self.telegram.send_response(
                message.user_id,
                "❌ Could not create payment link. Please try again."
            )
    
    async def run(self):
        """Start the bot"""
        setup_logging()
        logger.info("Starting OCRBridge Bot...")
        await self.telegram.receive_message(self._on_message)
        await self.telegram.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)


# Entry point
if __name__ == "__main__":
    # Dependencies would be injected here in production
    from src.processing.vlm import GeminiProvider
    from src.processing import DocumentProcessor
    from src.processing.parsers import StandardParser
    from src.export import GoogleSheetsProvider
    from src.payments import RazorpayProvider
    from src.services import PaymentService
    
    processor = ReceiptProcessingService(
        vlm_provider=GeminiProvider(),
        doc_processor=DocumentProcessor(),
        parser=StandardParser(),
        export_provider=GoogleSheetsProvider()
    )

    payments = PaymentService(provider=RazorpayProvider())
    
    bot = OCRBridgeBot(processor, payments)
    asyncio.run(bot.run())


# Backward compatibility
ParchiBot = OCRBridgeBot
