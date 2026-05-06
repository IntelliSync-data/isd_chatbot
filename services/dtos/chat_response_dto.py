from dataclasses import dataclass
from typing import Any


@dataclass
class ChatResponseDTO:
    bot_message: Any
    session_id: str
    customer_inquiry_created: bool
    conversation_ended: bool = False
