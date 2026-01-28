"""Centralized configuration constants for the Ripperdoc SDK.

This module provides a single source of truth for all configuration values,
reducing magic numbers and strings scattered throughout the codebase.

All environment variable keys and default values are defined here for easy
maintenance and consistency.
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# Environment Variable Keys
# =============================================================================

# Stream configuration
ENV_STREAM_CLOSE_TIMEOUT: Final = "RIPPERDOC_STREAM_CLOSE_TIMEOUT"

# =============================================================================
# Stream Configuration
# =============================================================================

class StreamConfig:
    """Configuration for stream management."""

    #: Default timeout for stream close (in milliseconds)
    DEFAULT_CLOSE_TIMEOUT_MS: Final = 60000

    #: Default timeout for stream close (in seconds)
    DEFAULT_CLOSE_TIMEOUT_SEC: Final = DEFAULT_CLOSE_TIMEOUT_MS / 1000.0

    #: Environment variable key for stream close timeout
    ENV_TIMEOUT_KEY: Final = ENV_STREAM_CLOSE_TIMEOUT

    @staticmethod
    def get_close_timeout() -> float:
        """Get the stream close timeout in seconds.

        Reads from environment variable or returns default.

        Returns:
            Timeout in seconds.
        """
        import os

        timeout_ms = float(
            os.environ.get(
                StreamConfig.ENV_TIMEOUT_KEY,
                StreamConfig.DEFAULT_CLOSE_TIMEOUT_MS,
            )
        )
        return timeout_ms / 1000.0


# =============================================================================
# Message Queue Configuration
# =============================================================================

class QueueConfig:
    """Configuration for message queue management."""

    #: Default buffer size for memory object streams
    DEFAULT_BUFFER_SIZE: Final = 1000

    #: Default buffer size for message send stream
    MESSAGE_SEND_BUFFER_SIZE: Final = 100


# =============================================================================
# Query Configuration
# =============================================================================

class QueryConfig:
    """Configuration for query management."""

    #: Default timeout for initialization (in seconds)
    DEFAULT_INITIALIZE_TIMEOUT: Final = 60.0

    #: Default timeout for control requests (in seconds)
    DEFAULT_CONTROL_REQUEST_TIMEOUT: Final = 60.0

    #: Prefix for request IDs
    REQUEST_ID_PREFIX: Final = "req_"

    #: Prefix for queue IDs
    QUEUE_ID_PREFIX: Final = "recv_"


# =============================================================================
# Message Type Constants
# =============================================================================

class MessageType:
    """Constants for message type values."""

    #: Control request message type
    CONTROL_REQUEST: Final = "control_request"

    #: Control response message type
    CONTROL_RESPONSE: Final = "control_response"

    #: Error message type
    ERROR: Final = "error"

    #: Result message type
    RESULT: Final = "result"

    #: Assistant message type
    ASSISTANT: Final = "assistant"

    #: User message type
    USER: Final = "user"


# =============================================================================
# Control Protocol Constants
# =============================================================================

class ControlProtocol:
    """Constants for control protocol messages."""

    #: Response subtype for success
    SUBTYPE_SUCCESS: Final = "success"

    #: Response subtype for error
    SUBTYPE_ERROR: Final = "error"

    #: Initialize request subtype
    SUBTYPE_INITIALIZE: Final = "initialize"

    #: Query request subtype
    SUBTYPE_QUERY: Final = "query"

    #: Tool permission request subtype
    SUBTYPE_CAN_USE_TOOL: Final = "can_use_tool"

    #: Hook callback request subtype
    SUBTYPE_HOOK_CALLBACK: Final = "hook_callback"

    #: MCP message request subtype
    SUBTYPE_MCP_MESSAGE: Final = "mcp_message"

    #: Interrupt request subtype
    SUBTYPE_INTERRUPT: Final = "interrupt"

    #: Set permission mode request subtype
    SUBTYPE_SET_PERMISSION_MODE: Final = "set_permission_mode"

    #: Set model request subtype
    SUBTYPE_SET_MODEL: Final = "set_model"

    #: Rewind files request subtype
    SUBTYPE_REWIND_FILES: Final = "rewind_files"


# =============================================================================
# Permission Mode Constants
# =============================================================================

class PermissionMode:
    """Permission mode constants.

    These define the available permission modes for tool usage.
    """

    #: Default mode - prompts for dangerous tools
    DEFAULT: Final = "default"

    #: Accept edits mode - auto-accept file edits
    ACCEPT_EDITS: Final = "acceptEdits"

    #: Plan mode - planning mode with no execution
    PLAN: Final = "plan"

    #: Bypass permissions mode - allow all tools (use with caution)
    BYPASS_PERMISSIONS: Final = "bypassPermissions"

    #: All valid permission modes
    VALID_MODES: Final = (DEFAULT, ACCEPT_EDITS, PLAN, BYPASS_PERMISSIONS)

    @classmethod
    def is_valid(cls, mode: str) -> bool:
        """Check if a permission mode is valid.

        Args:
            mode: The permission mode to check.

        Returns:
            True if the mode is valid, False otherwise.
        """
        return mode in cls.VALID_MODES


# =============================================================================
# Field Name Mapping for Python to CLI Conversion
# =============================================================================

class FieldNameMapping:
    """Mapping for Python-safe field names to CLI-expected field names.

    The Python SDK uses suffixes like `_` to avoid keyword conflicts,
    but the CLI expects the original keywords.
    """

    #: Mapping of Python field names to CLI field names
    MAPPING: Final = {
        "async_": "async",
        "continue_": "continue",
    }

    @classmethod
    def to_cli(cls, python_dict: dict[str, object]) -> dict[str, object]:
        """Convert Python-safe field names to CLI format.

        Args:
            python_dict: Dictionary with Python-safe field names.

        Returns:
            Dictionary with CLI-expected field names.
        """
        return {
            cls.MAPPING.get(k, k): v
            for k, v in python_dict.items()
        }


# =============================================================================
# Setting Source Constants
# =============================================================================

class SettingSource:
    """Sources for loading settings configuration.

    These control which settings files are loaded during session initialization.
    """

    #: User settings (~/.ripperdoc/settings.json)
    USER: Final = "user"

    #: Project settings (.ripperdoc/settings.json)
    PROJECT: Final = "project"

    #: Local settings (.ripperdoc.local/settings.json)
    LOCAL: Final = "local"

    #: Environment variables
    ENV: Final = "env"


# =============================================================================
# Permission Update Destination Constants
# =============================================================================

class PermissionUpdateDestination:
    """Destination types for permission updates."""

    #: User settings destination
    USER_SETTINGS: Final = "userSettings"

    #: Project settings destination
    PROJECT_SETTINGS: Final = "projectSettings"

    #: Local settings destination
    LOCAL_SETTINGS: Final = "localSettings"

    #: Session destination
    SESSION: Final = "session"


# =============================================================================
# Permission Behavior Constants
# =============================================================================

class PermissionBehavior:
    """Permission behavior types."""

    #: Allow behavior
    ALLOW: Final = "allow"

    #: Deny behavior
    DENY: Final = "deny"

    #: Ask behavior
    ASK: Final = "ask"


# =============================================================================
# Client Configuration
# =============================================================================

class ClientConfig:
    """Configuration for SDK client."""

    #: Default model to use
    DEFAULT_MODEL: Final = "main"

    #: Default query timeout in seconds (5 minutes)
    DEFAULT_QUERY_TIMEOUT: Final = 300.0

    #: Default max turns (None = unlimited)
    DEFAULT_MAX_TURNS: Final = None

    #: Default max thinking tokens (0 = disabled)
    DEFAULT_MAX_THINKING_TOKENS: Final = 0


# =============================================================================
# MCP Configuration
# =============================================================================

class McpConfig:
    """Configuration for MCP (Model Context Protocol) servers."""

    #: Stdio transport type
    TYPE_STDIO: Final = "stdio"

    #: SSE transport type
    TYPE_SSE: Final = "sse"

    #: HTTP transport type
    TYPE_HTTP: Final = "http"

    #: SDK transport type (in-process)
    TYPE_SDK: Final = "sdk"


# =============================================================================
# Hook Event Constants
# =============================================================================

class HookEvent:
    """Hook event type constants."""

    #: Pre tool use event
    PRE_TOOL_USE: Final = "PreToolUse"

    #: Post tool use event
    POST_TOOL_USE: Final = "PostToolUse"

    #: User prompt submit event
    USER_PROMPT_SUBMIT: Final = "UserPromptSubmit"

    #: Stop event
    STOP: Final = "Stop"

    #: Subagent stop event
    SUBAGENT_STOP: Final = "SubagentStop"

    #: Pre compact event
    PRE_COMPACT: Final = "PreCompact"


# =============================================================================
# SDK Beta Features
# =============================================================================

class SdkBeta:
    """SDK beta feature flags."""

    #: Context-1m beta feature
    CONTEXT_1M: Final = "context-1m-2025-08-07"


__all__ = [
    # Environment Variables
    "ENV_STREAM_CLOSE_TIMEOUT",
    # Stream Config
    "StreamConfig",
    # Queue Config
    "QueueConfig",
    # Query Config
    "QueryConfig",
    # Message Types
    "MessageType",
    # Control Protocol
    "ControlProtocol",
    # Permission Mode
    "PermissionMode",
    # Field Name Mapping
    "FieldNameMapping",
    # Setting Source
    "SettingSource",
    # Permission Update Destination
    "PermissionUpdateDestination",
    # Permission Behavior
    "PermissionBehavior",
    # Client Config
    "ClientConfig",
    # MCP Config
    "McpConfig",
    # Hook Events
    "HookEvent",
    # SDK Beta
    "SdkBeta",
]
