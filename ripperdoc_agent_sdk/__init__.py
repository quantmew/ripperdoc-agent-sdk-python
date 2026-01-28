"""Ripperdoc Python SDK.

This SDK provides interfaces for Ripperdoc.
It supports subprocess communication with the Ripperdoc CLI via JSON Control Protocol.

Basic Usage:
    ```python
    from ripperdoc_sdk import query, RipperdocAgentOptions

    async for message in query(
        prompt="Hello!",
        options=RipperdocAgentOptions()
    ):
        print(message)
    ```

With a persistent client:
    ```python
    from ripperdoc_sdk import RipperdocSDKClient, RipperdocAgentOptions

    async with RipperdocSDKClient(options=RipperdocAgentOptions()) as client:
        await client.query("Help me with this code")
        async for message in client.receive_messages():
            print(message)
    ```
"""

from ripperdoc_agent_sdk.client import (
    # Core client and options
    query,
    RipperdocSDKClient,
    RipperdocAgentOptions,
    # Compatibility aliases
    RipperdocClient,
    # Types from client module
    AgentConfig,
    HookCallback,
    HookMatcher,
    McpServerConfig,
    PermissionMode,
    PermissionModeCompat,
    SettingSource,
    StderrCallback,
    clear_programmatic_registries,
    get_programmatic_agents,
    get_programmatic_hooks,
)

# Transport layer
from ripperdoc_agent_sdk.transport import (
    Transport,
    StdioTransport,
    StdioTransportConfig,
    InProcessTransport,
)

# Control protocol types (for subprocess communication)
from ripperdoc_agent_sdk.control_protocol import (
    SDKControlRequest,
    SDKControlResponse,
    StreamMessage,
    PermissionUpdate as ControlPermissionUpdate,
    ServerInfo,
)

from ripperdoc_agent_sdk.types import (
    # Main exports
    Message as _Message,
    # Message types
    UserMessage as _UserMessage,
    AssistantMessage as _AssistantMessage,
    SystemMessage as _SystemMessage,
    ResultMessage as _ResultMessage,
    StreamEvent as _StreamEvent,
    # Content blocks
    ContentBlock as _ContentBlock,
    TextBlock as _TextBlock,
    ThinkingBlock as _ThinkingBlock,
    ToolUseBlock as _ToolUseBlock,
    ToolResultBlock as _ToolResultBlock,
    # Permission types
    PermissionUpdate,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    # Tool callback types
    CanUseTool,
    ToolPermissionContext,
    # Hook support
    HookContext,
    HookInput,
    BaseHookInput,
    PreToolUseHookInput,
    PostToolUseHookInput,
    UserPromptSubmitHookInput,
    StopHookInput,
    SubagentStopHookInput,
    PreCompactHookInput,
    HookJSONOutput,
    HookEvent,
    # Agent support
    AgentDefinition,
    # MCP Server Support
    McpServerConfig as TypedMcpServerConfig,
    # Beta support
    SdkBeta,
    # Sandbox support
    SandboxSettings,
    # System prompt types
    SystemPromptPreset,
    ToolsPreset,
    # Error types
    SDKError,
    CLIConnectionError,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError,
    MessageParseError,
    # Transport
    Transport as TypedTransport,
    # Assistant message error types
    AssistantMessageError,
)

__version__ = "0.1.0"

# Re-export types with their original names
Message = _Message
UserMessage = _UserMessage
AssistantMessage = _AssistantMessage
SystemMessage = _SystemMessage
ResultMessage = _ResultMessage
StreamEvent = _StreamEvent
ContentBlock = _ContentBlock
TextBlock = _TextBlock
ThinkingBlock = _ThinkingBlock
ToolUseBlock = _ToolUseBlock
ToolResultBlock = _ToolResultBlock

__all__ = [
    # Main exports
    "query",
    "__version__",
    # Transport
    "Transport",
    "StdioTransport",
    "StdioTransportConfig",
    "InProcessTransport",
    # Control Protocol
    "SDKControlRequest",
    "SDKControlResponse",
    "StreamMessage",
    "PermissionUpdate",
    "ServerInfo",
    # Client and Options
    "RipperdocSDKClient",
    "RipperdocAgentOptions",
    # Compatibility aliases
    "RipperdocClient",
    # Types - Core
    "Message",
    "UserMessage",
    "AssistantMessage",
    "SystemMessage",
    "ResultMessage",
    "StreamEvent",
    # Types - Content Blocks
    "ContentBlock",
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    # Types - Permissions
    "PermissionMode",
    "PermissionModeCompat",
    "McpServerConfig",
    "PermissionUpdate",
    "PermissionResult",
    "PermissionResultAllow",
    "PermissionResultDeny",
    # Types - Tool Callbacks
    "CanUseTool",
    "ToolPermissionContext",
    # Types - Hooks
    "HookCallback",
    "HookContext",
    "HookInput",
    "BaseHookInput",
    "PreToolUseHookInput",
    "PostToolUseHookInput",
    "UserPromptSubmitHookInput",
    "StopHookInput",
    "SubagentStopHookInput",
    "PreCompactHookInput",
    "HookJSONOutput",
    "HookEvent",
    "HookMatcher",
    # Types - Agents
    "AgentDefinition",
    "AgentConfig",
    "SettingSource",
    # Types - Beta and Plugins
    "SdkBeta",
    # Types - Sandbox
    "SandboxSettings",
    # Types - System Prompt
    "SystemPromptPreset",
    "ToolsPreset",
    # Types - Errors
    "SDKError",
    "CLIConnectionError",
    "CLINotFoundError",
    "ProcessError",
    "CLIJSONDecodeError",
    "MessageParseError",
    # Types - Assistant Message Errors
    "AssistantMessageError",
    # Legacy types (for backward compatibility)
    "StderrCallback",
    # Registry access
    "get_programmatic_agents",
    "get_programmatic_hooks",
    "clear_programmatic_registries",
]
