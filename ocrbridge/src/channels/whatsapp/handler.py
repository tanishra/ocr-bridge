from src.interfaces import IChannelHandler


class WhatsAppChannelHandler(IChannelHandler):
    """Placeholder for WhatsApp Business API implementation"""
    
    async def receive_message(self, callback):
        raise NotImplementedError("WhatsApp not implemented")
    
    async def send_response(self, user_id, message, attachments=None):
        raise NotImplementedError("WhatsApp not implemented")
    
    async def start(self):
        raise NotImplementedError("WhatsApp not implemented")