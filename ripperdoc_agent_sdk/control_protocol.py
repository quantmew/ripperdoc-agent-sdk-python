"""JSON Control Protocol types for subprocess communication.

This module defines the message types used for communication between
the SDK and the CLI subprocess over stdio.

This module now re-exports types from the protocol module for backward
compatibility. New code should import directly from ripperdoc_agent_sdk.protocol.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict, Union

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

# Import Pydantic models from protocol module
from ripperdoc_agent_sdk.protocol import (
    ControlInitializeRequest as _ControlInitializeRequest,
    ControlQueryRequest as _ControlQueryRequest,
    ControlPermissionRequest as _ControlPermissionRequest,
    ControlInterruptRequest as _ControlInterruptRequest,
    ControlSetPermissionModeRequest as _ControlSetPermissionModeRequest,
    ControlSetModelRequest as _ControlSetModelRequest,
    ControlRewindFilesRequest as _ControlRewindFilesRequest,
    ControlHookCallbackRequest as _ControlHookCallbackRequest,
    ControlMcpMessageRequest as _ControlMcpMessageRequest,
    ControlResponseSuccess as _ControlResponseSuccess,
    ControlResponseError as _ControlResponseError,
    ResultMessage as _ProtocolResultMessage,
    PermissionUpdate as _ProtocolPermissionUpdate,
    PermissionRuleValue as _ProtocolPermissionRuleValue,
    HookMatcherConfig as _ProtocolHookMatcherConfig,
    ServerInfo as _ProtocolServerInfo,
    model_to_dict,
)


# =============================================================================
# Backward Compatibility: Re-export Pydantic models
# =============================================================================

# Control Request Types (SDK → CLI) - Re-export Pydantic models
SDKControlInitializeRequest = _ControlInitializeRequest
SDKControlQueryRequest = _ControlQueryRequest
SDKControlPermissionRequest = _ControlPermissionRequest
SDKControlInterruptRequest = _ControlInterruptRequest
SDKControlSetPermissionModeRequest = _ControlSetPermissionModeRequest
SDKControlSetModelRequest = _ControlSetModelRequest
SDKControlRewindFilesRequest = _ControlRewindFilesRequest
SDKHookCallbackRequest = _ControlHookCallbackRequest
SDKControlMcpMessageRequest = _ControlMcpMessageRequest

# Control Response Types (CLI → SDK) - Re-export Pydantic models
ControlResponseSuccess = _ControlResponseSuccess
ControlResponseError = _ControlResponseError
ControlResponse = Union[_ControlResponseSuccess, _ControlResponseError]

# Permission and Hook types - Re-export Pydantic models
PermissionUpdate = _ProtocolPermissionUpdate
PermissionRuleValue = _ProtocolPermissionRuleValue
HookMatcherConfig = _ProtocolHookMatcherConfig
ServerInfo = _ProtocolServerInfo


# =============================================================================
# Stream Message Types (CLI → SDK) - Keep as TypedDict for backward compatibility
# These are used for parsing incoming messages from CLI
# =============================================================================

class StreamUserMessage(TypedDict):
    """User message from CLI."""
    type: Literal["user"]
    message: dict[str, Any]
    uuid: NotRequired[str]
    parent_tool_use_id: NotRequired[str]
    tool_use_result: NotRequired[dict[str, Any]]
    session_id: str


class StreamAssistantMessage(TypedDict):
    """Assistant message from CLI."""
    type: Literal["assistant"]
    message: dict[str, Any]
    model: str
    parent_tool_use_id: NotRequired[str]
    error: NotRequired[str]
    session_id: str


class StreamProgressMessage(TypedDict):
    """Progress message from CLI."""
    type: Literal["progress"]
    tool_use_id: str
    content: Any
    session_id: str


class StreamResultMessage(TypedDict):
    """Result message from CLI."""
    type: Literal["result"]
    subtype: Literal["result"]
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: NotRequired[float]
    usage: NotRequired[dict[str, Any]]
    result: NotRequired[str]


class StreamSystemMessage(TypedDict):
    """System message from CLI."""
    type: Literal["system"]
    subtype: str
    data: dict[str, Any]


class StreamErrorMessage(TypedDict):
    """Error message from CLI."""
    type: Literal["error"]
    error: str


# Union of all stream message types
StreamMessage = Union[
    StreamUserMessage,
    StreamAssistantMessage,
    StreamProgressMessage,
    StreamResultMessage,
    StreamSystemMessage,
    StreamErrorMessage,
]


# =============================================================================
# Legacy TypedDict aliases for backward compatibility
# These are deprecated in favor of Pydantic models
# =============================================================================

class _SDKControlInitializeRequest(TypedDict):
    """Initialize request - sent when SDK connects to CLI (DEPRECATED - use Pydantic model)."""
    subtype: Literal["initialize"]
    options: dict[str, Any]
    hooks: Optional[dict[str, list[dict[str, Any]]]]


class _SDKControlQueryRequest(TypedDict):
    """Query request - send a query to the CLI (DEPRECATED - use Pydantic model)."""
    subtype: Literal["query"]
    prompt: str
    session_id: str


class _SDKControlPermissionRequest(TypedDict):
    """Permission request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["can_use_tool"]
    tool_name: str
    input: dict[str, Any]
    permission_suggestions: Optional[list[dict[str, Any]]]
    blocked_path: Optional[str]


