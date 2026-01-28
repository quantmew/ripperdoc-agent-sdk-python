"""Pydantic models for stdio protocol messages.

This module defines type-safe models for all JSON messages exchanged
over the stdio protocol, replacing raw dictionary construction with
validated, self-documenting Pydantic models.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Content Block Models
# ============================================================================

class ContentBlock(BaseModel):
    """Base class for content blocks in messages."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class TextContentBlock(ContentBlock):
    """A text content block."""

    type: Literal["text"] = "text"
    text: str


class ThinkingContentBlock(ContentBlock):
    """A thinking/reasoning content block."""

    type: str = Field(default="thinking")
    thinking: str = Field(alias="text")
    signature: str | None = None


class ToolUseContentBlock(ContentBlock):
    """A tool use content block."""

    type: str = Field(default="tool_use")
    id: str = Field(default="")
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultContentBlock(ContentBlock):
    """A tool result content block."""

    type: str = Field(default="tool_result")
    tool_use_id: str = Field(default="")
    content: str = Field(default="")
    is_error: bool | None = None


class ImageSource(BaseModel):
    """Image source data."""

    type: str = Field(default="base64")
    media_type: str = Field(default="image/jpeg")
    data: str


class ImageContentBlock(ContentBlock):
    """An image content block."""

    type: str = Field(default="image")
    source: ImageSource


# Union type for all content blocks
ContentBlockType = (
    TextContentBlock
    | ThinkingContentBlock
    | ToolUseContentBlock
    | ToolResultContentBlock
    | ImageContentBlock
)


# ============================================================================
# Message Models
# ============================================================================

class MessageData(BaseModel):
    """Base message data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class AssistantMessageData(MessageData):
    """Assistant message data."""

    content: list[dict[str, Any]] | str
    model: str = "main"


class UserMessageData(MessageData):
    """User message data."""

    content: str = ""


class AssistantStreamMessage(BaseModel):
    """An assistant message sent to the SDK."""

    type: str = Field(default="assistant")
    message: AssistantMessageData
    parent_tool_use_id: str | None = None


class UserStreamMessage(BaseModel):
    """A user message sent to the SDK."""

    type: str = Field(default="user")
    message: UserMessageData
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: Any = None


# Union type for stream messages
StreamMessage = AssistantStreamMessage | UserStreamMessage


# ============================================================================
# Control Protocol Request Models (SDK → CLI)
# ============================================================================

class ControlRequestData(BaseModel):
    """Base class for control request data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ControlInitializeRequest(ControlRequestData):
    """Initialize request - sent when SDK connects to CLI."""

    subtype: Literal["initialize"] = "initialize"
    options: dict[str, Any]
    hooks: dict[str, list[dict[str, Any]]] | None = None


class ControlQueryRequest(ControlRequestData):
    """Query request - send a query to the CLI."""

    subtype: Literal["query"] = "query"
    prompt: str
    session_id: str


class ControlPermissionRequest(ControlRequestData):
    """Permission request - ask if a tool can be used."""

    subtype: Literal["can_use_tool"] = "can_use_tool"
    tool_name: str
    input: dict[str, Any]
    permission_suggestions: list[dict[str, Any]] | None = None
    blocked_path: str | None = None


class ControlInterruptRequest(ControlRequestData):
    """Interrupt request - interrupt the current query."""

    subtype: Literal["interrupt"] = "interrupt"


class ControlSetPermissionModeRequest(ControlRequestData):
    """Set permission mode request."""

    subtype: Literal["set_permission_mode"] = "set_permission_mode"
    mode: str


class ControlSetModelRequest(ControlRequestData):
    """Set model request."""

    subtype: Literal["set_model"] = "set_model"
    model: str | None = None


class ControlRewindFilesRequest(ControlRequestData):
    """Rewind files request."""

    subtype: Literal["rewind_files"] = "rewind_files"
    user_message_id: str


class ControlHookCallbackRequest(ControlRequestData):
    """Hook callback request - execute a hook callback."""

    subtype: Literal["hook_callback"] = "hook_callback"
    callback_id: str
    input: dict[str, Any]
    tool_use_id: str | None = None


class ControlMcpMessageRequest(ControlRequestData):
    """MCP message request - send message to MCP server."""

    subtype: Literal["mcp_message"] = "mcp_message"
    server_name: str
    message: dict[str, Any]


class ControlRequestMessage(BaseModel):
    """A control request message wrapper."""

    type: Literal["control_request"] = "control_request"
    request_id: str
    request: (
        ControlInitializeRequest
        | ControlQueryRequest
        | ControlPermissionRequest
        | ControlInterruptRequest
        | ControlSetPermissionModeRequest
        | ControlSetModelRequest
        | ControlRewindFilesRequest
        | ControlHookCallbackRequest
        | ControlMcpMessageRequest
    )


# ============================================================================
# Control Protocol Response Models (CLI → SDK)
# ============================================================================

