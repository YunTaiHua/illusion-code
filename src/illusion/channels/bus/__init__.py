"""Message bus module for decoupled channel-agent communication."""

from illusion.channels.bus.events import InboundMessage, OutboundMessage
from illusion.channels.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
