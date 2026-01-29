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

Protocol Models:
    ```python
    from ripperdoc_sdk import protocol

    # Create a control request using Pydantic models
    init_request = protocol.ControlInitializeRequest(
        options={"model": "main"},
        hooks=None,
    )
    ```

SDK MCP Server Support:
    ```python
    from ripperdoc_sdk import tool, create_sdk_mcp_server, RipperdocAgentOptions

    @tool("greet", "Greet a user", {"name": str})
    async def greet(args):
        return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

    server = create_sdk_mcp_server(name="my-server", tools=[greet])

    async for message in query(
        prompt="Say hello to Alice",
        options=RipperdocAgentOptions(mcp_servers={"my-server": server})
    ):
        print(message)
    ```
"""

from collections.abc import Awaitable, Callable
from typing import Any, Dict

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

# Protocol models (Pydantic models for type-safe protocol communication)
from ripperdoc_agent_sdk import protocol as _protocol_module
protocol = _protocol_module

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
    SdkMcpTool,
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

# =============================================================================
# SDK MCP Server Support (In-Process Tools)
# =============================================================================


def tool(
    name: str, description: str, input_schema: type | dict[str, Any]
) -> Callable[[Callable[[Any], Awaitable[dict[str, Any]]]], SdkMcpTool[Any]]:
    """Decorator for defining MCP tools with type safety.

    Creates a tool that can be used with SDK MCP servers. The tool runs
    in-process within your Python application, providing better performance
    than external MCP servers.

    Args:
        name: Unique identifier for the tool. This is what Claude will use
            to reference the tool in function calls.
        description: Human-readable description of what the tool does.
            This helps Claude understand when to use the tool.
        input_schema: Schema defining the tool's input parameters.
            Can be either:
            - A dictionary mapping parameter names to types (e.g., {"text": str})
            - A TypedDict class for more complex schemas
            - A JSON Schema dictionary for full validation

    Returns:
        A decorator function that wraps the tool implementation and returns
        an SdkMcpTool instance ready for use with create_sdk_mcp_server().

    Example:
        Basic tool with simple schema:
        >>> @tool("greet", "Greet a user", {"name": str})
        ... async def greet(args):
        ...     return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

        Tool with multiple parameters:
        >>> @tool("add", "Add two numbers", {"a": float, "b": float})
        ... async def add_numbers(args):
        ...     result = args["a"] + args["b"]
        ...     return {"content": [{"type": "text", "text": f"Result: {result}"}]}

        Tool with error handling:
        >>> @tool("divide", "Divide two numbers", {"a": float, "b": float})
        ... async def divide(args):
        ...     if args["b"] == 0:
        ...         return {"content": [{"type": "text", "text": "Error: Division by zero"}], "is_error": True}
        ...     return {"content": [{"type": "text", "text": f"Result: {args['a'] / args['b']}"}]}

    Notes:
        - The tool function must be async (defined with async def)
        - The function receives a single dict argument with the input parameters
        - The function should return a dict with a "content" key containing the response
        - Errors can be indicated by including "is_error": True in the response
    """

    def decorator(
        handler: Callable[[Any], Awaitable[dict[str, Any]]],
    ) -> SdkMcpTool[Any]:
        return SdkMcpTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )

    return decorator


def create_sdk_mcp_server(
    name: str, version: str = "1.0.0", tools: list[SdkMcpTool[Any]] | None = None
) -> TypedMcpServerConfig:
    """Create an in-process MCP server that runs within your Python application.

    Unlike external MCP servers that run as separate processes, SDK MCP servers
    run directly in your application's process. This provides:
    - Better performance (no IPC overhead)
    - Simpler deployment (single process)
    - Easier debugging (same process)
    - Direct access to your application's state

    Args:
        name: Unique identifier for the server. This name is used to reference
            the server in the mcp_servers configuration.
        version: Server version string. Defaults to "1.0.0". This is for
            informational purposes and doesn't affect functionality.
        tools: List of SdkMcpTool instances created with the @tool decorator.
            These are the functions that Claude can call through this server.
            If None or empty, the server will have no tools (rarely useful).

    Returns:
        McpSdkServerConfig: A configuration object (TypedDict) that can be passed to
            RipperdocAgentOptions.mcp_servers. This config contains the server
            instance and metadata needed for the SDK to route tool calls.

    Example:
        Simple calculator server:
        >>> @tool("add", "Add numbers", {"a": float, "b": float})
        ... async def add(args):
        ...     return {"content": [{"type": "text", "text": f"Sum: {args['a'] + args['b']}"}]}
        >>>
        >>> @tool("multiply", "Multiply numbers", {"a": float, "b": float})
        ... async def multiply(args):
        ...     return {"content": [{"type": "text", "text": f"Product: {args['a'] * args['b']}"}]}
        >>>
        >>> calculator = create_sdk_mcp_server(
        ...     name="calculator",
        ...     version="2.0.0",
        ...     tools=[add, multiply]
        ... )
        >>>
        >>> # Use with Ripperdoc
        >>> options = RipperdocAgentOptions(
        ...     mcp_servers={"calc": calculator},
        ...     allowed_tools=["add", "multiply"]
        ... )

        Server with application state access:
        >>> class DataStore:
        ...     def __init__(self):
        ...         self.items = []
        ...
        >>> store = DataStore()
        >>>
        >>> @tool("add_item", "Add item to store", {"item": str})
        ... async def add_item(args):
        ...     store.items.append(args["item"])
        ...     return {"content": [{"type": "text", "text": f"Added: {args['item']}"}]}
        >>>
        >>> server = create_sdk_mcp_server("store", tools=[add_item])

    Notes:
        - The server runs in the same process as your Python application
        - Tools have direct access to your application's variables and state
        - No subprocess or IPC overhead for tool calls
        - Server lifecycle is managed automatically by the SDK

    See Also:
        - tool(): Decorator for creating tool functions
        - RipperdocAgentOptions: Configuration for using servers with query()
    """
    from mcp.server import Server
    from mcp.types import ImageContent, TextContent, Tool

    # Create MCP server instance
    server = Server(name, version=version)

    # Register tools if provided
    if tools:
        # Store tools for access in handlers
        tool_map = {tool_def.name: tool_def for tool_def in tools}

        # Register list_tools handler to expose available tools
        @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
        async def list_tools() -> list[Tool]:
            """Return the list of available tools."""
            tool_list = []
            for tool_def in tools:
                # Convert input_schema to JSON Schema format
                if isinstance(tool_def.input_schema, dict):
                    # Check if it's already a JSON schema
                    if (
                        "type" in tool_def.input_schema
                        and "properties" in tool_def.input_schema
                    ):
                        schema = tool_def.input_schema
                    else:
                        # Simple dict mapping names to types - convert to JSON schema
                        properties = {}
                        for param_name, param_type in tool_def.input_schema.items():
                            if param_type is str:
                                properties[param_name] = {"type": "string"}
                            elif param_type is int:
                                properties[param_name] = {"type": "integer"}
                            elif param_type is float:
                                properties[param_name] = {"type": "number"}
                            elif param_type is bool:
                                properties[param_name] = {"type": "boolean"}
                            else:
                                properties[param_name] = {"type": "string"}  # Default
                        schema = {
                            "type": "object",
                            "properties": properties,
                            "required": list(properties.keys()),
                        }
                else:
                    # For TypedDict or other types, create basic schema
                    schema = {"type": "object", "properties": {}}

                tool_list.append(
                    Tool(
                        name=tool_def.name,
                        description=tool_def.description,
                        inputSchema=schema,
                    )
                )
            return tool_list

        # Register call_tool handler to execute tools
        @server.call_tool()  # type: ignore[untyped-decorator]
        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            """Execute a tool by name with given arguments."""
            if name not in tool_map:
                raise ValueError(f"Tool '{name}' not found")

            tool_def = tool_map[name]
            # Call the tool's handler with arguments
            result = await tool_def.handler(arguments)

            # Convert result to MCP format
            # The decorator expects us to return the content, not a CallToolResult
            # It will wrap our return value in CallToolResult
            content: list[TextContent | ImageContent] = []
            if "content" in result:
                for item in result["content"]:
                    if item.get("type") == "text":
                        content.append(TextContent(type="text", text=item["text"]))
                    if item.get("type") == "image":
                        content.append(
                            ImageContent(
                                type="image",
                                data=item["data"],
                                mimeType=item["mimeType"],
                            )
                        )

            # Return just the content list - the decorator wraps it
            return content

    # Return SDK server configuration as a dict matching McpSdkServerConfig type
    return {
        "type": "sdk",
        "name": name,
        "instance": server,
    }


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
    # Protocol module (Pydantic models)
    "protocol",
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
    # SDK MCP Server Support (In-Process Tools)
    "create_sdk_mcp_server",
    "tool",
    "SdkMcpTool",
]