class _SDKControlInterruptRequest(TypedDict):
    """Interrupt request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["interrupt"]


class _SDKControlSetPermissionModeRequest(TypedDict):
    """Set permission mode request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["set_permission_mode"]
    mode: str


class _SDKControlSetModelRequest(TypedDict):
    """Set model request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["set_model"]
    model: Optional[str]


class _SDKControlRewindFilesRequest(TypedDict):
    """Rewind files request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["rewind_files"]
    user_message_id: str


class _SDKHookCallbackRequest(TypedDict):
    """Hook callback request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["hook_callback"]
    callback_id: str
    input: dict[str, Any]
    tool_use_id: Optional[str]


class _SDKControlMcpMessageRequest(TypedDict):
    """MCP message request (DEPRECATED - use Pydantic model)."""
    subtype: Literal["mcp_message"]
    server_name: str
    message: dict[str, Any]


# Union of all control request types (for type checking)
SDKControlRequest = TypedDict(
    "SDKControlRequest",
    {
        "type": Literal["control_request"],
        "request_id": str,
        "request": Union[
            _SDKControlInitializeRequest,
            _SDKControlQueryRequest,
            _SDKControlPermissionRequest,
            _SDKControlInterruptRequest,
            _SDKControlSetPermissionModeRequest,
            _SDKControlSetModelRequest,
            _SDKControlRewindFilesRequest,
            _SDKHookCallbackRequest,
            _SDKControlMcpMessageRequest,
        ],
    },
)


class SDKControlResponse(TypedDict):
    """Control response wrapper (DEPRECATED - use Pydantic model)."""
    type: Literal["control_response"]
    response: ControlResponse


__all__ = [
    # Control Requests (Pydantic models)
    "SDKControlRequest",
    "SDKControlInitializeRequest",
    "SDKControlQueryRequest",
    "SDKControlPermissionRequest",
    "SDKControlInterruptRequest",
    "SDKControlSetPermissionModeRequest",
    "SDKControlSetModelRequest",
    "SDKControlRewindFilesRequest",
    "SDKHookCallbackRequest",
    "SDKControlMcpMessageRequest",
    # Control Responses (Pydantic models)
    "SDKControlResponse",
    "ControlResponse",
    "ControlResponseSuccess",
    "ControlResponseError",
    # Stream Messages (TypedDict)
    "StreamMessage",
    "StreamUserMessage",
    "StreamAssistantMessage",
    "StreamProgressMessage",
    "StreamResultMessage",
    "StreamSystemMessage",
    "StreamErrorMessage",
    # Permission
    "PermissionUpdate",
    "PermissionRuleValue",
    # Hooks
    "HookMatcherConfig",
    # Server Info
    "ServerInfo",
]
