"""Pydantic models for stdio protocol messages.

This module defines type-safe models for all JSON messages exchanged
over the stdio protocol, replacing raw dictionary construction with
validated, self-documenting Pydantic models.

All models extend HybridModel for dataclass-like compatibility.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union
from pydantic import Field, ConfigDict

from ripperdoc_agent_sdk.protocol.base import HybridModel


# ============================================================================
# Content Block Models
# ============================================================================

class ContentBlock(HybridModel):
    """Base class for content blocks in messages."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class TextContentBlock(ContentBlock):
    """A text content block."""

    type: Literal["text"] = "text"
    text: str

    def __repr__(self) -> str:
        """Use TextBlock alias for Claude SDK compatibility."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"TextBlock({', '.join(fields)})"


class ThinkingContentBlock(ContentBlock):
    """A thinking/reasoning content block."""

    type: str = Field(default="thinking")
    thinking: str = Field(alias="text")
    signature: Optional[str] = None

    def __repr__(self) -> str:
        """Use ThinkingBlock alias for Claude SDK compatibility."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"ThinkingBlock({', '.join(fields)})"


class ToolUseContentBlock(ContentBlock):
    """A tool use content block."""

    type: str = Field(default="tool_use")
    id: str = Field(default="")
    name: str
    input: dict[str, Any] = Field(default_factory=dict)

    def __repr__(self) -> str:
        """Use ToolUseBlock alias for Claude SDK compatibility."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"ToolUseBlock({', '.join(fields)})"


class ToolResultContentBlock(ContentBlock):
    """A tool result content block."""

    type: str = Field(default="tool_result")
    tool_use_id: str = Field(default="")
    content: str = Field(default="")
    is_error: Optional[bool] = None

    def __repr__(self) -> str:
        """Use ToolResultBlock alias for Claude SDK compatibility."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"ToolResultBlock({', '.join(fields)})"


class ImageSource(HybridModel):
    """Image source data."""

    type: str = Field(default="base64")
    media_type: str = Field(default="image/jpeg")
    data: str


class ImageContentBlock(ContentBlock):
    """An image content block."""

    type: str = Field(default="image")
    source: ImageSource

    def __repr__(self) -> str:
        """Use ImageBlock alias for Claude SDK compatibility."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"ImageBlock({', '.join(fields)})"


# Union type for all content blocks
ContentBlockType = Union[
    TextContentBlock,
    ThinkingContentBlock,
    ToolUseContentBlock,
    ToolResultContentBlock,
    ImageContentBlock,
]


# ============================================================================
# Message Models
# ============================================================================

class MessageData(HybridModel):
    """Base message data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class AssistantMessageData(MessageData):
    """Assistant message data."""

    content: Union[list[dict[str, Any]], str]
    model: str = "main"


class UserMessageData(MessageData):
    """User message data."""

    content: str = ""


class AssistantStreamMessage(HybridModel):
    """An assistant message sent to the SDK."""

    type: str = Field(default="assistant")
    message: AssistantMessageData
    parent_tool_use_id: Optional[str] = None


class UserStreamMessage(HybridModel):
    """A user message sent to the SDK."""

    type: str = Field(default="user")
    message: UserMessageData
    uuid: Optional[str] = None
    parent_tool_use_id: Optional[str] = None
    tool_use_result: Any = None


# Union type for stream messages
StreamMessage = Union[AssistantStreamMessage, UserStreamMessage]


# ============================================================================
# Control Protocol Request Models (SDK → CLI)
# ============================================================================

class ControlRequestData(HybridModel):
    """Base class for control request data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ControlInitializeRequest(ControlRequestData):
    """Initialize request - sent when SDK connects to CLI."""

    subtype: Literal["initialize"] = "initialize"
    options: dict[str, Any]
    hooks: Optional[dict[str, list[dict[str, Any]]]] = None


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
    permission_suggestions: Optional[list[dict[str, Any]]] = None
    blocked_path: Optional[str] = None


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
    model: Optional[str] = None


class ControlRewindFilesRequest(ControlRequestData):
    """Rewind files request."""

    subtype: Literal["rewind_files"] = "rewind_files"
    user_message_id: str


class ControlHookCallbackRequest(ControlRequestData):
    """Hook callback request - execute a hook callback."""

    subtype: Literal["hook_callback"] = "hook_callback"
    callback_id: str
    input: dict[str, Any]
    tool_use_id: Optional[str] = None


class ControlMcpMessageRequest(ControlRequestData):
    """MCP message request - send message to MCP server."""

    subtype: Literal["mcp_message"] = "mcp_message"
    server_name: str
    message: dict[str, Any]


class ControlRequestMessage(HybridModel):
    """A control request message wrapper."""

    type: Literal["control_request"] = "control_request"
    request_id: str
    request: Union[
        ControlInitializeRequest,
        ControlQueryRequest,
        ControlPermissionRequest,
        ControlInterruptRequest,
        ControlSetPermissionModeRequest,
        ControlSetModelRequest,
        ControlRewindFilesRequest,
        ControlHookCallbackRequest,
        ControlMcpMessageRequest,
    ]


# ============================================================================
# Control Protocol Response Models (CLI → SDK)
# ============================================================================

class ControlResponseData(HybridModel):
    """Base class for control response data."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ControlResponseSuccess(ControlResponseData):
    """A successful control response."""

    subtype: Literal["success"] = "success"
    request_id: str
    response: Optional[dict[str, Any]] = None


