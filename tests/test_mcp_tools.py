"""Tests for MCP tool support."""

import pytest

from ripperdoc_agent_sdk import tool, create_sdk_mcp_server, SdkMcpTool


class TestToolDecorator:
    """Tests for @tool decorator."""

    def test_tool_decorator_returns_wrapper(self):
        """Test that @tool decorator returns a wrapper function."""
        wrapper = tool("test_tool", "Test description", {"input": str})
        assert callable(wrapper)

    def test_tool_decorator_creates_sdk_mcp_tool(self):
        """Test that @tool decorator creates SdkMcpTool instance."""

        @tool("add", "Add two numbers", {"a": float, "b": float})
        async def add_numbers(args):
            return {"content": [{"type": "text", "text": "OK"}]}

        assert isinstance(add_numbers, SdkMcpTool)
        assert add_numbers.name == "add"
        assert add_numbers.description == "Add two numbers"
        assert add_numbers.input_schema == {"a": float, "b": float}

    def test_tool_with_simple_schema(self):
        """Test tool with simple schema."""

        @tool("greet", "Greet user", {"name": str})
        async def greet(args):
            return {"content": [{"type": "text", "text": f"Hello {args['name']}"}]}

        assert greet.name == "greet"
        assert greet.input_schema == {"name": str}

    def test_tool_with_dict_schema(self):
        """Test tool with dict schema (JSON Schema)."""

        schema = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"},
            },
        }

        @tool("repeat", "Repeat text", schema)
        async def repeat(args):
            return {"content": [{"type": "text", "text": "OK"}]}

        assert repeat.name == "repeat"
        assert repeat.input_schema == schema

    def test_tool_stores_handler(self):
        """Test that tool stores the handler function."""

        async def my_handler(args):
            return {"content": [{"type": "text", "text": "OK"}]}

        tool_obj = tool("test", "Test", {"x": str})(my_handler)
        assert tool_obj.handler == my_handler


class TestCreateSdkMcpServer:
    """Tests for create_sdk_mcp_server function."""

    def test_create_server_minimal(self):
        """Test creating a server with minimal parameters."""
        server = create_sdk_mcp_server(name="test_server")
        # McpSdkServerConfig is a TypedDict
        assert server["type"] == "sdk"
        assert server["name"] == "test_server"
        assert server["instance"] is not None

    def test_create_server_with_version(self):
        """Test creating a server with custom version."""
        server = create_sdk_mcp_server(name="test", version="2.0.0")
        assert server["name"] == "test"
        # The version is set on the internal MCP server instance

    def test_create_server_with_tools(self):
        """Test creating a server with tools."""

        @tool("echo", "Echo input", {"text": str})
        async def echo(args):
            return {"content": [{"type": "text", "text": args['text']}]}

        @tool("add", "Add numbers", {"a": int, "b": int})
        async def add(args):
            return {"content": [{"type": "text", "text": str(args['a'] + args['b'])}]}

        server = create_sdk_mcp_server(
            name="calculator",
            version="1.0.0",
            tools=[echo, add],
        )
        assert server["name"] == "calculator"
        assert server["instance"] is not None

    def test_create_server_with_empty_tools(self):
        """Test creating a server with empty tools list."""
        server = create_sdk_mcp_server(name="empty", tools=[])
        assert server["name"] == "empty"
        assert server["instance"] is not None
