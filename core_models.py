from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    name: str
    id: str
    platform: str


@dataclass
class Message:
    content: str
    sender: str
    timestamp: datetime | int | str
    channel: Channel
    message_type: str


@dataclass
class Notification:
    message: Message
    original_message: Optional[str] = None
    url: str = ""
