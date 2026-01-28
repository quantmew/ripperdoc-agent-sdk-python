# Ripperdoc Python SDK

Python SDK for Ripperdoc AI Agent.

## Features

- **Subprocess Architecture**: Clean separation between SDK and CLI via JSON Control Protocol
- **Async-First**: Built with `asyncio` and `anyio` for efficient async operations
- **Type Safety**: Full type hints for better IDE support and type checking
- **Comprehensive**: Support for hooks, permissions, MCP servers, and custom tools

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/quantmew/ripperdoc-agent-sdk-python
```

For development:

```bash
pip install git+https://github.com/quantmew/ripperdoc-agent-sdk-python#egg=ripperdoc-agent-sdk[dev]
```

## Quick Start

### Simple Query

```python
import asyncio
from ripperdoc_agent_sdk import query, RipperdocAgentOptions

async def main():
    async for message in query(
        prompt="What is the capital of France?",
        options=RipperdocAgentOptions()
    ):
        print(message)

asyncio.run(main())
```

### Persistent Client

```python
import asyncio
from ripperdoc_agent_sdk import RipperdocSDKClient, RipperdocAgentOptions

async def main():
    async with RipperdocSDKClient(options=RipperdocAgentOptions()) as client:
        await client.query("Help me understand this code")

        async for message in client.receive_messages():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(main())
```

## Configuration

### RipperdocAgentOptions

```python
from ripperdoc_agent_sdk import RipperdocAgentOptions

options = RipperdocAgentOptions(
    model="model-name",
    permission_mode="default",  # or "acceptEdits", "bypassPermissions", "plan"
    allowed_tools=["Bash", "Read", "Write"],
    max_turns=10,
    system_prompt="You are a helpful coding assistant",
    cli_path="/path/to/ripperdoc",  # Optional: path to Ripperdoc CLI
)
```

### Permission Modes

- `"default"`: Prompts for dangerous operations
- `"acceptEdits"`: Auto-accept file edits
- `"bypassPermissions"`: Allow all operations (use with caution)
- `"plan"`: Planning mode with no execution

## Advanced Usage

### Custom Permission Checker

```python
from ripperdoc_agent_sdk import (
    RipperdocSDKClient,
    RipperdocAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
)

async def my_permission_checker(tool_name, tool_input, context):
    # Custom permission logic
    if tool_name == "Bash" and "rm -rf" in tool_input.get("command", ""):
        return PermissionResultDeny(message="Dangerous command!")
    return PermissionResultAllow()

options = RipperdocAgentOptions(
    permission_checker=my_permission_checker,
)
```

### Programmatic Hooks

```python
from ripperdoc_agent_sdk import RipperdocAgentOptions, HookMatcher

async def my_hook(event_type, data):
    print(f"Hook event: {event_type}")
    return {"continue_": True}

options = RipperdocAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(
                callback=my_hook,
                tool_pattern="Bash*",
            )
        ]
    },
)
```

### MCP Servers

```python
from ripperdoc_agent_sdk import RipperdocAgentOptions, McpServerConfig

options = RipperdocAgentOptions(
    mcp_servers={
        "my-server": McpServerConfig(
            type="stdio",
            command="node",
            args=["/path/to/server.js"],
        )
    },
)
```

### Custom Agents

```python
from ripperdoc_agent_sdk import RipperdocAgentOptions, AgentConfig

options = RipperdocAgentOptions(
    agents={
        "code-reviewer": AgentConfig(
            description="Reviews code for bugs and style issues",
            prompt="You are a code reviewer. Focus on bug detection and style.",
            tools=["Read", "Grep"],
        )
    },
)
```

## Message Types

The SDK provides the following message types:

- `UserMessage`: Messages from the user
- `AssistantMessage`: Responses from the AI
- `SystemMessage`: System-level events
- `ResultMessage`: Query completion with metadata
- `StreamEvent`: Raw stream events

### Content Blocks

- `TextBlock`: Plain text content
- `ThinkingBlock`: Extended thinking output
- `ToolUseBlock`: Tool invocation
- `ToolResultBlock`: Tool execution result

## Architecture

The SDK uses a subprocess architecture:

```
┌─────────────────────┐
│   Python SDK        │
│                     │
│  ┌───────────────┐  │
│  │ Ripperdoc     │  │
│  │ SDK Client    │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ JSON Control  │  │
│  │   Protocol    │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │ stdio
    ┌──────▼─────────┐
    │  Ripperdoc     │
    │  CLI Process   │
    └────────────────┘
```

## Development

### Running Tests

```bash
pytest tests/
```

### Type Checking

```bash
mypy ripperdoc_agent_sdk
```

### Code Formatting

```bash
black ripperdoc_agent_sdk
ruff check ripperdoc_agent_sdk
```

## Requirements

- Python 3.10+
- anyio >= 4.0.0
- pydantic >= 2.0.0

## License

Apache License 2.0

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## Related Projects

- [Ripperdoc](https://github.com/your-org/ripperdoc) - The main Ripperdoc CLI
