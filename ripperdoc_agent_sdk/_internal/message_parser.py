"""Message parser for Ripperdoc SDK subprocess architecture.

This module parses JSON messages from the CLI into typed Message objects.
"""

from typing import Any

from ripperdoc_agent_sdk._errors import MessageParseError
from ripperdoc_agent_sdk.types import (
    AssistantMessage,
    ContentBlock,
    Message,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

class MessageParser:
    """Parser for CLI messages.

    Mirrors claude-agent-sdk parsing behavior.
    """

    def __init__(self) -> None:
        """Initialize the parser."""

    def parse(self, data: dict[str, Any]) -> Message:
        """Parse message from CLI output into typed Message objects.

        Args:
            data: Raw message dictionary from CLI output

        Returns:
            Parsed Message object

        Raises:
            MessageParseError: If parsing fails or message type is unrecognized
        """
        if not isinstance(data, dict):
            raise MessageParseError(
                f"Invalid message data type (expected dict, got {type(data).__name__})",
                data,
            )

        message_type = data.get("type")
        if not message_type:
            raise MessageParseError("Message missing 'type' field", data)

        if message_type == "user":
            return self._parse_user_message(data)
        if message_type == "assistant":
            return self._parse_assistant_message(data)
        if message_type == "system":
            return self._parse_system_message(data)
        if message_type == "result":
            return self._parse_result_message(data)
        if message_type == "stream_event":
            return self._parse_stream_event_message(data)

        raise MessageParseError(f"Unknown message type: {message_type}", data)

    def _parse_user_message(self, data: dict[str, Any]) -> UserMessage:
        """Parse user message from CLI data."""
        try:
            parent_tool_use_id = data.get("parent_tool_use_id")
            tool_use_result = data.get("tool_use_result")
            uuid_value = data.get("uuid")
            content = data["message"]["content"]

            if isinstance(content, list):
                content_blocks: list[ContentBlock] = []
                for block in content:
                    block_type = block.get("type")
                    if block_type == "text":
                        content_blocks.append(TextBlock(text=block.get("text", "")))
                    elif block_type == "tool_use":
                        content_blocks.append(
                            ToolUseBlock(
                                id=block.get("id", ""),
                                name=block.get("name", ""),
                                input=block.get("input", {}) or {},
                            )
                        )
                    elif block_type == "tool_result":
                        result_content = block.get("content")
                        if result_content is None:
                            result_content = ""
                        content_blocks.append(
                            ToolResultBlock(
                                tool_use_id=block.get("tool_use_id", ""),
                                content=result_content,
                                is_error=block.get("is_error"),
                            )
                        )
                return UserMessage(
                    content=content_blocks,
                    uuid=uuid_value,
                    parent_tool_use_id=parent_tool_use_id,
                    tool_use_result=tool_use_result,
                )

            return UserMessage(
                content=content,
                uuid=uuid_value,
                parent_tool_use_id=parent_tool_use_id,
                tool_use_result=tool_use_result,
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in user message: {e}", data
            ) from e

    def _parse_assistant_message(self, data: dict[str, Any]) -> AssistantMessage:
        """Parse assistant message from CLI data."""
        try:
            content_blocks: list[ContentBlock] = []
            for block in data["message"]["content"]:
                block_type = block.get("type")
                if block_type == "text":
                    content_blocks.append(TextBlock(text=block.get("text", "")))
                elif block_type == "thinking":
                    content_blocks.append(
                        ThinkingBlock(
                            thinking=block.get("thinking", ""),
                            signature=block.get("signature"),
                        )
                    )
                elif block_type == "tool_use":
                    content_blocks.append(
                        ToolUseBlock(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            input=block.get("input", {}),
                        )
                    )
                elif block_type == "tool_result":
                    result_content = block.get("content")
                    if result_content is None:
                        result_content = ""
                    content_blocks.append(
                        ToolResultBlock(
                            tool_use_id=block.get("tool_use_id", ""),
                            content=result_content,
                            is_error=block.get("is_error"),
                        )
                    )

            return AssistantMessage(
                content=content_blocks,
                model=data["message"]["model"],
                parent_tool_use_id=data.get("parent_tool_use_id"),
                error=data["message"].get("error"),
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in assistant message: {e}", data
            ) from e

    def _parse_system_message(self, data: dict[str, Any]) -> SystemMessage:
        """Parse system message from CLI data."""
        try:
            return SystemMessage(
                subtype=data["subtype"],
                data=data,
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in system message: {e}", data
            ) from e

    def _parse_result_message(self, data: dict[str, Any]) -> ResultMessage:
        """Parse result message from CLI data."""
        try:
            return ResultMessage(
                subtype=data.get("subtype", "result"),
                duration_ms=data["duration_ms"],
                duration_api_ms=data["duration_api_ms"],
                is_error=data["is_error"],
                num_turns=data["num_turns"],
                session_id=data["session_id"],
                total_cost_usd=data.get("total_cost_usd"),
                usage=data.get("usage"),
                result=data.get("result"),
                structured_output=data.get("structured_output"),
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in result message: {e}", data
            ) from e

    def _parse_stream_event_message(self, data: dict[str, Any]) -> StreamEvent:
        """Parse stream event message from CLI data."""
        try:
            return StreamEvent(
                uuid=data["uuid"],
                session_id=data["session_id"],
                event=data["event"],
                parent_tool_use_id=data.get("parent_tool_use_id"),
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in stream_event message: {e}", data
            ) from e


# Default parser instance for backward compatibility
_default_parser = MessageParser()


def parse_message(data: dict[str, Any]) -> Message:
    """Parse message from CLI output into typed Message objects.

    This is a convenience function that uses the default parser instance.
    For stateful parsing or to avoid shared state, create a MessageParser instance.

    Args:
        data: Raw message dictionary from CLI output

    Returns:
        Parsed Message object

    Raises:
        MessageParseError: If parsing fails or message type is unrecognized
    """
    return _default_parser.parse(data)


__all__ = ["parse_message", "MessageParser"]
