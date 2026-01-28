"""Message adapter for SDK compatibility.

This module provides adapters to convert between internal message types
and SDK compatible message types.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any, AsyncIterator

from .types import (
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    StreamEvent,
    ContentBlock,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)

# Define internal message types for Ripperdoc
# Since we're making this standalone, we need to define these here


class InternalMessage:
    """Internal message structure matching Ripperdoc's format."""

    def __init__(
        self,
        role: str,
        content: str | list[Any],
        model: str | None = None,
    ):
        self.role = role
        self.content = content
        self.model = model


class InternalUserMessage:
    """Internal user message structure."""

    def __init__(
        self,
        message: InternalMessage,
        uuid: str | None = None,
        parent_tool_use_id: str | None = None,
        tool_use_result: dict[str, Any] | None = None,
    ):
        self.message = message
        self.uuid = uuid
        self.parent_tool_use_id = parent_tool_use_id
        self.tool_use_result = tool_use_result
        self.type = "user"


class InternalAssistantMessage:
    """Internal assistant message structure."""

    def __init__(
        self,
        message: InternalMessage,
        model: str | None = None,
        is_api_error_message: bool = False,
        parent_tool_use_id: str | None = None,
    ):
        self.message = message
        self.model = model or ""
        self.is_api_error_message = is_api_error_message
        self.parent_tool_use_id = parent_tool_use_id
        self.type = "assistant"


class InternalProgressMessage:
    """Internal progress message structure."""

    def __init__(
        self,
        tool_use_id: str,
        content: Any,
    ):
        self.tool_use_id = tool_use_id
        self.content = content
        self.type = "progress"


class MessageContent:
    """Message content block structure."""

    def __init__(
        self,
        type: str,
        text: str | None = None,
        thinking: str | None = None,
        signature: str | None = None,
        id: str | None = None,
        tool_use_id: str | None = None,
        name: str | None = None,
        input: dict[str, Any] | None = None,
        is_error: bool | None = None,
    ):
        self.type = type
        self.text = text
        self.thinking = thinking
        self.signature = signature
        self.id = id
        self.tool_use_id = tool_use_id
        self.name = name
        self.input = input
        self.is_error = is_error


InternalMessageType = InternalUserMessage | InternalAssistantMessage | InternalProgressMessage


# =============================================================================
# Message Adapter
# =============================================================================