class ControlResponseError(ControlResponseData):
    """An error control response."""

    subtype: Literal["error"] = "error"
    request_id: str
    error: str


class ControlResponseMessage(HybridModel):
    """A control response message wrapper."""

    type: Literal["control_response"] = "control_response"
    response: Union[ControlResponseSuccess, ControlResponseError]


# ============================================================================
# Result/Usage Models
# ============================================================================

class UsageInfo(HybridModel):
    """Token usage information."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0


class MCPServerInfo(HybridModel):
    """MCP server information."""

    name: str


class InitializeResponseData(HybridModel):
    """Response data for initialize request."""

    session_id: str
    system_prompt: str
    tools: list[str]
    mcp_servers: list[MCPServerInfo] = Field(default_factory=list)
    slash_commands: list[Any] = Field(default_factory=list)
    apiKeySource: str = "none"
    ripperdoc_version: str = "0.1.0"
    output_style: str = "default"
    agents: list[str] = Field(default_factory=list)
    skills: list[Any] = Field(default_factory=list)
    plugins: list[Any] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class ResultMessage(HybridModel):
    """A result message sent at the end of a query."""

    type: Literal["result"] = "result"
    subtype: Literal["result"] = "result"
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: Optional[float] = None
    usage: Optional[UsageInfo] = None
    result: Optional[str] = None
    structured_output: Any = None


# ============================================================================
# Permission Response Models
# ============================================================================

class PermissionResponseAllow(HybridModel):
    """A permission allow response."""

    decision: Literal["allow"] = "allow"
    updated_input: Optional[dict[str, Any]] = Field(None, alias="updatedInput")


class PermissionResponseDeny(HybridModel):
    """A permission deny response."""

    decision: Literal["deny"] = "deny"
    message: str = ""


class PermissionRuleValue(HybridModel):
    """Permission rule value."""

    tool_name: str = Field(alias="toolName")
    rule_content: Optional[str] = Field(None, alias="ruleContent")


class PermissionUpdate(HybridModel):
    """Permission update configuration."""

    type: Literal[
        "addRules",
        "replaceRules",
        "removeRules",
        "setMode",
        "addDirectories",
        "removeDirectories",
    ]
    destination: Optional[Literal[
        "userSettings", "projectSettings", "localSettings", "session"
    ]] = None
    rules: Optional[list[PermissionRuleValue]] = None
    behavior: Optional[Literal["allow", "deny", "ask"]] = None
    mode: Optional[str] = None
    directories: Optional[list[str]] = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


# ============================================================================
# Hook Models
# ============================================================================

class HookMatcherConfig(HybridModel):
    """Hook matcher configuration for control protocol."""

    matcher: Optional[str] = None
    timeout: Optional[float] = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


# ============================================================================
# Server Info Models
# ============================================================================

class ServerInfo(HybridModel):
    """Server initialization information."""

    commands: list[dict[str, Any]] = Field(default_factory=list)
    output_style: str = "default"
    version: str = "unknown"
    features: list[str] = Field(default_factory=list)


# ============================================================================
# Helper Functions
# ============================================================================

def model_to_dict(model: HybridModel) -> dict[str, Any]:
    """Convert a HybridModel to a JSON-serializable dictionary.

    This handles exclude_none=True and ensures proper serialization,
    while always including type/subtype fields for protocol messages.

    Args:
        model: The HybridModel to convert.

    Returns:
        A JSON-serializable dictionary.
    """
    return model.to_dict(exclude_none=False)


__all__ = [
    # Base
    "HybridModel",
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
