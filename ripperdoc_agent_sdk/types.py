"""SDK compatible type definitions for Ripperdoc.

This module provides a unified type system that uses Pydantic models from
the protocol module for validation and consistency, while maintaining
backward compatibility through type aliases.

Migration Notes:
- ContentBlock types are now Pydantic models (HybridModel) with dataclass-like API
- ResultMessage is now a Pydantic model with .to_dict() method
- Permission types use Pydantic models from protocol module
- Old dataclass patterns still work through backward compatibility
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, Callable, Awaitable
from dataclasses import dataclass, field
from typing import (
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

# =============================================================================
# Import Pydantic Models from Protocol Module
# =============================================================================

from ripperdoc_agent_sdk.protocol import (
    # Base
    HybridModel,
    # Content Blocks (Pydantic models)
    TextContentBlock,
    ThinkingContentBlock,
    ToolUseContentBlock,
    ToolResultContentBlock,
    ImageContentBlock,
    ImageSource,
    ContentBlockType,
    # Messages (Pydantic models)
    AssistantStreamMessage,
    UserStreamMessage,
    StreamMessage,
    # Result/Usage (Pydantic models)
    UsageInfo,
    ResultMessage,
    # Permissions (Pydantic models)
    PermissionResponseAllow,
    PermissionResponseDeny,
    PermissionUpdate,
    PermissionRuleValue,
    # Hooks (Pydantic models)
    HookMatcherConfig,
    # Control protocol (Pydantic models)
    ControlResponseSuccess,
    ControlResponseError,
    # Helpers
    model_to_dict,
)
from ripperdoc_agent_sdk.config import (
    PermissionMode as ConfigPermissionMode,
    PermissionUpdateDestination as ConfigPermissionUpdateDestination,
    PermissionBehavior as ConfigPermissionBehavior,
    HookEvent as ConfigHookEvent,
    SettingSource as ConfigSettingSource,
    McpConfig,
    SdkBeta as ConfigSdkBeta,
)

# =============================================================================
# Content Block Type Aliases (Backward Compatible)
# =============================================================================

# Re-export content blocks with friendly names
TextBlock = TextContentBlock
ThinkingBlock = ThinkingContentBlock
ToolUseBlock = ToolUseContentBlock
ToolResultBlock = ToolResultContentBlock
ImageBlock = ImageContentBlock

# Union type for all content blocks
ContentBlock = ContentBlockType


# =============================================================================
# Message Types
# =============================================================================

@dataclass
class UserMessage:
    """User message with optional tool results.

    This provides a dataclass-like interface for backward compatibility.
    New code should use UserStreamMessage directly from the protocol module.
    """

    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: dict[str, Any] | None = None


@dataclass
class AssistantMessage:
    """Assistant message with content blocks.

    This provides a dataclass-like interface for backward compatibility.
    New code should use AssistantStreamMessage directly from the protocol module.
    """

    content: list[ContentBlock]
    model: str
    parent_tool_use_id: str | None = None
    error: str | None = None


@dataclass
class SystemMessage:
    """System message with metadata.

    Contains system-level information and events.
    This remains a dataclass as it's SDK-specific.
    """

    subtype: str
    data: dict[str, Any]


@dataclass
class StreamEvent:
    """Stream event for partial message updates during streaming.

    Contains raw stream events from the underlying API for advanced use cases.
    This remains a dataclass as it's SDK-specific.
    """

    uuid: str
    session_id: str
    event: dict[str, Any]
    parent_tool_use_id: str | None = None


# Union type for all message types
Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage | StreamEvent


# =============================================================================
# Permission System Types
# =============================================================================

# Permission mode literal type - re-export from config
PermissionMode = ConfigPermissionMode

# Permission update destination - re-export from config
PermissionUpdateDestination = Literal[
    ConfigPermissionUpdateDestination.USER_SETTINGS,
    ConfigPermissionUpdateDestination.PROJECT_SETTINGS,
    ConfigPermissionUpdateDestination.LOCAL_SETTINGS,
    ConfigPermissionUpdateDestination.SESSION,
]

# Permission behavior - re-export from config
PermissionBehavior = Literal[
    ConfigPermissionBehavior.ALLOW,
    ConfigPermissionBehavior.DENY,
    ConfigPermissionBehavior.ASK,
]


@dataclass
class ToolPermissionContext:
    """Context information for tool permission callbacks.

    Provides additional context when making permission decisions.
    """

    signal: Any | None = None
    suggestions: list[PermissionUpdate] = field(default_factory=list)


# Permission results - using protocol models with backward compatible aliases
PermissionResultAllow = PermissionResponseAllow
PermissionResultDeny = PermissionResponseDeny
PermissionResult = PermissionResponseAllow | PermissionResponseDeny

# Tool permission callback type
CanUseTool = Callable[
    [str, dict[str, Any], ToolPermissionContext],
    Awaitable[PermissionResult],
]


# =============================================================================
# Hook System Types
# =============================================================================

# Hook event types - re-export from config
HookEvent = (
    Literal[ConfigHookEvent.PRE_TOOL_USE]
    | Literal[ConfigHookEvent.POST_TOOL_USE]
    | Literal[ConfigHookEvent.USER_PROMPT_SUBMIT]
    | Literal[ConfigHookEvent.STOP]
    | Literal[ConfigHookEvent.SUBAGENT_STOP]
    | Literal[ConfigHookEvent.PRE_COMPACT]
)


# Base hook input fields
class BaseHookInput(TypedDict, total=False):
    """Base hook input fields present across many hook events."""

    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: str


# Specific hook input types
class PreToolUseHookInput(BaseHookInput):
    """Input data for PreToolUse hook events."""

    hook_event_name: Literal["PreToolUse"]
    tool_name: str
    tool_input: dict[str, Any]


class PostToolUseHookInput(BaseHookInput):
    """Input data for PostToolUse hook events."""

    hook_event_name: Literal["PostToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: Any


class UserPromptSubmitHookInput(BaseHookInput):
    """Input data for UserPromptSubmit hook events."""

    hook_event_name: Literal["UserPromptSubmit"]
    prompt: str


class StopHookInput(BaseHookInput):
    """Input data for Stop hook events."""

    hook_event_name: Literal["Stop"]
    stop_hook_active: bool


class SubagentStopHookInput(BaseHookInput):
    """Input data for SubagentStop hook events."""

    hook_event_name: Literal["SubagentStop"]
    stop_hook_active: bool


class PreCompactHookInput(BaseHookInput):
    """Input data for PreCompact hook events."""

    hook_event_name: Literal["PreCompact"]
    trigger: Literal["manual", "auto"]
    custom_instructions: str | None


# Union type for all hook inputs
HookInput = (
    PreToolUseHookInput
    | PostToolUseHookInput
    | UserPromptSubmitHookInput
    | StopHookInput
    | SubagentStopHookInput
    | PreCompactHookInput
)


# Hook-specific output types
class PreToolUseHookSpecificOutput(TypedDict):
    """Hook-specific output for PreToolUse events."""

    hookEventName: Literal["PreToolUse"]
    permissionDecision: NotRequired[Literal["allow", "deny", "ask"]]
    permissionDecisionReason: NotRequired[str]
    updatedInput: NotRequired[dict[str, Any]]


class PostToolUseHookSpecificOutput(TypedDict):
    """Hook-specific output for PostToolUse events."""

    hookEventName: Literal["PostToolUse"]
    additionalContext: NotRequired[str]


class UserPromptSubmitHookSpecificOutput(TypedDict):
    """Hook-specific output for UserPromptSubmit events."""

    hookEventName: Literal["UserPromptSubmit"]
    additionalContext: NotRequired[str]


HookSpecificOutput = (
    PreToolUseHookSpecificOutput
    | PostToolUseHookSpecificOutput
    | UserPromptSubmitHookSpecificOutput
)


# Hook JSON output types
class AsyncHookJSONOutput(TypedDict):
    """Async hook output that defers hook execution.

    Note: async_ is used instead of async to avoid Python keyword conflict.
    """

    async_: Literal[True]
    asyncTimeout: NotRequired[int]


class SyncHookJSONOutput(TypedDict):
    """Synchronous hook output with control and decision fields.

    Note: continue_ is used instead of continue to avoid Python keyword conflict.
    """

    continue_: NotRequired[bool]
    suppressOutput: NotRequired[bool]
    stopReason: NotRequired[str]
    decision: NotRequired[Literal["block"]]
    systemMessage: NotRequired[str]
    reason: NotRequired[str]
    hookSpecificOutput: NotRequired[HookSpecificOutput]


HookJSONOutput = AsyncHookJSONOutput | SyncHookJSONOutput


class HookContext(TypedDict):
    """Context information for hook callbacks."""

    signal: Any | None


# Hook callback type
HookCallback = Callable[
    [HookInput, str | None, HookContext],
    Awaitable[HookJSONOutput],
]


# Hook matcher - using protocol model with backward compatibility
HookMatcher = HookMatcherConfig


# =============================================================================
# Agent Definition Types
# =============================================================================

@dataclass
class AgentDefinition:
    """Agent definition configuration.

    Defines a subagent with its own system prompt and available tools.
    """

    description: str
    prompt: str
    tools: list[str] | None = None
    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None


# Setting source literal type - re-export from config
SettingSource = ConfigSettingSource


# =============================================================================
# SDK MCP Server Types (In-Process Tools)
# =============================================================================

from typing import Generic as TypingGeneric, TypeVar

T = TypeVar("T")


@dataclass
class SdkMcpTool(TypingGeneric[T]):
    """Definition for an SDK MCP tool.

    An SDK MCP tool runs in-process within the Python application,
    providing better performance than external MCP servers.

    Attributes:
        name: Unique identifier for the tool (what Claude uses to reference it).
        description: Human-readable description of what the tool does.
        input_schema: Schema defining the tool's input parameters.
            Can be a dict mapping names to types, a TypedDict class, or JSON Schema.
        handler: Async function that handles tool calls.
    """

    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]


# =============================================================================
# MCP Server Types
# =============================================================================

class McpStdioServerConfig(TypedDict):
    """MCP stdio server configuration."""

    type: NotRequired[Literal[McpConfig.TYPE_STDIO]]
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]


class McpSSEServerConfig(TypedDict):
    """MCP SSE server configuration."""

    type: Literal[McpConfig.TYPE_SSE]
    url: str
    headers: NotRequired[dict[str, str]]


class McpHttpServerConfig(TypedDict):
    """MCP HTTP server configuration."""

    type: Literal[McpConfig.TYPE_HTTP]
    url: str
    headers: NotRequired[dict[str, str]]


class McpSdkServerConfig(TypedDict):
    """SDK MCP server configuration (for in-process servers).

    Note: Ripperdoc doesn't support this type yet, but the type is
    defined for API compatibility.
    """

    type: Literal[McpConfig.TYPE_SDK]
    name: str
    instance: Any  # MCP Server instance


# Union type for all MCP server configs
McpServerConfig = (
    McpStdioServerConfig | McpSSEServerConfig | McpHttpServerConfig | McpSdkServerConfig
)


# =============================================================================
# Plugin and Beta Types
# =============================================================================

class SdkPluginConfig(TypedDict):
    """SDK plugin configuration."""

    type: Literal["local"]
    path: str


# Beta features - re-export from config
SdkBeta = Literal[ConfigSdkBeta.CONTEXT_1M]


# =============================================================================
# Sandbox Types
# =============================================================================

class SandboxNetworkConfig(TypedDict, total=False):
    """Network configuration for sandbox."""

    allowUnixSockets: list[str]
    allowAllUnixSockets: bool
    allowLocalBinding: bool
    httpProxyPort: int
    socksProxyPort: int


class SandboxIgnoreViolations(TypedDict, total=False):
    """Violations to ignore in sandbox."""

    file: list[str]
    network: list[str]


class SandboxSettings(TypedDict, total=False):
    """Sandbox settings configuration.

    Controls how bash commands are sandboxed for isolation.
    Note: Ripperdoc doesn't fully support sandboxing yet,
    but the type is defined for API compatibility.
    """

    enabled: bool
    autoAllowBashIfSandboxed: bool
    excludedCommands: list[str]
    allowUnsandboxedCommands: bool
    network: SandboxNetworkConfig
    ignoreViolations: SandboxIgnoreViolations
    enableWeakerNestedSandbox: bool


# =============================================================================
# System Prompt Types
# =============================================================================

class SystemPromptPreset(TypedDict):
    """System prompt preset configuration."""

    type: Literal["preset"]
    preset: Literal["ripperdoc"]
    append: NotRequired[str]


class ToolsPreset(TypedDict):
    """Tools preset configuration."""

    type: Literal["preset"]
    preset: Literal["ripperdoc"]


# =============================================================================
# Error Types
# =============================================================================


class SDKError(Exception):
    """Base exception for all SDK errors."""


class CLIConnectionError(SDKError):
    """Raised when unable to connect to the service."""


class CLINotFoundError(CLIConnectionError):
    """Raised when the CLI is not found or not installed."""


class ProcessError(SDKError):
    """Raised when the process fails."""


class CLIJSONDecodeError(SDKError):
    """Raised when unable to decode JSON from output."""


class MessageParseError(SDKError):
    """Raised when unable to parse a message from output."""


# =============================================================================
# Assistant Message Error Types
# =============================================================================

AssistantMessageError = Literal[
    "authentication_failed",
    "billing_error",
    "rate_limit",
    "invalid_request",
    "server_error",
    "unknown",
]


# =============================================================================
# Transport Abstract Base Class
# =============================================================================


class Transport(ABC):
    """Abstract base class for transport implementations.

    Transport defines how the SDK communicates with the underlying service.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish the connection."""

    @abstractmethod
    async def write(self, data: str) -> None:
        """Write data to the transport."""

    @abstractmethod
    def read_messages(self) -> AsyncIterable[dict[str, Any]]:
        """Read messages from the transport."""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the transport is ready."""

    @abstractmethod
    async def end_input(self) -> None:
        """Signal that no more input will be sent."""