class MessageAdapter:
    """Adapter for converting between Ripperdoc and SDK message types.

    Ripperdoc uses an internal message structure (with nested Message objects),
    while SDK uses a flat ContentBlock-based structure. This adapter
    bridges the gap between the two formats.
    """

    @staticmethod
    def to_sdk_message(
        msg: InternalMessageType,
        model: str | None = None,
        session_id: str | None = None,
    ) -> Message:
        """Convert a Ripperdoc message to a SDK compatible message.

        Args:
            msg: The Ripperdoc message to convert
            model: The model name (for AssistantMessage)
            session_id: The session ID (for ResultMessage)

        Returns:
            A SDK compatible Message
        """
        msg_type = getattr(msg, "type", None)

        if msg_type == "user" or isinstance(msg, InternalUserMessage):
            return MessageAdapter._user_to_sdk(msg)
        elif msg_type == "assistant" or isinstance(msg, InternalAssistantMessage):
            return MessageAdapter._assistant_to_sdk(msg, model or "")
        elif msg_type == "progress" or isinstance(msg, InternalProgressMessage):
            return MessageAdapter._progress_to_sdk(msg)
        else:
            return SystemMessage(
                subtype="unknown",
                data={"original_message": str(msg)},
            )

    @staticmethod
    def _user_to_sdk(msg: InternalUserMessage) -> UserMessage:
        """Convert Ripperdoc UserMessage to SDK UserMessage."""
        content: str | list[ContentBlock] = []
        has_blocks = False

        inner_msg = getattr(msg, "message", None)
        if inner_msg is None:
            return UserMessage(
                content=getattr(msg, "content", str(msg)),
                uuid=getattr(msg, "uuid", None),
                parent_tool_use_id=getattr(msg, "parent_tool_use_id", None),
                tool_use_result=getattr(msg, "tool_use_result", None),
            )

        inner_content = getattr(inner_msg, "content", None)
        if isinstance(inner_content, str):
            content = inner_content
        elif isinstance(inner_content, list):
            content = []
            for item in inner_content:
                if isinstance(item, MessageContent):
                    block = MessageAdapter._content_to_block(item)
                    if block:
                        content.append(block)
                        has_blocks = True
                elif isinstance(item, dict):
                    block = MessageAdapter._dict_to_block(item)
                    if block:
                        content.append(block)
                        has_blocks = True

            if not has_blocks and not content:
                content = str(inner_msg.content or "")

        return UserMessage(
            content=content,
            uuid=getattr(msg, "uuid", None),
            parent_tool_use_id=getattr(msg, "parent_tool_use_id", None),
            tool_use_result=getattr(msg, "tool_use_result", None),
        )

    @staticmethod
    def _assistant_to_sdk(
        msg: InternalAssistantMessage, model: str
    ) -> AssistantMessage:
        """Convert Ripperdoc AssistantMessage to SDK AssistantMessage."""
        content: list[ContentBlock] = []

        inner_msg = getattr(msg, "message", None)
        if inner_msg is None:
            return AssistantMessage(
                content=[],
                model=model,
                parent_tool_use_id=getattr(msg, "parent_tool_use_id", None),
                error=getattr(msg, "error", None),
            )

        inner_content = getattr(inner_msg, "content", None)
        if isinstance(inner_content, list):
            for item in inner_content:
                if isinstance(item, MessageContent):
                    block = MessageAdapter._content_to_block(item)
                    if block:
                        content.append(block)
                elif isinstance(item, dict):
                    block = MessageAdapter._dict_to_block(item)
                    if block:
                        content.append(block)
        elif isinstance(inner_content, str):
            content = [TextBlock(text=inner_content)]

        return AssistantMessage(
            content=content,
            model=model,
            parent_tool_use_id=getattr(msg, "parent_tool_use_id", None),
            error=getattr(msg, "is_api_error_message", None),
        )

    @staticmethod
    def _progress_to_sdk(msg: InternalProgressMessage) -> SystemMessage:
        """Convert Ripperdoc ProgressMessage to SDK SystemMessage."""
        return SystemMessage(
            subtype="progress",
            data={
                "tool_use_id": getattr(msg, "tool_use_id", ""),
                "content": getattr(msg, "content", None),
            },
        )

    @staticmethod
    def _content_to_block(content: MessageContent) -> ContentBlock | None:
        """Convert a MessageContent to a ContentBlock."""
        content_type = getattr(content, "type", None)

        if content_type == "text" or content_type is None:
            return TextBlock(text=getattr(content, "text", ""))

        elif content_type == "thinking":
            return ThinkingBlock(
                thinking=getattr(content, "thinking", ""),
                signature=getattr(content, "signature", ""),
            )

        elif content_type == "redacted_thinking":
            return ThinkingBlock(
                thinking=getattr(content, "data", ""),
                signature=getattr(content, "signature", ""),
            )

        elif content_type == "tool_use":
            return ToolUseBlock(
                id=getattr(content, "id", "")
                or getattr(content, "tool_use_id", "")
                or "",
                name=getattr(content, "name", ""),
                input=getattr(content, "input", {}) or {},
            )

        elif content_type == "tool_result":
            return ToolResultBlock(
                tool_use_id=getattr(content, "tool_use_id", "")
                or getattr(content, "id", "")
                or "",
                content=getattr(content, "text", None),
                is_error=getattr(content, "is_error", None),
            )

        else:
            return TextBlock(text=str(content))

    @staticmethod
    def _dict_to_block(d: dict[str, Any]) -> ContentBlock | None:
        """Convert a dict to a ContentBlock."""
        block_type = d.get("type")

        if block_type == "text":
            return TextBlock(text=d.get("text", ""))

        elif block_type == "thinking":
            return ThinkingBlock(
                thinking=d.get("thinking", ""),
                signature=d.get("signature", ""),
            )

        elif block_type == "redacted_thinking":
            return ThinkingBlock(
                thinking=d.get("data", ""),
                signature=d.get("signature", ""),
            )

        elif block_type == "tool_use":
            return ToolUseBlock(
                id=d.get("id", "") or d.get("tool_use_id", "") or "",
                name=d.get("name", ""),
                input=d.get("input", {}) or {},
            )

        elif block_type == "tool_result":
            return ToolResultBlock(
                tool_use_id=d.get("tool_use_id", "") or d.get("id", "") or "",
                content=d.get("text", None) or d.get("content", None),
                is_error=d.get("is_error", None),
            )

        else:
            return TextBlock(text=str(d))

    @staticmethod
    def from_sdk_message(msg: Message) -> InternalUserMessage | InternalAssistantMessage:
        """Convert a SDK message to a Ripperdoc message.

        Args:
            msg: The SDK compatible message to convert

        Returns:
            A Ripperdoc internal message
        """
        if isinstance(msg, UserMessage):
            return MessageAdapter._sdk_user_to_ripperdoc(msg)
        elif isinstance(msg, AssistantMessage):
            return MessageAdapter._sdk_assistant_to_ripperdoc(msg)
        else:
            return InternalAssistantMessage(
                message=InternalMessage(role="assistant", content=""),
            )

    @staticmethod
    def _sdk_user_to_ripperdoc(msg: UserMessage) -> InternalUserMessage:
        """Convert SDK UserMessage to Ripperdoc UserMessage."""
        content = msg.content

        if isinstance(content, list):
            message_contents = []
            for block in content:
                mc = MessageAdapter._block_to_content(block)
                if mc:
                    message_contents.append(mc)

            inner_msg = InternalMessage(role="user", content=message_contents)
        else:
            inner_msg = InternalMessage(role="user", content=content)

        return InternalUserMessage(
            message=inner_msg,
            uuid=msg.uuid,
            tool_use_result=msg.tool_use_result,
        )

    @staticmethod
    def _sdk_assistant_to_ripperdoc(msg: AssistantMessage) -> InternalAssistantMessage:
        """Convert SDK AssistantMessage to Ripperdoc AssistantMessage."""
        message_contents = []

        for block in msg.content:
            mc = MessageAdapter._block_to_content(block)
            if mc:
                message_contents.append(mc)

        inner_msg = InternalMessage(
            role="assistant",
            content=message_contents if message_contents else "",
        )

        return InternalAssistantMessage(
            message=inner_msg,
            model=msg.model,
            is_api_error_message=bool(msg.error),
        )

    @staticmethod
    def _block_to_content(block: ContentBlock) -> MessageContent | None:
        """Convert a ContentBlock to a MessageContent."""
        if isinstance(block, TextBlock):
            return MessageContent(type="text", text=block.text)

        elif isinstance(block, ThinkingBlock):
            return MessageContent(
                type="thinking",
                thinking=block.thinking,
                signature=block.signature,
            )

        elif isinstance(block, ToolUseBlock):
            return MessageContent(
                type="tool_use",
                id=block.id,
                name=block.name,
                input=block.input,
            )

        elif isinstance(block, ToolResultBlock):
            return MessageContent(
                type="tool_result",
                tool_use_id=block.tool_use_id,
                text=block.content if isinstance(block.content, str) else None,
                is_error=block.is_error,
            )

        else:
            return None


