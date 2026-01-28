"""Message parser for Ripperdoc SDK subprocess architecture.

This module parses JSON messages from the CLI into typed Message objects.
It uses Python's match/case for clean pattern matching.
"""

import logging
import uuid
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

logger = logging.getLogger(__name__)


def _normalize_init_message(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize init message data for SDK compatibility.

    This function normalizes Ripperdoc's init message format to match
    SDK's expected format:

    - model: Keep "main" pointer (model resolution happens elsewhere)
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

    Uses Python's match/case for clean pattern matching.

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

    match message_type:
        case "user":
            try:
                parent_tool_use_id = data.get("parent_tool_use_id")
                tool_use_result = data.get("tool_use_result")
                uuid = data.get("uuid")

                # Parse content blocks
                content = data.get("message", {}).get("content", "")
                if isinstance(content, list):
                    content_blocks: list[ContentBlock] = []
                    for block in content:
                        block_type = block.get("type")
                        match block_type:
                            case "text":
                                content_blocks.append(
                                    TextBlock(text=block.get("text", ""))
                                )
                            case "tool_use":
                                content_blocks.append(
                                    ToolUseBlock(
                                        id=block.get("id", ""),
                                        name=block.get("name", ""),
                                        input=block.get("input", {}) or {},
                                    )
                                )
                            case "tool_result":
                                # Normalize tool_result block to match SDK behavior:
                                # - content should contain the actual content (not None)
                                # - is_error should be a boolean (not None)
                                tool_result_block = block
                                tool_result_id = tool_result_block.get("tool_use_id", "")
                                result_content = tool_result_block.get("content")
                                result_is_error = tool_result_block.get("is_error")

                                # If content is None, try to extract from tool_use_result dict
                                if result_content is None and tool_use_result:
                                    if isinstance(tool_use_result, dict):
                                        # Extract content from tool_use_result dict
                                        result_content = tool_use_result.get("content") or tool_use_result.get("result")
                                    else:
                                        result_content = str(tool_use_result)

                                # Convert is_error=None to is_error=False for SDK compatibility
                                if result_is_error is None:
                                    result_is_error = False

                                content_blocks.append(
                                    ToolResultBlock(
                                        tool_use_id=tool_result_id,
                                        content=result_content,
                                        is_error=result_is_error,
                                    )
                                )
                            case _:
                                logger.warning(f"Unknown content block type: {block_type}")

                    return UserMessage(
                        content=content_blocks if content_blocks else content,
                        uuid=uuid,
                        parent_tool_use_id=parent_tool_use_id,
                        tool_use_result=tool_use_result,
                    )
                else:
                    # String content
                    return UserMessage(
                        content=content,
                        uuid=uuid,
                        parent_tool_use_id=parent_tool_use_id,
                        tool_use_result=tool_use_result,
                    )

            except KeyError as e:
                raise MessageParseError(
                    f"Missing required field in user message: {e}", data
                ) from e

        case "assistant":
            try:
                content_blocks: list[ContentBlock] = []
                for block in data.get("message", {}).get("content", []):
                    block_type = block.get("type")
                    match block_type:
                        case "text":
                            content_blocks.append(
                                TextBlock(text=block.get("text", ""))
                            )
                        case "thinking":
                            content_blocks.append(
                                ThinkingBlock(
                                    thinking=block.get("thinking", ""),
                                    signature=block.get("signature", ""),
                                )
                            )
                        case "tool_use":
                            content_blocks.append(
                                ToolUseBlock(
                                    id=block.get("id", ""),
                                    name=block.get("name", ""),
                                    input=block.get("input", {}) or {},
                                )
                            )
                        case "tool_result":
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
                        case _:
                            logger.warning(f"Unknown content block type: {block_type}")

                return AssistantMessage(
                    content=content_blocks,
                    model=data.get("message", {}).get("model", ""),
                    parent_tool_use_id=data.get("parent_tool_use_id"),
                    error=data.get("message", {}).get("error"),
                )

            except KeyError as e:
                raise MessageParseError(
                    f"Missing required field in assistant message: {e}", data
                ) from e

        case "progress":
            # Progress messages
            return SystemMessage(
                subtype="progress",
                data={
                    "tool_use_id": data.get("tool_use_id", ""),
                    "content": data.get("content"),
                },
            )

        case "result":
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

        case "system":
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

        case "stream_event":
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

        case "error":
            # Error message from the CLI
            error_text = data.get("error", "Unknown error")
            return SystemMessage(
                subtype="error",
                data={
                    "error": error_text,
                    "exit_code": data.get("exit_code"),
                },
            )

        case _:
            raise MessageParseError(f"Unknown message type: {message_type}", data)


__all__ = ["parse_message"]
