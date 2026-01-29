"""Test script for SDK MCP server functionality."""

import asyncio
from mcp.types import ListToolsRequest, CallToolRequest, CallToolRequestParams
from ripperdoc_agent_sdk import tool, create_sdk_mcp_server


async def test_tool_decorator():
    """Test the tool decorator."""
    print("Testing @tool decorator...")

    @tool("greet", "Greet a user", {"name": str})
    async def greet(args: dict[str, str]) -> dict[str, any]:
        return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

    assert greet.name == "greet"
    assert greet.description == "Greet a user"
    assert greet.input_schema == {"name": str}
    assert callable(greet.handler)
    print("  @tool decorator works!")


async def test_create_sdk_mcp_server():
    """Test the create_sdk_mcp_server function."""
    print("Testing create_sdk_mcp_server...")

    @tool("add", "Add two numbers", {"a": float, "b": float})
    async def add(args: dict[str, float]) -> dict[str, any]:
        result = args["a"] + args["b"]
        return {"content": [{"type": "text", "text": f"Sum: {result}"}]}

    @tool("multiply", "Multiply two numbers", {"a": float, "b": float})
    async def multiply(args: dict[str, float]) -> dict[str, any]:
        result = args["a"] * args["b"]
        return {"content": [{"type": "text", "text": f"Product: {result}"}]}

    # Create server with tools
    calculator = create_sdk_mcp_server(
        name="calculator",
        version="2.0.0",
        tools=[add, multiply]
    )

    assert calculator["type"] == "sdk"
    assert calculator["name"] == "calculator"
    assert "instance" in calculator
    print("  create_sdk_mcp_server works!")

    # Test the MCP server directly
    server = calculator["instance"]

    # Get list of tools using MCP protocol
    list_handler = server.request_handlers.get(ListToolsRequest)
    result = await list_handler(ListToolsRequest())
    tools = result.root.tools
    assert len(tools) == 2
    assert tools[0].name == "add"
    assert tools[1].name == "multiply"
    print("  list_tools works!")

    # Test calling a tool using MCP protocol
    call_handler = server.request_handlers.get(CallToolRequest)
    params = CallToolRequestParams(name="add", arguments={"a": 3.5, "b": 2.5})
    result = await call_handler(CallToolRequest(params=params))
    content = result.root.content
    assert len(content) == 1
    assert content[0].type == "text"
    assert "6.0" in content[0].text
    print("  call_tool works!")

    # Test multiply
    params = CallToolRequestParams(name="multiply", arguments={"a": 3, "b": 4})
    result = await call_handler(CallToolRequest(params=params))
    content = result.root.content
    assert len(content) == 1
    assert content[0].type == "text"
    assert "12" in content[0].text
    print("  multiply tool works!")


async def test_error_handling():
    """Test error handling in tools."""
    print("Testing error handling...")

    @tool("divide", "Divide two numbers", {"a": float, "b": float})
    async def divide(args: dict[str, float]) -> dict[str, any]:
        if args["b"] == 0:
            return {
                "content": [{"type": "text", "text": "Error: Division by zero"}],
                "is_error": True
            }
        result = args["a"] / args["b"]
        return {"content": [{"type": "text", "text": f"Result: {result}"}]}

    server = create_sdk_mcp_server(name="math", tools=[divide])
    call_handler = server["instance"].request_handlers.get(CallToolRequest)

    # Test normal division
    params = CallToolRequestParams(name="divide", arguments={"a": 10, "b": 2})
    result = await call_handler(CallToolRequest(params=params))
    content = result.root.content
    assert "5" in content[0].text
    print("  Normal division works!")

    # Test division by zero
    params = CallToolRequestParams(name="divide", arguments={"a": 10, "b": 0})
    result = await call_handler(CallToolRequest(params=params))
    content = result.root.content
    assert "Division by zero" in content[0].text
    print("  Error handling works!")


async def test_json_schema_input():
    """Test tool with JSON Schema input."""
    print("Testing JSON Schema input...")

    json_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "count": {"type": "integer", "default": 1}
        },
        "required": ["message"]
    }

    @tool("echo", "Echo a message", json_schema)
    async def echo(args: dict[str, any]) -> dict[str, any]:
        message = args.get("message", "")
        count = args.get("count", 1)
        return {"content": [{"type": "text", "text": message * count}]}

    server = create_sdk_mcp_server(name="echo_server", tools=[echo])
    list_handler = server["instance"].request_handlers.get(ListToolsRequest)
    result = await list_handler(ListToolsRequest())
    tools = result.root.tools
    assert tools[0].name == "echo"
    assert tools[0].inputSchema == json_schema
    print("  JSON Schema input works!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Running SDK MCP Server Tests")
    print("=" * 60)

    await test_tool_decorator()
    await test_create_sdk_mcp_server()
    await test_error_handling()
    await test_json_schema_input()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