# =============================================================================
# Async Message Stream Adapter
# =============================================================================

class AsyncMessageAdapter:
    """Async iterator that adapts Ripperdoc messages to SDK messages."""

    def __init__(
        self,
        source: AsyncIterable[InternalMessageType],
        model: str | None = None,
    ):
        """Initialize the adapter.

        Args:
            source: The source async iterable of Ripperdoc messages
            model: The model name to use for AssistantMessage
        """
        self._source = source
        self._model = model

    def __aiter__(self) -> AsyncIterator[Message]:
        """Return self as an async iterator."""
        return self._adapt()

    async def _adapt(self) -> AsyncIterator[Message]:
        """Adapt messages from the source."""
        async for msg in self._source:
            yield MessageAdapter.to_sdk_message(msg, self._model)


# =============================================================================
# ResultMessage Factory
# =============================================================================

class ResultMessageFactory:
    """Factory for creating ResultMessage objects.

    Ripperdoc doesn't have native ResultMessage, so we create them
    at the end of queries for SDK compatibility.
    """

    @staticmethod
    def create(
        session_id: str,
        duration_ms: int,
        duration_api_ms: int = 0,
        is_error: bool = False,
        num_turns: int = 1,
        total_cost_usd: float | None = None,
        usage: dict[str, Any] | None = None,
        result: str | None = None,
    ) -> ResultMessage:
        """Create a ResultMessage.

        Args:
            session_id: The session identifier
            duration_ms: Total duration in milliseconds
            duration_api_ms: API duration in milliseconds
            is_error: Whether an error occurred
            num_turns: Number of conversation turns
            total_cost_usd: Total cost in USD
            usage: Token usage information
            result: Result text

        Returns:
            A ResultMessage instance
        """
        return ResultMessage(
            subtype="result",
            duration_ms=duration_ms,
            duration_api_ms=duration_api_ms,
            is_error=is_error,
            num_turns=num_turns,
            session_id=session_id,
            total_cost_usd=total_cost_usd,
            usage=usage,
            result=result,
        )


__all__ = [
    "MessageAdapter",
    "AsyncMessageAdapter",
    "ResultMessageFactory",
    # Internal types for compatibility
    "InternalMessage",
    "InternalUserMessage",
    "InternalAssistantMessage",
    "InternalProgressMessage",
    "InternalMessageType",
    "MessageContent",
]
