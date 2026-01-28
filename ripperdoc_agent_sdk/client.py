"""Headless Python SDK for Ripperdoc.

This SDK provides interfaces while using Ripperdoc's internal implementation.

The SDK supports subprocess communication mode with JSON Control Protocol over stdio.
"""

from __future__ import annotations

import asyncio
import os
import warnings
from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    Literal,
)

from ripperdoc_agent_sdk.types import (
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    ContentBlock,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
    McpServerConfig as TypedMcpServerConfig,
    AgentDefinition as TypedAgentDefinition,
    HookMatcher as TypedHookMatcher,
    CanUseTool,
    ToolPermissionContext,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    PermissionUpdate,
    SdkBeta,
    SandboxSettings,
    SystemPromptPreset,
    ToolsPreset,
)

from ripperdoc_agent_sdk.adapter import (
    MessageAdapter,
    AsyncMessageAdapter,
    ResultMessageFactory,
)
from ripperdoc_agent_sdk.protocol import (
    ControlInitializeRequest,
    ControlQueryRequest,
    model_to_dict,
)
from ripperdoc_agent_sdk.config import (
    PermissionMode,
    SettingSource,
    ClientConfig,
)

# Subprocess mode imports (lazy loaded to avoid circular imports)
_subprocess_transport = None
_query_class = None


@dataclass
class McpServerConfig:
    """Configuration for an MCP server.

    Supports stdio, SSE, and HTTP server types.
    """

    # Server type: 'stdio', 'sse', or 'http'
    type: str = "stdio"
    # Command for stdio servers
    command: Optional[str] = None
    # Arguments for stdio servers
    args: Optional[List[str]] = None
    # URL for SSE/HTTP servers
    url: Optional[str] = None
    # Environment variables for stdio servers
    env: Optional[Dict[str, str]] = None
    # Headers for SSE/HTTP servers
    headers: Optional[Dict[str, str]] = None
    # Optional server description
    description: Optional[str] = None
    # Optional instructions for the server
    instructions: Optional[str] = None

    def to_typed_dict(self) -> TypedMcpServerConfig:
        """Convert to SDK compatible TypedDict format."""
        if self.type == "stdio":
            return {
                "type": "stdio",
                "command": self.command or "",
                **({"args": self.args} if self.args else {}),
                **({"env": self.env} if self.env else {}),
            }
        elif self.type == "sse":
            return {
                "type": "sse",
                "url": self.url or "",
                **({"headers": self.headers} if self.headers else {}),
            }
        elif self.type == "http":
            return {
                "type": "http",
                "url": self.url or "",
                **({"headers": self.headers} if self.headers else {}),
            }
        else:
            # Default to stdio
            return {
                "type": "stdio",
                "command": self.command or "",
            }

    @classmethod
    def from_typed_dict(cls, config: TypedMcpServerConfig) -> "McpServerConfig":
        """Create from SDK compatible TypedDict format."""
        server_type = config.get("type", "stdio")
        return cls(
            type=server_type,
            command=config.get("command"),
            args=config.get("args"),
            url=config.get("url"),
            env=config.get("env"),
            headers=config.get("headers"),
            description=config.get("description"),
            instructions=config.get("instructions"),
        )


@dataclass
class AgentConfig:
    """Programmatic configuration for a subagent.

    Allows defining custom subagents without using markdown files.
    """

    # Description of when to use this agent (shown in Task tool)
    description: str
    # System prompt for the agent
    prompt: str
    # Tools available to this agent. Use ["*"] for all tools.
    tools: Optional[List[str]] = None
    # Model to use: 'sonnet', 'opus', 'haiku', or None to inherit
    model: Optional[str] = None
    # Display color for the agent
    color: Optional[str] = None
    # Whether to fork context for this agent
    fork_context: bool = False

    def to_agent_definition(self) -> TypedAgentDefinition:
        """Convert to SDK compatible AgentDefinition."""
        return TypedAgentDefinition(
            description=self.description,
            prompt=self.prompt,
            tools=self.tools,
            model=self._map_model_value(self.model),
        )

    @staticmethod
    def _map_model_value(model: Optional[str]) -> Optional[Literal["sonnet", "opus", "haiku", "inherit"]]:
        """Map model string to SDK compatible literal."""
        if model is None:
            return None
        model_lower = model.lower()
        if "sonnet" in model_lower:
            return "sonnet"
        elif "opus" in model_lower:
            return "opus"
        elif "haiku" in model_lower:
            return "haiku"
        elif model_lower in ("inherit", "main"):
            return "inherit"
        return None

    @classmethod
    def from_agent_definition(cls, definition: TypedAgentDefinition) -> "AgentConfig":
        """Create from SDK compatible AgentDefinition."""
        return cls(
            description=definition.description,
            prompt=definition.prompt,
            tools=definition.tools,
            model=definition.model,
        )


