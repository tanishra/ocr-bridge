# ocrbridge/src/interfaces/channel_handler.py
from abc import ABC, abstractmethod
from typing import Callable, Awaitable
from dataclasses import dataclass


@dataclass
class ChannelMessage:
    user_id: str
    message_id: str
    content: str
    attachments: list  # List of file paths or bytes
    metadata: dict


class IChannelHandler(ABC):
    """Contract for channel handlers (Telegram, WhatsApp, etc.)"""
    
    @abstractmethod
    async def receive_message(self, callback: Callable[[ChannelMessage], Awaitable[None]]) -> None:
        """Register callback for incoming messages"""
        pass
    
    @abstractmethod
    async def send_response(
        self,
        user_id: str,
        message: str,
        attachments: list = None
    ) -> None:
        """Send response back to user"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the channel listener"""
        pass
