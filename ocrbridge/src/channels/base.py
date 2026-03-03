from abc import ABC
from src.interfaces import IChannelHandler


class BaseChannelHandler(IChannelHandler, ABC):
    """Base class for channel handlers"""
    
    def __init__(self):
        self.message_callback = None
    
    async def receive_message(self, callback):
        self.message_callback = callback
    
    async def _handle_incoming(self, message):
        if self.message_callback:
            await self.message_callback(message)