# Type alias for hook callback functions
# Hook callbacks receive event type, input data, and return a decision dict
HookCallback = Callable[
    [str, Dict[str, Any]],
    Union[
        Dict[str, Any],  # Sync return
        Awaitable[Dict[str, Any]],  # Async return
    ],
]


@dataclass
class HookMatcher:
    """Matcher configuration for a programmatic hook.

    Defines when a hook should be triggered based on tool names or patterns.
    """
    # Callback function to execute
    callback: HookCallback
    # Tool name pattern to match (for PreToolUse/PostToolUse hooks)
    tool_pattern: Optional[str] = None

    def to_typed_matcher(self) -> TypedHookMatcher:
        """Convert to SDK compatible HookMatcher."""
        # Wrap single callback in a list for compatibility
        return TypedHookMatcher(
            matcher=self.tool_pattern,
            hooks=[self._wrap_callback(self.callback)],
        )

    @staticmethod
    def _wrap_callback(
        callback: HookCallback,
    ) -> Callable[
        [Any, str | None, Any],  # HookInput, tool_use_id, HookContext
        Awaitable[Dict[str, Any]],
    ]:
        """Wrap Ripperdoc-style hook callback to SDK format."""
        async def wrapped(
            input_data: Any,
            tool_use_id: str | None,
            context: Any,
        ) -> Dict[str, Any]:
            # Extract event type from input_data if available
            event_type = getattr(input_data, "hook_event_name", "Unknown")
            # Convert input to dict format expected by Ripperdoc callback
            input_dict = input_data if isinstance(input_data, dict) else {
                "event": event_type,
                "data": input_data,
            }
            result = callback(event_type, input_dict)
            if asyncio.iscoroutine(result):
                return await result
            return result  # type: ignore

        return wrapped


# Type alias for stderr callback
StderrCallback = Callable[[str], None]


_END_OF_STREAM = object()


