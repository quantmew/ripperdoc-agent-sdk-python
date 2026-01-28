"""Pydantic models for stdio protocol messages.

This module defines type-safe models for all JSON messages exchanged
over the stdio protocol, replacing raw dictionary construction with
validated, self-documenting Pydantic models.
"""

from ripperdoc_agent_sdk.protocol.models import (
    # Content Blocks
    ContentBlock,
    TextContentBlock,
    ThinkingContentBlock,
    ToolUseContentBlock,
    ToolResultContentBlock,
    ImageContentBlock,
    ImageSource,
    ContentBlockType,
    # Messages
    MessageData,
    AssistantMessageData,
    UserMessageData,
    AssistantStreamMessage,
    UserStreamMessage,
    StreamMessage,
    # Control Protocol
    ControlResponseData,
    ControlResponseSuccess,
    ControlResponseError,
    ControlResponseMessage,
    ControlRequestData,
    ControlInitializeRequest,
    ControlQueryRequest,
    ControlPermissionRequest,
    ControlInterruptRequest,
    ControlSetPermissionModeRequest,
    ControlSetModelRequest,
    ControlRewindFilesRequest,
    ControlHookCallbackRequest,
    ControlMcpMessageRequest,
    ControlRequestMessage,
    # Result/Usage
    UsageInfo,
    MCPServerInfo,
    InitializeResponseData,
    ResultMessage,
    # Permissions
    PermissionResponseAllow,
    PermissionResponseDeny,
    PermissionUpdate,
    PermissionRuleValue,
    # Hooks
    HookMatcherConfig,
    # Server Info
    ServerInfo,
    # Helpers
    model_to_dict,
)

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
    "ControlResponseData",
    "ControlResponseSuccess",
    "ControlResponseError",
    "ControlResponseMessage",
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
