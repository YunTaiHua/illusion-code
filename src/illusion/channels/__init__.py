"""IllusionCode channels subsystem.

Provides a message-bus architecture for integrating chat platforms
(Telegram, Discord, Slack, etc.) with the IllusionCode query engine.

Usage::

    from illusion.channels import BaseChannel, ChannelManager, MessageBus
"""

from illusion.channels.bus.events import InboundMessage, OutboundMessage
from illusion.channels.bus.queue import MessageBus
from illusion.channels.impl.base import BaseChannel
from illusion.channels.impl.manager import ChannelManager

__all__ = [
    "BaseChannel",
    "ChannelManager",
    "InboundMessage",
    "MessageBus",
    "OutboundMessage",
]
