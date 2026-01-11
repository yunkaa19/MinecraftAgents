import json
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, List, Callable

@dataclass
class Message:
    """
    Represents a standard message in the multi-agent system.
    
    Attributes:
        type (str): The type of the message (e.g., 'map.v1').
        source (str): The name of the sender agent.
        target (str): The name of the target agent or 'all'.
        payload (Dict[str, Any]): The content of the message.
        timestamp (float): The time the message was created.
        status (str): The processing status of the message.
        context (Dict[str, Any]): Additional metadata.
    """
    type: str
    source: str
    target: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    status: str = "new"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Converts the message to a JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Creates a Message instance from a JSON string."""
        data = json.loads(json_str)
        return cls(**data)

class MessageValidator:
    """Helper class for validating message structure."""
    REQUIRED_FIELDS = {'type', 'source', 'target', 'timestamp', 'payload', 'status', 'context'}

    @staticmethod
    def validate(message_data: Dict[str, Any]) -> bool:
        """
        Validates that the message dictionary contains all required fields.
        """
        missing_fields = MessageValidator.REQUIRED_FIELDS - message_data.keys()
        if missing_fields:
            raise ValueError(f"Message missing required fields: {missing_fields}")
        return True

    @staticmethod
    def validate_json(json_str: str) -> bool:
        """
        Validates a JSON string against the schema.
        """
        try:
            data = json.loads(json_str)
            return MessageValidator.validate(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string")

class MessageBus:
    """
    A simple Publish-Subscribe message bus for agent communication.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Message], None]]] = {}
        self._history: List[Message] = []
        self.logger = logging.getLogger("MessageBus")

    def subscribe(self, message_type: str, callback: Callable[[Message], None]):
        """
        Subscribes a callback function to a specific message type.
        
        Args:
            message_type (str): The type of message to listen for.
            callback (Callable): The function to call when a message is received.
        """
        if message_type not in self._subscribers:
            self._subscribers[message_type] = []
        self._subscribers[message_type].append(callback)
        self.logger.debug(f"Subscribed to {message_type}")

    def publish(self, message: Message):
        """
        Publishes a message to all subscribers of its type.
        
        Args:
            message (Message): The message to publish.
        """
        self._history.append(message)
        self.logger.info(f"Message published: {message.type} from {message.source}")
        
        if message.type in self._subscribers:
            for callback in self._subscribers[message.type]:
                try:
                    callback(message)
                except Exception as e:
                    self.logger.error(f"Error processing message {message.type}: {e}")

