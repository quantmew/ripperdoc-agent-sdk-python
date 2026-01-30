"""Message parser for Ripperdoc SDK subprocess architecture.

This module parses JSON messages from the CLI into typed Message objects.
"""

import logging
import uuid
from typing import Any, Optional

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

logger = logging.getLogger(__name__)


class MessageParser:
    """Parser for CLI messages with stateful context.

    This class encapsulates parsing state (like the actual model name from init)
    without using global variables, making it more testable and thread-safe.
    """

    def __init__(self) -> None:
        """Initialize the parser with default state."""
        self._actual_model_name: Optional[str] = None

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

        # Use if-elif instead of match/case for Python 3.9 compatibility
        if message_type == "user":
            return self._parse_user_message(data)
        elif message_type == "assistant":
            return self._parse_assistant_message(data)
        elif message_type == "progress":
            return self._parse_progress_message(data)
        elif message_type == "result":
            return self._parse_result_message(data)
        elif message_type == "system":
            return self._parse_system_message(data)
        elif message_type == "stream_event":
            return self._parse_stream_event_message(data)
        elif message_type == "error":
            return self._parse_error_message(data)
        else:
            raise MessageParseError(f"Unknown message type: {message_type}", data)

    def _parse_user_message(self, data: dict[str, Any]) -> UserMessage:
        """Parse user message from CLI data."""
        parent_tool_use_id = data.get("parent_tool_use_id")
        tool_use_result = data.get("tool_use_result")
        uuid_value = data.get("uuid")

        # Parse content blocks
        content = data.get("message", {}).get("content", "")

        # Build content_blocks list for Claude SDK compatibility
        content_blocks: list[ContentBlock] = []

        # First, parse existing content blocks if any
        if isinstance(content, list):
            for block in content:
                block_type = block.get("type")
                if block_type == "text":
                    content_blocks.append(
                        TextBlock(text=block.get("text", ""))
                    )
                elif block_type == "tool_use":
                    content_blocks.append(
                        ToolUseBlock(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            input=block.get("input", {}) or {},
                        )
                    )
                elif block_type == "tool_result":
                    # Parse existing tool_result block in content
                    tool_result_id = block.get("tool_use_id", "")
                    result_content = block.get("content")
                    result_is_error = block.get("is_error")

                    # If content is None, try to extract from tool_use_result dict
                    if result_content is None and tool_use_result:
                        if isinstance(tool_use_result, dict):
                            # Extract content from tool_use_result dict
                            result_content = tool_use_result.get("content") or tool_use_result.get("result")
                        else:
                            result_content = str(tool_use_result)

                    # Convert None to empty string for SDK compatibility
                    if result_content is None:
                        result_content = ""

                    if result_is_error is None:
                        result_is_error = False

                    content_blocks.append(
                        ToolResultBlock(
                            tool_use_id=tool_result_id,
                            content=result_content,
                            is_error=result_is_error,
                        )
                    )
                else:
                    logger.warning(f"Unknown content block type: {block_type}")
        elif isinstance(content, str) and content:
            # Wrap non-empty string content in TextBlock
            content_blocks.append(TextBlock(text=content))

        # For Claude SDK compatibility: convert tool_use_result dict to ToolResultBlock
        # and add it to content blocks (instead of keeping it as a separate field)
        if tool_use_result and isinstance(tool_use_result, dict):
            # Extract information from tool_use_result
            tool_use_id = tool_use_result.get("tool_use_id") or parent_tool_use_id or ""
            result_content = tool_use_result.get("content") or tool_use_result.get("result")
            result_is_error = tool_use_result.get("is_error")

            # Handle special cases for tool_use_result format
            if result_content is None:
                # Check for error field
                if "error" in tool_use_result:
                    result_content = tool_use_result["error"]
                    result_is_error = True
                else:
                    result_content = str(tool_use_result)

            if result_is_error is None:
                result_is_error = False

            # Create ToolResultBlock and add to content
            content_blocks.append(
                ToolResultBlock(
                    tool_use_id=tool_use_id,
                    content=result_content,
                    is_error=result_is_error,
                )
            )

        # Return UserMessage with content_blocks list (Claude SDK format)
        # If no content blocks, use empty string for backward compatibility
        return UserMessage(
            content=content_blocks if content_blocks else "",
            uuid=uuid_value,
            parent_tool_use_id=parent_tool_use_id,
            tool_use_result=None,  # Cleared for Claude SDK compatibility
        )

    def _parse_assistant_message(self, data: dict[str, Any]) -> AssistantMessage:
        """Parse assistant message from CLI data."""
        content_blocks: list[ContentBlock] = []
        for block in data.get("message", {}).get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                content_blocks.append(
                    TextBlock(text=block.get("text", ""))
                )
            elif block_type == "thinking":
                content_blocks.append(
                    ThinkingBlock(
                        thinking=block.get("thinking", ""),
                        signature=block.get("signature", ""),
                    )
                )
            elif block_type == "tool_use":
                content_blocks.append(
                    ToolUseBlock(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        input=block.get("input", {}) or {},
                    )
                )
            elif block_type == "tool_result":
                # Normalize tool_result block to match SDK behavior
                result_content = block.get("content")
                result_is_error = block.get("is_error")

                # Convert is_error=None to is_error=False for SDK compatibility
                if result_is_error is None:
                    result_is_error = False

                content_blocks.append(
                    ToolResultBlock(
                        tool_use_id=block.get("tool_use_id", ""),
                        content=result_content,
                        is_error=result_is_error,
                    )
                )
            else:
                logger.warning(f"Unknown content block type: {block_type}")

        # Use the actual model name from init message for Claude SDK compatibility
        # If the message contains a model field, use it; otherwise use the stored model name
        message_model = data.get("message", {}).get("model", "")
        if not message_model or message_model == "main":
            message_model = self._actual_model_name or "glm-4.7"

        return AssistantMessage(
            content=content_blocks,
            model=message_model,
            parent_tool_use_id=data.get("parent_tool_use_id"),
            error=data.get("message", {}).get("error"),
        )

    def _parse_progress_message(self, data: dict[str, Any]) -> SystemMessage:
        """Parse progress message from CLI data."""
        return SystemMessage(
            subtype="progress",
            data={
                "tool_use_id": data.get("tool_use_id", ""),
                "content": data.get("content"),
            },
        )

    def _parse_result_message(self, data: dict[str, Any]) -> ResultMessage:
        """Parse result message from CLI data."""
        return ResultMessage(
            subtype=data.get("subtype", "result"),
            duration_ms=data.get("duration_ms", 0),
            duration_api_ms=data.get("duration_api_ms", 0),
            is_error=data.get("is_error", False),
            num_turns=data.get("num_turns", 0),
            session_id=data.get("session_id", ""),
            total_cost_usd=data.get("total_cost_usd"),
            usage=data.get("usage"),
            result=data.get("result"),
            structured_output=data.get("structured_output"),
        )

    def _parse_system_message(self, data: dict[str, Any]) -> SystemMessage:
        """Parse system message from CLI data."""
        subtype = data.get("subtype", "")
        # Normalize init message data for SDK compatibility
        if subtype == "init":
            normalized_data = self._normalize_init_message(data)
            return SystemMessage(
                subtype=subtype,
                data=normalized_data,
            )
        return SystemMessage(
            subtype=subtype,
            data=data,
        )

    def _parse_stream_event_message(self, data: dict[str, Any]) -> StreamEvent:
        """Parse stream event message from CLI data."""
        return StreamEvent(
            uuid=data["uuid"],
            session_id=data["session_id"],
            event=data["event"],
            parent_tool_use_id=data.get("parent_tool_use_id"),
        )

    def _parse_error_message(self, data: dict[str, Any]) -> SystemMessage:
        """Parse error message from CLI data."""
        error_text = data.get("error", "Unknown error")
        return SystemMessage(
            subtype="error",
            data={
                "error": error_text,
                "exit_code": data.get("exit_code"),
            },
        )

    def _normalize_init_message(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize init message data for SDK compatibility.

        This function normalizes Ripperdoc's init message format to match
        SDK's expected format:

        - model: Store actual model name for Claude SDK compatibility
        - agents: Ensure agents list includes default agents if empty
        - slash_commands: Add default slash commands if empty

        Args:
            data: Raw init message data from CLI (contains nested data field)

        Returns:
            Normalized init message data
        """
        # The input data has nested structure: {type, subtype, data: {...}}
        # We need to extract and normalize the inner data dict
        inner_data = data.get("data", {})
        if not isinstance(inner_data, dict):
            inner_data = {}

        # Create a copy of inner data to modify
        normalized = dict(inner_data)

        # Store the actual model name for Claude SDK compatibility
        # The 'model' field in init message contains the actual model name
        self._actual_model_name = normalized.get("model", "main")
        # Ensure we have a valid model name (not "main" placeholder)
        if self._actual_model_name == "main":
            self._actual_model_name = "glm-4.7"  # Default fallback for Claude SDK compatibility

        # Update the model field in normalized data to the actual model name
        normalized["model"] = self._actual_model_name

        # Normalize agents field - add default agents if empty to match SDK
        agents = normalized.get("agents", [])
        if not agents:
            # Add default agent types that SDK typically provides
            normalized["agents"] = ["Bash", "general-purpose", "Explore", "Plan"]

        # Normalize slash_commands field - add default commands if empty
        slash_commands = normalized.get("slash_commands", [])
        if not slash_commands:
            # Add common slash commands for SDK compatibility
            normalized["slash_commands"] = [
                "compact", "context", "cost", "init", "pr-comments",
                "release-notes", "review", "security-review"
            ]

        # Return the normalized data, preserving other fields from original
        return normalized


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


def _normalize_init_message(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize init message data for SDK compatibility.

    This function normalizes Ripperdoc's init message format to match
    SDK's expected format:

    - model: Store actual model name for Claude SDK compatibility
    - agents: Ensure agents list includes default agents if empty
    - slash_commands: Add default slash commands if empty

    Args:
        data: Raw init message data from CLI (contains nested data field)

    Returns:
        Normalized init message data
    """
    global _actual_model_name

    # The input data has nested structure: {type, subtype, data: {...}}
    # We need to extract and normalize the inner data dict
    inner_data = data.get("data", {})
    if not isinstance(inner_data, dict):
        inner_data = {}

    # Create a copy of inner data to modify
    normalized = dict(inner_data)

    # Store the actual model name for Claude SDK compatibility
    # The 'model' field in init message contains the actual model name
    _actual_model_name = normalized.get("model", "main")
    # Ensure we have a valid model name (not "main" placeholder)
    if _actual_model_name == "main":
        _actual_model_name = "glm-4.7"  # Default fallback for Claude SDK compatibility

    # Update the model field in normalized data to the actual model name
    normalized["model"] = _actual_model_name

    # Normalize agents field - add default agents if empty to match SDK
    agents = normalized.get("agents", [])
    if not agents:
        # Add default agent types that SDK typically provides
        normalized["agents"] = ["Bash", "general-purpose", "Explore", "Plan"]

    # Normalize slash_commands field - add default commands if empty
    slash_commands = normalized.get("slash_commands", [])
    if not slash_commands:
        # Add common slash commands for SDK compatibility
        normalized["slash_commands"] = [
            "compact", "context", "cost", "init", "pr-comments",
            "release-notes", "review", "security-review"
        ]

    # Return the normalized data, preserving other fields from original
    # The original data dict at top level contains type, subtype, etc.
    # We return the normalized inner data as the new data field
    return normalized


def parse_message(data: dict[str, Any]) -> Message:
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

    # Use if-elif instead of match/case for Python 3.9 compatibility
    if message_type == "user":
        try:
            parent_tool_use_id = data.get("parent_tool_use_id")
            tool_use_result = data.get("tool_use_result")
            uuid = data.get("uuid")

            # Parse content blocks
            content = data.get("message", {}).get("content", "")

            # Build content_blocks list for Claude SDK compatibility
            content_blocks: list[ContentBlock] = []

            # First, parse existing content blocks if any
            if isinstance(content, list):
                for block in content:
                    block_type = block.get("type")
                    if block_type == "text":
                        content_blocks.append(
                            TextBlock(text=block.get("text", ""))
                        )
                    elif block_type == "tool_use":
                        content_blocks.append(
                            ToolUseBlock(
                                id=block.get("id", ""),
                                name=block.get("name", ""),
                                input=block.get("input", {}) or {},
                            )
                        )
                    elif block_type == "tool_result":
                        # Parse existing tool_result block in content
                        tool_result_id = block.get("tool_use_id", "")
                        result_content = block.get("content")
                        result_is_error = block.get("is_error")

                        # If content is None, try to extract from tool_use_result dict
                        if result_content is None and tool_use_result:
                            if isinstance(tool_use_result, dict):
                                # Extract content from tool_use_result dict
                                result_content = tool_use_result.get("content") or tool_use_result.get("result")
                            else:
                                result_content = str(tool_use_result)

                        # Convert None to empty string for SDK compatibility
                        if result_content is None:
                            result_content = ""

                        if result_is_error is None:
                            result_is_error = False

                        content_blocks.append(
                            ToolResultBlock(
                                tool_use_id=tool_result_id,
                                content=result_content,
                                is_error=result_is_error,
                            )
                        )
                    else:
                        logger.warning(f"Unknown content block type: {block_type}")
            elif isinstance(content, str) and content:
                # Wrap non-empty string content in TextBlock
                content_blocks.append(TextBlock(text=content))

            # For Claude SDK compatibility: convert tool_use_result dict to ToolResultBlock
            # and add it to content blocks (instead of keeping it as a separate field)
            if tool_use_result and isinstance(tool_use_result, dict):
                # Extract information from tool_use_result
                tool_use_id = tool_use_result.get("tool_use_id") or parent_tool_use_id or ""
                result_content = tool_use_result.get("content") or tool_use_result.get("result")
                result_is_error = tool_use_result.get("is_error")

                # Handle special cases for tool_use_result format
                if result_content is None:
                    # Check for error field
                    if "error" in tool_use_result:
                        result_content = tool_use_result["error"]
                        result_is_error = True
                    else:
                        result_content = str(tool_use_result)

                if result_is_error is None:
                    result_is_error = False

                # Create ToolResultBlock and add to content
                content_blocks.append(
                    ToolResultBlock(
                        tool_use_id=tool_use_id,
                        content=result_content,
                        is_error=result_is_error,
                    )
                )

            # Return UserMessage with content_blocks list (Claude SDK format)
            # If no content blocks, use empty string for backward compatibility
            return UserMessage(
                content=content_blocks if content_blocks else "",
                uuid=uuid,
                parent_tool_use_id=parent_tool_use_id,
                tool_use_result=None,  # Cleared for Claude SDK compatibility
            )

        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in user message: {e}", data
            ) from e

    elif message_type == "assistant":
        try:
            content_blocks: list[ContentBlock] = []
            for block in data.get("message", {}).get("content", []):
                block_type = block.get("type")
                if block_type == "text":
                    content_blocks.append(
                        TextBlock(text=block.get("text", ""))
                    )
                elif block_type == "thinking":
                    content_blocks.append(
                        ThinkingBlock(
                            thinking=block.get("thinking", ""),
                            signature=block.get("signature", ""),
                        )
                    )
                elif block_type == "tool_use":
                    content_blocks.append(
                        ToolUseBlock(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            input=block.get("input", {}) or {},
                        )
                    )
                elif block_type == "tool_result":
                    # Normalize tool_result block to match SDK behavior
                    result_content = block.get("content")
                    result_is_error = block.get("is_error")

                    # Convert is_error=None to is_error=False for SDK compatibility
                    if result_is_error is None:
                        result_is_error = False

                    content_blocks.append(
                        ToolResultBlock(
                            tool_use_id=block.get("tool_use_id", ""),
                            content=result_content,
                            is_error=result_is_error,
                        )
                    )
                else:
                    logger.warning(f"Unknown content block type: {block_type}")

            # Use the actual model name from init message for Claude SDK compatibility
            # If the message contains a model field, use it; otherwise use the stored model name
            message_model = data.get("message", {}).get("model", "")
            if not message_model or message_model == "main":
                message_model = _actual_model_name or "glm-4.7"

            return AssistantMessage(
                content=content_blocks,
                model=message_model,
                parent_tool_use_id=data.get("parent_tool_use_id"),
                error=data.get("message", {}).get("error"),
            )

        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in assistant message: {e}", data
            ) from e

    elif message_type == "progress":
        # Progress messages
        return SystemMessage(
            subtype="progress",
            data={
                "tool_use_id": data.get("tool_use_id", ""),
                "content": data.get("content"),
            },
        )

    elif message_type == "result":
        try:
            return ResultMessage(
                subtype=data.get("subtype", "result"),
                duration_ms=data.get("duration_ms", 0),
                duration_api_ms=data.get("duration_api_ms", 0),
                is_error=data.get("is_error", False),
                num_turns=data.get("num_turns", 0),
                session_id=data.get("session_id", ""),
                total_cost_usd=data.get("total_cost_usd"),
                usage=data.get("usage"),
                result=data.get("result"),
                structured_output=data.get("structured_output"),
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in result message: {e}", data
            ) from e

    elif message_type == "system":
        try:
            subtype = data.get("subtype", "")
            # Normalize init message data for SDK compatibility
            if subtype == "init":
                normalized_data = _normalize_init_message(data)
                return SystemMessage(
                    subtype=subtype,
                    data=normalized_data,
                )
            return SystemMessage(
                subtype=subtype,
                data=data,
            )
        except KeyError as e:
            raise MessageParseError(
                f"Missing required field in system message: {e}", data
            ) from e

    elif message_type == "stream_event":
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

    elif message_type == "error":
        # Error message from the CLI
        error_text = data.get("error", "Unknown error")
        return SystemMessage(
            subtype="error",
            data={
                "error": error_text,
                "exit_code": data.get("exit_code"),
            },
        )

    else:
        raise MessageParseError(f"Unknown message type: {message_type}", data)


__all__ = ["parse_message"]