@dataclass
class RipperdocAgentOptions:
    """Configuration for SDK usage.

    This is the main options class for configuring Ripperdoc SDK behavior.
    It provides SDK configuration options.

    Attributes:
        tools: Custom tools to use instead of defaults.
        allowed_tools: List of tool names to allow (whitelist).
        disallowed_tools: List of tool names to disallow (blacklist).
        permission_mode: Permission mode for operations. Defaults to DEFAULT.
        verbose: Enable verbose output.
        model: Model pointer to use. Defaults to "main".
        max_thinking_tokens: Maximum tokens for thinking (0 = disabled).
        max_turns: Maximum conversation turns before stopping. None = unlimited.
        context: Additional context dictionary.
        system_prompt: Custom system prompt (overrides default).
        additional_instructions: Extra instructions to append to system prompt.
        permission_checker: Custom function to check tool permissions.
        cwd: Working directory for the session.
        resume: Session ID to resume from.
        continue_conversation: Continue the most recent conversation.
        mcp_servers: Programmatic MCP server configurations.
        agents: Programmatic subagent definitions (keyed by agent type name).
        hooks: Programmatic hook callbacks (keyed by event name).
        env: Environment variables to pass to subprocesses.
        additional_directories: Extra directories the agent can access.
        include_partial_messages: Include partial message events during streaming.
        stderr: Callback for stderr output from subprocesses.
        fork_session: Create a new session branch when resuming.
        setting_sources: Which settings sources to load (user, project, local, env).
        user: User identifier for the session.
        permission_prompt_tool_name: MCP tool name for permission prompts.
        settings: Path to custom settings file.
        extra_args: Additional arguments to pass through.
        max_buffer_size: Maximum buffer size for streaming responses.
        cli_path: Path to the Ripperdoc CLI executable.
        query_timeout: Timeout in seconds for the query (default: 300 = 5 minutes).
    """

    tools: Optional[Sequence[Any]] = None
    allowed_tools: Optional[Sequence[str]] = None
    disallowed_tools: Optional[Sequence[str]] = None
    permission_mode: PermissionMode = PermissionMode.DEFAULT
    verbose: bool = False
    model: str = ClientConfig.DEFAULT_MODEL
    max_thinking_tokens: int = ClientConfig.DEFAULT_MAX_THINKING_TOKENS
    max_turns: Optional[int] = ClientConfig.DEFAULT_MAX_TURNS
    context: Dict[str, str] = field(default_factory=dict)
    system_prompt: Optional[str] = None
    additional_instructions: Optional[Union[str, Sequence[str]]] = None
    permission_checker: Optional[Callable] = None
    cwd: Optional[Union[str, Path]] = None
    # Session management
    resume: Optional[str] = None
    continue_conversation: bool = False
    fork_session: bool = False
    # MCP configuration
    mcp_servers: Optional[Dict[str, McpServerConfig]] = None
    # Programmatic agents (key = agent type name)
    agents: Optional[Dict[str, AgentConfig]] = None
    # Programmatic hooks (key = event name like "PreToolUse", "PostToolUse", etc.)
    hooks: Optional[Dict[str, List[HookMatcher]]] = None
    # Environment variables for subprocesses
    env: Optional[Dict[str, str]] = None
    # Additional directories the agent can access
    additional_directories: Optional[List[str]] = None
    # Include partial messages during streaming
    include_partial_messages: bool = False
    # Stderr callback for subprocess output
    stderr: Optional[StderrCallback] = None
    # Low priority options
    setting_sources: Optional[List[SettingSource]] = None
    user: Optional[str] = None
    permission_prompt_tool_name: Optional[str] = None
    settings: Optional[Union[str, Path]] = None
    extra_args: Optional[Dict[str, Optional[str]]] = None
    max_buffer_size: Optional[int] = None
    # CLI path for subprocess mode
    cli_path: Optional[str] = None
    # Query timeout in seconds
    query_timeout: float = ClientConfig.DEFAULT_QUERY_TIMEOUT
    # Deprecated: use permission_mode instead (kept for backward compatibility)
    yolo_mode: bool = False
    # SDK specific fields (accepted but may not be fully supported)
    max_budget_usd: Optional[float] = None
    fallback_model: Optional[str] = None
    betas: List[str] = field(default_factory=list)
    sandbox: Optional[Dict[str, Any]] = None
    enable_file_checkpointing: bool = False
    output_format: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Handle deprecated yolo_mode parameter."""
        # If yolo_mode is explicitly set to True, apply permission_mode
        if self.yolo_mode:
            warnings.warn(
                "yolo_mode is deprecated, "
                f"use permission_mode='{PermissionMode.BYPASS_PERMISSIONS}' instead",
                DeprecationWarning,
                stacklevel=3,
            )
            object.__setattr__(self, "permission_mode", PermissionMode.BYPASS_PERMISSIONS)

    def extra_instructions(self) -> List[str]:
        """Normalize additional instructions to a list."""
        if self.additional_instructions is None:
            return []
        if isinstance(self.additional_instructions, str):
            return [self.additional_instructions]
        return [text for text in self.additional_instructions if text]


# Module-level registries for programmatic agents and hooks
# These allow TaskTool and HookManager to access SDK-defined configurations
_programmatic_agents: Dict[str, Any] = {}  # agent_type -> AgentDefinition
_programmatic_hooks: Dict[str, List[HookMatcher]] = {}  # event_name -> List[HookMatcher]


def get_programmatic_agents() -> Dict[str, Any]:
    """Get programmatically registered agents."""
    return _programmatic_agents


def get_programmatic_hooks() -> Dict[str, List[HookMatcher]]:
    """Get programmatically registered hooks."""
    return _programmatic_hooks


def clear_programmatic_registries() -> None:
    """Clear all programmatic registries."""
    _programmatic_agents.clear()
    _programmatic_hooks.clear()


def _coerce_to_path(path: Union[str, Path]) -> Path:
    return path if isinstance(path, Path) else Path(path)


class RipperdocSDKClient:
    """Persistent session with conversation history.

    This class provides SDK compatible interface using
    subprocess architecture. The SDK communicates with a Ripperdoc CLI
    subprocess via JSON Control Protocol over stdio.

    Subprocess Architecture:
    - Client spawns a CLI subprocess
    - Communication via JSON Control Protocol over stdin/stdout
    - Enables multi-language SDK support and process isolation
    """

    def __init__(
        self,
        options: Optional["RipperdocAgentOptions"] = None,
    ) -> None:
        self.options = options or RipperdocAgentOptions()

        self._history: List[Any] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._current_task: Optional[asyncio.Task] = None
        self._connected = False
        self._previous_cwd: Optional[Path] = None
        self._session_hook_contexts: List[str] = []
        self._session_id: Optional[str] = None
        self._session_start_time: Optional[float] = None
        self._session_end_sent: bool = False
        self._turn_count: int = 0
        # Store init message to send on each query
        self._init_message: Optional[Any] = None
        # Track current model for SDK compatibility
        self._current_model: str = self.options.model or "unknown"

        # Subprocess components
        self._transport: Optional[Any] = None  # SubprocessCLITransport
        self._query: Optional[Any] = None  # Query class

        # Initialize subprocess components
        self._init_subprocess_components()

    def _init_subprocess_components(self) -> None:
        """Initialize subprocess mode components.

        Imports are done here to avoid circular import issues.
        """
        global _subprocess_transport, _query_class

        if _subprocess_transport is None:
            from ripperdoc_agent_sdk._internal.transport.stdio_cli import SubprocessCLITransport
            _subprocess_transport = SubprocessCLITransport

        if _query_class is None:
            from ripperdoc_agent_sdk._internal.query import Query
            _query_class = Query

        # Convert options to typed dict format for transport
        self._transport_options = self._build_transport_options()

    def _build_transport_options(self) -> Any:
        """Build options dict for SubprocessCLITransport."""
        # Build the options dict
        options_dict = {
            "cli_path": self.options.cli_path,
            "model": self.options.model or "main",
            "permission_mode": self.options.permission_mode,
            "max_turns": self.options.max_turns,
            "system_prompt": self.options.system_prompt,
            "cwd": str(self.options.cwd) if self.options.cwd else None,
            "allowed_tools": list(self.options.allowed_tools) if self.options.allowed_tools else None,
            "disallowed_tools": list(self.options.disallowed_tools) if self.options.disallowed_tools else None,
            "env": self.options.env or {},
            "stderr": self.options.stderr,
            "max_buffer_size": self.options.max_buffer_size,
            # SDK compatibility fields (passed but may be ignored)
            "max_budget_usd": self.options.max_budget_usd,
            "fallback_model": self.options.fallback_model,
            "betas": self.options.betas,
            "sandbox": self.options.sandbox,
            "enable_file_checkpointing": self.options.enable_file_checkpointing,
            "output_format": self.options.output_format,
        }

        # Remove None values
        options_dict = {k: v for k, v in options_dict.items() if v is not None}

        return options_dict

    @property
    def history(self) -> List[Any]:
        return list(self._history)

    @property
    def session_id(self) -> Optional[str]:
        """Return the current session ID."""
        return self._session_id

    @property
    def turn_count(self) -> int:
        """Return the number of turns in the current session."""
        return self._turn_count

    @property
    def user(self) -> Optional[str]:
        """Return the user identifier for this session."""
        return self.options.user

    async def __aenter__(self) -> "RipperdocSDKClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # type: ignore[override]
        await self.disconnect()

    async def connect(
        self,
        prompt: Optional[str] = None
    ) -> None:
        """Connect to the CLI subprocess and initialize the session.

        Args:
            prompt: Optional prompt to send after connecting.
        """
        if not self._connected:
            # Change working directory if specified
            if self.options.cwd is not None:
                self._previous_cwd = Path.cwd()
                os.chdir(_coerce_to_path(self.options.cwd))

            # Initialize subprocess connection
            await self._connect_subprocess()

            self._connected = True

        if prompt:
            await self.query(prompt)

    async def _connect_subprocess(self) -> None:
        """Initialize subprocess mode connection.

        Creates the SubprocessCLITransport and Query instances,
        connects to the CLI subprocess, and sends initialize request.
        """
        if not _subprocess_transport or not _query_class:
            raise RuntimeError("Subprocess components not initialized")

        # Build options dict for transport (avoids circular imports)
        options_dict = self._build_transport_options()

        # Create the transport with dict options
        self._transport = _subprocess_transport(
            prompt="",  # Empty prompt for streaming mode
            options=options_dict,  # Pass dict directly, transport accepts both dict and object
        )

        # Connect the transport (starts the subprocess)
        await self._transport.connect()

        # Create the Query handler
        self._query = _query_class(
            transport=self._transport,
            is_streaming_mode=True,
            can_use_tool=self._build_permission_checker(),
            hooks=self._build_hooks_dict(),
            sdk_mcp_servers=self.options.mcp_servers,
        )

        # Start the query's message reading task
        await self._query.start()

        # Send initialize request
        try:
            init_request = ControlInitializeRequest(
                options=options_dict,
                hooks=self._build_hooks_dict(),
            )
            init_response = await self._query._send_control_request(
                init_request,
                timeout=60.0,
            )
            self._session_id = init_response.get("response", {}).get("session_id")

            # Create and store init SystemMessage
            from ripperdoc_agent_sdk.types import SystemMessage
            init_data = init_response.get("response", {})
            self._init_message = SystemMessage(
                subtype="init",
                data={
                    "type": "system",  # SDK compatibility
                    "subtype": "init",
                    "cwd": options_dict.get("cwd", str(Path.cwd())),
                    "session_id": self._session_id,
                    "tools": init_data.get("tools", []),
                    "mcp_servers": init_data.get("mcp_servers", []),
                    "model": options_dict.get("model", "main"),
                    "permissionMode": options_dict.get("permission_mode", "default"),
                    "slash_commands": init_data.get("slash_commands", []),  # From CLI
                    "apiKeySource": init_data.get("apiKeySource", "none"),  # From CLI
                    "sdk_version": init_data.get("sdk_version", "0.1.0"),  # From CLI
                    "output_style": init_data.get("output_style", "default"),  # From CLI
                    "agents": init_data.get("agents", []),  # From CLI
                    "skills": init_data.get("skills", []),  # From CLI
                    "plugins": init_data.get("plugins", []),  # From CLI
                    "uuid": self._session_id,  # Use session_id as uuid
                }
            )
        except Exception:
            await self._transport.close()
            raise

    def _build_permission_checker(self) -> Optional[Callable]:
        """Build permission checker for subprocess mode."""
        if self.options.permission_mode == "bypassPermissions":
            return None

        # Create a wrapper that converts between SDK and CLI formats
        async def checker(
            tool_name: str,
            tool_input: dict[str, Any],
            context: Any,
        ) -> Any:
            from ripperdoc_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

            # Call the original permission checker
            if self.options.permission_checker:
                result = self.options.permission_checker(
                    tool_name,
                    tool_input,
                    context,
                )
                if asyncio.iscoroutine(result):
                    result = await result

                # Convert result to SDK format
                if isinstance(result, bool):
                    return PermissionResultAllow() if result else PermissionResultDeny()
                elif isinstance(result, tuple):
                    allowed, message = result
                    return PermissionResultAllow() if allowed else PermissionResultDeny(message=message)
                elif isinstance(result, dict):
                    if result.get("decision") == "allow":
                        return PermissionResultAllow(updated_input=result.get("updated_input"))
                    else:
                        return PermissionResultDeny(message=result.get("message"), interrupt=result.get("interrupt", False))
                elif isinstance(result, PermissionResult):
                    return result
                else:
                    return PermissionResultAllow()

            # Default: allow
            return PermissionResultAllow()

        return checker

    def _build_hooks_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Build hooks dict for subprocess mode."""
        hooks_dict: dict[str, list[dict[str, Any]]] = {}

        if not self.options.hooks:
            return hooks_dict

        # Convert HookMatcher objects to dict format
        for event_name, matchers in self.options.hooks.items():
            hooks_dict[event_name] = []
            for matcher in matchers:
                hook_dict = {
                    "matcher": matcher.matcher if hasattr(matcher, "matcher") else "*",
                    "callback_id": f"hook_{id(matcher)}",  # Use id as unique identifier
                }
                hooks_dict[event_name].append(hook_dict)

        return hooks_dict

    async def disconnect(self) -> None:
        """Close the subprocess connection and clean up resources."""
        # Close query and transport
        if self._query:
            await self._query.close()
            self._query = None
        if self._transport:
            await self._transport.close()
            self._transport = None

        # Cancel current task if running
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        # Restore working directory
        if self._previous_cwd:
            os.chdir(self._previous_cwd)
            self._previous_cwd = None

        self._connected = False

    async def query(self, prompt: str, session_id: str = "default") -> None:
        """Send a prompt and start streaming the response.

        Args:
            prompt: The prompt to send.
            session_id: Session identifier for the conversation (default: "default").
        """
        if self._current_task and not self._current_task.done():
            raise RuntimeError(
                "A query is already in progress; wait for it to finish or interrupt it."
            )

        if not self._connected:
            await self.connect()

        # Check max_turns limit
        if self.options.max_turns is not None and self._turn_count >= self.options.max_turns:
            from ripperdoc_agent_sdk.adapter import InternalMessage, InternalAssistantMessage
            error_message = InternalAssistantMessage(
                message=InternalMessage(
                    role="assistant",
                    content=f"Maximum turns ({self.options.max_turns}) reached. "
                    "Create a new session to continue."
                ),
            )
            self._queue = asyncio.Queue()
            await self._queue.put(error_message)
            await self._queue.put(_END_OF_STREAM)
            self._current_task = asyncio.create_task(asyncio.sleep(0))
            return

        self._queue = asyncio.Queue()

        # Re-add init message if available
        if self._init_message:
            await self._queue.put(self._init_message)

        # Send query via subprocess
        if not self._query:
            raise RuntimeError("Query not initialized in subprocess mode")

        async def _runner() -> None:
            try:
                # Send query request via control protocol using Pydantic model
                query_request = ControlQueryRequest(
                    prompt=prompt,
                    session_id=self._session_id or "default",
                )
                await self._query._send_control_request(query_request)

                # Receive messages from the query's message stream
                # Use a new iterator for each query
                message_iterator = self._query.receive_messages()
                async for message in message_iterator:
                    self._history.append(message)  # type: ignore[arg-type]
                    await self._queue.put(message)

                    # After receiving ResultMessage, stop receiving for this query
                    # but keep the subprocess running for potential follow-up queries
                    if isinstance(message, ResultMessage):
                        break
            finally:
                await self._queue.put(_END_OF_STREAM)

        self._current_task = asyncio.create_task(_runner())

    async def receive_messages(self) -> AsyncIterator[Message]:
        """Yield messages for the active query in SDK compatible format.

        This method returns messages in SDK compatible format
        (UserMessage, AssistantMessage, SystemMessage, ResultMessage).
        """
        if self._current_task is None:
            raise RuntimeError("No active query to receive messages from.")

        # Get query timeout from options (default: 5 minutes)
        query_timeout = self.options.query_timeout

        while True:
            try:
                # Add timeout to prevent indefinite hanging
                import asyncio
                message = await asyncio.wait_for(self._queue.get(), timeout=query_timeout)
            except asyncio.TimeoutError:
                # Timeout waiting for response - cancel the query task
                if self._current_task and not self._current_task.done():
                    self._current_task.cancel()
                    try:
                        await self._current_task
                    except asyncio.CancelledError:
                        pass

                # Raise an error to inform the caller
                raise TimeoutError(
                    f"Query timed out after {query_timeout} seconds. "
                    "The CLI process may have hung or crashed."
                )

            if message is _END_OF_STREAM:
                break

            # Messages are already in SDK format from subprocess
            yield message  # type: ignore

    async def receive_response(self) -> AsyncIterator[Message]:
        """Yield messages until and including a ResultMessage.

        This async iterator yields all messages in sequence and automatically terminates
        after yielding a ResultMessage (which indicates the response is complete).

        Yields:
            Message: Each message received (UserMessage, AssistantMessage, SystemMessage, ResultMessage)
        """
        async for message in self.receive_messages():
            yield message
            if isinstance(message, ResultMessage):
                # Wait for the runner task to complete before returning
                # This ensures end_input() is called and cleanup is done
                if self._current_task:
                    await self._current_task
                return

    async def interrupt(self) -> None:
        """Request cancellation of the active query."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        await self._queue.put(_END_OF_STREAM)

    async def set_permission_mode(self, mode: PermissionMode) -> None:
        """Change permission mode during conversation.

        Args:
            mode: The permission mode to set. Valid options:
                - 'default': Prompts for dangerous tools
                - 'acceptEdits': Auto-accept file edits
                - 'bypassPermissions': Allow all tools (use with caution)
                - 'plan': Planning mode - no execution

        Example:
            ```python
            async with RipperdocSDKClient() as client:
                await client.query("Help me analyze this code")
                await client.set_permission_mode('acceptEdits')
                await client.query("Now implement the fix")
            ```
        """
        if not PermissionMode.is_valid(mode):
            raise ValueError(
                f"Invalid permission mode: {mode}. "
                f"Valid modes: {PermissionMode.VALID_MODES}"
            )

        self.options.permission_mode = mode

    async def set_model(self, model: Optional[str] = None) -> None:
        """Change the AI model during conversation.

        Args:
            model: The model to use, or None to use default.

        Example:
            ```python
            async with RipperdocSDKClient() as client:
                await client.query("Help me understand this problem")
                await client.set_model('model-name')
                await client.query("Now implement the solution")
            ```
        """
        self.options.model = model
        self._current_model = model or "unknown"

    async def rewind_files(self, user_message_id: str) -> None:
        """Rewind tracked files to their state at a specific user message.

        Note: This is a placeholder for SDK compatibility.
        File checkpointing is not currently implemented in Ripperdoc.

        Args:
            user_message_id: UUID of the user message to rewind to.

        Raises:
            NotImplementedError: File checkpointing is not supported yet.
        """
        raise NotImplementedError(
            "File checkpointing and rewind_files() are not currently supported "
            "in Ripperdoc. This method exists for SDK API compatibility."
        )

    async def get_server_info(self) -> Dict[str, Any] | None:
        """Get server initialization info.

        Returns initialization information from the CLI including available commands,
        output styles, and server capabilities. Returns None if not in streaming mode.

        Returns:
            Dictionary with server info, or None if not connected.

        Example:
            ```python
            async with RipperdocSDKClient() as client:
                info = await client.get_server_info()
                if info:
                    print(f"Commands available: {len(info.get('commands', []))}")
                    print(f"Output style: {info.get('output_style', 'default')}")
            ```
        """
        if not self._connected or not self._query:
            return None

        # Return the initialization result that was obtained during connect
        if hasattr(self._query, '_initialization_result'):
            return self._query._initialization_result

        return {
            "session_id": self._session_id,
            "turn_count": self._turn_count,
            "model": self._current_model,
            "cwd": str(self.options.cwd) if self.options.cwd else None,
            "permission_mode": self.options.permission_mode,
        }


async def query(
    *,
    prompt: Union[str, AsyncIterable[dict[str, Any]]],
    options: Optional["RipperdocAgentOptions"] = None,
    transport: Any = None,  # Ignored, for SDK compatibility
) -> AsyncIterator[Message]:
    """Query for one-shot or unidirectional streaming interactions.

    This function provides a simple, stateless interface for queries where you don't need
    bidirectional communication or conversation management.

    Args:
        prompt: The prompt to send. Can be a string for single-shot queries
                or an AsyncIterable[dict] for streaming mode.
        options: Optional configuration (defaults to RipperdocAgentOptions() if None).
        transport: Ignored parameter for SDK compatibility.

    Yields:
        Messages from the conversation in SDK compatible format.

    Example:
        ```python
        async for message in query(
            prompt="What is the capital of France?",
            options=RipperdocAgentOptions(allowed_tools=["Bash"])
        ):
            print(message)
        ```
    """
    # Handle streaming mode (AsyncIterable prompt)
    if isinstance(prompt, AsyncIterable):
        # For streaming mode, we use the client directly
        client = RipperdocSDKClient(options=options)
        await client.connect()
        try:
            async for msg in client.receive_messages():
                yield msg
        finally:
            await client.disconnect()
        return

    # For simple string prompts, use the original flow
    internal_options = options or RipperdocAgentOptions()
    client = RipperdocSDKClient(options=internal_options)
    await client.connect()
    await client.query(str(prompt))

    try:
        async for message in client.receive_messages():
            # receive_messages() already converts to SDK compatible format
            yield message
    finally:
        await client.disconnect()


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# For backward compatibility, provide aliases using old names
RipperdocClient = RipperdocSDKClient

__all__ = [
    # Main client and options
    "query",
    "RipperdocSDKClient",
    "RipperdocAgentOptions",
    # Compatibility aliases
    "RipperdocClient",
    # Types from client module
    "AgentConfig",
    "HookCallback",
    "HookMatcher",
    "McpServerConfig",
    "PermissionMode",
    "SettingSource",
    "StderrCallback",
    "clear_programmatic_registries",
    "get_programmatic_agents",
    "get_programmatic_hooks",
]