class ControlResponseData(BaseModel):
    """Base class for control response data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ControlResponseSuccess(ControlResponseData):
    """A successful control response."""

    subtype: Literal["success"] = "success"
    request_id: str
    response: dict[str, Any] | None = None


class ControlResponseError(ControlResponseData):
    """An error control response."""

    subtype: Literal["error"] = "error"
    request_id: str
    error: str


class ControlResponseMessage(BaseModel):
    """A control response message wrapper."""

    type: Literal["control_response"] = "control_response"
    response: ControlResponseSuccess | ControlResponseError


# ============================================================================
# Result/Usage Models
# ============================================================================

class UsageInfo(BaseModel):
    """Token usage information."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0


class MCPServerInfo(BaseModel):
    """MCP server information."""

    name: str


class InitializeResponseData(BaseModel):
    """Response data for initialize request."""

    session_id: str
    system_prompt: str
    tools: list[str]
    mcp_servers: list[MCPServerInfo] = Field(default_factory=list)
    slash_commands: list[Any] = Field(default_factory=list)
    apiKeySource: str = "none"
    claude_code_version: str = "0.1.0"
    output_style: str = "default"
    agents: list[str] = Field(default_factory=list)
    skills: list[Any] = Field(default_factory=list)
    plugins: list[Any] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ResultMessage(BaseModel):
    """A result message sent at the end of a query."""

    type: Literal["result"] = "result"
    subtype: Literal["result"] = "result"
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: UsageInfo | None = None
    result: str | None = None
    structured_output: Any = None


# ============================================================================
# Permission Response Models
# ============================================================================

class PermissionResponseAllow(BaseModel):
    """A permission allow response."""

    decision: Literal["allow"] = "allow"
    updated_input: dict[str, Any] | None = Field(None, alias="updatedInput")


class PermissionResponseDeny(BaseModel):
    """A permission deny response."""

    decision: Literal["deny"] = "deny"
    message: str = ""


class PermissionRuleValue(BaseModel):
    """Permission rule value."""

    tool_name: str = Field(alias="toolName")
    rule_content: str | None = Field(None, alias="ruleContent")


class PermissionUpdate(BaseModel):
    """Permission update configuration."""

    type: Literal[
        "addRules",
        "replaceRules",
        "removeRules",
        "setMode",
        "addDirectories",
        "removeDirectories",
    ]
    destination: Literal[
        "userSettings", "projectSettings", "localSettings", "session"
    ] | None = None
    rules: list[PermissionRuleValue] | None = None
    behavior: Literal["allow", "deny", "ask"] | None = None
    mode: str | None = None
    directories: list[str] | None = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


# ============================================================================
# Hook Models
# ============================================================================

class HookMatcherConfig(BaseModel):
    """Hook matcher configuration for control protocol."""

    matcher: str | None = None
    timeout: float | None = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


# ============================================================================
# Server Info Models
# ============================================================================

class ServerInfo(BaseModel):
    """Server initialization information."""

    commands: list[dict[str, Any]] = Field(default_factory=list)
    output_style: str = "default"
    version: str = "unknown"
    features: list[str] = Field(default_factory=list)


# ============================================================================
# Helper Functions
# ============================================================================

def model_to_dict(model: BaseModel) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON-serializable dictionary.

    This handles exclude_none=True and ensures proper serialization,
    while always including type/subtype fields for protocol messages.

    Args:
        model: The Pydantic model to convert.

    Returns:
        A JSON-serializable dictionary.
    """
    return model.model_dump(exclude_none=True, by_alias=True, mode="json")


__all__ = [
    # Content Blocks
    "ContentBlock",
    "TextContentBlock",
    "ThinkingContentBlock",
    "ToolUseContentBlock",
    "ToolResultContentBlock",
    "ImageContentBlock",
    "ImageSource",
    "ContentBlockType",
    # Messages
    "MessageData",
    "AssistantMessageData",
    "UserMessageData",
    "AssistantStreamMessage",
    "UserStreamMessage",
    "StreamMessage",
    # Control Protocol
    "ControlRequestData",
    "ControlInitializeRequest",
    "ControlQueryRequest",
    "ControlPermissionRequest",
    "ControlInterruptRequest",
    "ControlSetPermissionModeRequest",
    "ControlSetModelRequest",
    "ControlRewindFilesRequest",
    "ControlHookCallbackRequest",
    "ControlMcpMessageRequest",
    "ControlRequestMessage",
    "ControlResponseData",
    "ControlResponseSuccess",
    "ControlResponseError",
    "ControlResponseMessage",
    # Result/Usage
    "UsageInfo",
    "MCPServerInfo",
    "InitializeResponseData",
    "ResultMessage",
    # Permissions
    "PermissionResponseAllow",
    "PermissionResponseDeny",
    "PermissionUpdate",
    "PermissionRuleValue",
    # Hooks
    "HookMatcherConfig",
    # Server Info
    "ServerInfo",
    # Helpers
    "model_to_dict",
]
