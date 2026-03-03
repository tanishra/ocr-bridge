import asyncio
import os
import tempfile
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from config import get_settings, get_logger
from src.interfaces import IChannelHandler, ChannelMessage
from src.channels.base import BaseChannelHandler


logger = get_logger(__name__)


class TelegramChannelHandler(BaseChannelHandler):
    """Telegram bot implementation"""
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.application: Application = None
    
    async def start(self) -> None:
        """Start the bot"""
        self.application = Application.builder().token(self.token).build()
        
        # Register handlers - PDF handler FIRST (more specific)
        self.application.add_handler(CommandHandler("pay", self._handle_pay_command))
        self.application.add_handler(MessageHandler(filters.Document.PDF, self._handle_document))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))  # Fallback
        self.application.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        
        logger.info("Telegram bot starting...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
    
    async def send_response(self, user_id: str, message: str, attachments: list = None):
        """Send message back to user"""
        await self.application.bot.send_message(
            chat_id=user_id,
            text=message
        )
    
    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo message"""
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            await file.download_to_drive(tmp.name)
            with open(tmp.name, 'rb') as f:
                image_bytes = f.read()
        
        os.unlink(tmp.name)
        
        message = ChannelMessage(
            user_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            content=update.message.caption or "",
            attachments=[image_bytes],
            metadata={"type": "photo"}
        )
        
        await update.message.reply_text("📄 Receipt received, processing...")
        asyncio.create_task(self._handle_incoming(message))
    
    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document (PDF)"""
        doc = update.message.document
        
        # Check file size (max 20MB)
        if doc.file_size > 20 * 1024 * 1024:
            await update.message.reply_text("❌ File too large. Max 20MB.")
            return
        
        # Accept PDF and common document types
        file_name = doc.file_name or ""
        mime_type = doc.mime_type or ""
        
        is_pdf = file_name.lower().endswith('.pdf') or 'pdf' in mime_type.lower()
        
        if not is_pdf:
            await update.message.reply_text(f"❌ PDF files only. Got: {mime_type or file_name}")
            return
        
        try:
            file = await context.bot.get_file(doc.file_id)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                await file.download_to_drive(tmp.name)
                with open(tmp.name, 'rb') as f:
                    doc_bytes = f.read()
            
            os.unlink(tmp.name)
            
            message = ChannelMessage(
                user_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                content=update.message.caption or "",
                attachments=[doc_bytes],
                metadata={"type": "pdf", "filename": doc.file_name}
            )
            
            await update.message.reply_text("📄 PDF received, processing...")
            asyncio.create_task(self._handle_incoming(message))
            
        except Exception as e:
            logger.error(f"Failed to handle PDF: {e}")
            await update.message.reply_text(f"❌ Failed to process PDF: {str(e)}")
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        message = ChannelMessage(
            user_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            content=update.message.text,
            attachments=[],
            metadata={"type": "text"}
        )
        await self._handle_incoming(message)
        await update.message.reply_text("Please send a receipt photo or PDF file.")

    async def _handle_pay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pay <amount> command."""
        args = context.args or []
        message = ChannelMessage(
            user_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            content=update.message.text or "",
            attachments=[],
            metadata={"type": "command", "command": "pay", "args": args}
        )
        await self._handle_incoming(message)
