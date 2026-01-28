"""Tests for subprocess mode functionality.

This test module covers:
- Subprocess mode options
- Transport layer
- Query class
- Protocol handler
- Integration tests
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from dataclasses import dataclass

import pytest

from ripperdoc_agent_sdk import RipperdocAgentOptions, RipperdocSDKClient
from ripperdoc_agent_sdk._internal.transport import Transport
from ripperdoc_agent_sdk._internal.query import Query
from ripperdoc_agent_sdk._internal.message_parser import parse_message
from ripperdoc_agent_sdk._errors import (
    CLIConnectionError,
    CLINotFoundError,
    MessageParseError,
)
from ripperdoc_agent_sdk.types import (
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ContentBlock,
)


class MockTransport(Transport):
    """Mock transport for testing."""

    def __init__(self, prompt: str = "", options: Any = None) -> None:
        self._connected = False
        self._ready = False
        self._messages_to_send: list[dict[str, Any]] = []
        self._received_messages: list[str] = []
        self._prompt = prompt
        self._options = options
        self._closed = False

    async def connect(self) -> None:
        """Mock connect."""
        self._connected = True
        self._ready = True

    async def write(self, data: str) -> None:
        """Mock write."""
        self._received_messages.append(data)

    def read_messages(self):
        """Mock read messages - returns an async iterable that immediately exits."""
        # Return an async generator that immediately exits (empty stream)
        async def _reader():
            return
            yield  # This makes it an async generator but never yields anything

        return _reader()

    async def close(self) -> None:
        """Mock close."""
        self._closed = True
        self._connected = False
        self._ready = False

    def is_ready(self) -> bool:
        """Check if ready."""
        return self._ready

    async def end_input(self) -> None:
        """Mock end input."""
        pass


class TestMessageParser:
    """Test message parsing from CLI output."""

    def test_parse_user_message_with_string_content(self) -> None:
        """Parse user message with string content."""
        data = {
            "type": "user",
            "message": {"content": "Hello, world!"},
            "uuid": "test-uuid",
        }
        message = parse_message(data)
        assert isinstance(message, UserMessage)
        assert message.content == "Hello, world!"
        assert message.uuid == "test-uuid"

    def test_parse_user_message_with_block_content(self) -> None:
        """Parse user message with content blocks."""
        data = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {"command": "ls"}}
                ]
            },
            "uuid": "test-uuid",
        }
        message = parse_message(data)
        assert isinstance(message, UserMessage)
        assert isinstance(message.content, list)
        assert len(message.content) == 2
        assert isinstance(message.content[0], TextBlock)
        assert message.content[0].text == "Hello"
        assert isinstance(message.content[1], ToolUseBlock)
        assert message.content[1].name == "Bash"

    def test_parse_user_message_tool_result_normalization(self) -> None:
        """Test ToolResultBlock normalization for SDK compatibility.

        This test verifies that:
        1. content=None is converted to actual content from tool_use_result
        2. is_error=None is converted to is_error=False
        3. tool_use_result dict is properly handled
        """
        # Case 1: Tool result with content=None and tool_use_result dict (Ripperdoc format)
        data = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "Read:0",
                        "content": None,
                        "is_error": None,
                    }
                ]
            },
            "uuid": "test-uuid",
            "tool_use_result": {
                "content": "file content here",
                "file_path": "/path/to/file.txt",
                "line_count": 100,
            },
        }
        message = parse_message(data)
        assert isinstance(message, UserMessage)
        assert isinstance(message.content, list)
        assert len(message.content) == 1
        result_block = message.content[0]
        assert isinstance(result_block, ToolResultBlock)
        assert result_block.tool_use_id == "Read:0"
        # Content should be extracted from tool_use_result
        assert result_block.content == "file content here"
        # is_error=None should be converted to False
        assert result_block.is_error is False

        # Case 2: Tool result with explicit content (already correct format)
        data2 = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_123",
                        "content": "Error: File not found",
                        "is_error": True,
                    }
                ]
            },
            "uuid": "test-uuid",
            "tool_use_result": "Error: File not found",
        }
        message2 = parse_message(data2)
        assert isinstance(message2, UserMessage)
        assert isinstance(message2.content, list)
        assert len(message2.content) == 1
        result_block2 = message2.content[0]
        assert isinstance(result_block2, ToolResultBlock)
        assert result_block2.tool_use_id == "call_123"
        assert result_block2.content == "Error: File not found"
        assert result_block2.is_error is True

        # Case 3: Tool result with is_error=None (should convert to False)
        data3 = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-1",
                        "content": "Success",
                        "is_error": None,
                    }
                ]
            },
            "uuid": "test-uuid",
        }
        message3 = parse_message(data3)
        assert isinstance(message3, UserMessage)
        assert isinstance(message3.content, list)
        result_block3 = message3.content[0]
        assert isinstance(result_block3, ToolResultBlock)
        assert result_block3.content == "Success"
        assert result_block3.is_error is False

    def test_parse_assistant_message(self) -> None:
        """Parse assistant message."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Response text"}
                ],
                "model": "model-name",
            },
        }
        message = parse_message(data)
        assert isinstance(message, AssistantMessage)
        assert message.model == "model-name"
        assert isinstance(message.content, list)
        assert len(message.content) == 1
        assert isinstance(message.content[0], TextBlock)
        assert message.content[0].text == "Response text"

    def test_parse_assistant_message_with_thinking(self) -> None:
        """Parse assistant message with thinking block."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "Let me think...",
                        "signature": "sig123"
                    },
                    {"type": "text", "text": "Answer"}
                ],
                "model": "model-name",
            },
        }
        message = parse_message(data)
        assert isinstance(message, AssistantMessage)
        assert len(message.content) == 2

    def test_parse_progress_message(self) -> None:
        """Parse progress message."""
        data = {
            "type": "progress",
            "tool_use_id": "tool-1",
            "content": "Processing...",
        }
        message = parse_message(data)
        assert isinstance(message, SystemMessage)
        assert message.subtype == "progress"
        assert message.data["tool_use_id"] == "tool-1"
        assert message.data["content"] == "Processing..."

    def test_parse_result_message(self) -> None:
        """Parse result message."""
        data = {
            "type": "result",
            "duration_ms": 1500,
            "duration_api_ms": 1200,
            "is_error": False,
            "num_turns": 3,
            "session_id": "sess-123",
            "total_cost_usd": 0.01,
        }
        message = parse_message(data)
        assert isinstance(message, ResultMessage)
        assert message.duration_ms == 1500
        assert message.is_error is False
        assert message.num_turns == 3
        assert message.session_id == "sess-123"

    def test_parse_system_message(self) -> None:
        """Parse system message."""
        data = {
            "type": "system",
            "subtype": "error",
            "data": {"message": "An error occurred"},
        }
        message = parse_message(data)
        assert isinstance(message, SystemMessage)
        assert message.subtype == "error"

    def test_parse_init_message_normalization(self) -> None:
        """Test init message normalization for SDK compatibility.

        This test verifies that:
        1. agents=[] is populated with default agents
        2. slash_commands=[] is populated with default commands
        3. model is preserved from the original data
        4. Other fields like session_id, tools, etc. are preserved
        """
        # Case 1: Ripperdoc format with empty agents and slash_commands
        data = {
            "type": "system",
            "subtype": "init",
            "data": {
                "type": "system",
                "subtype": "init",
                "cwd": "/path/to/project",
                "session_id": "test-session-123",
                "tools": ["Bash", "Read", "Write"],
                "model": "main",
                "permissionMode": "acceptEdits",
                "slash_commands": [],
                "apiKeySource": "none",
                "sdk_version": "0.1.0",
                "output_style": "default",
                "agents": [],
                "skills": [],
                "plugins": [],
            },
        }
        message = parse_message(data)
        assert isinstance(message, SystemMessage)
        assert message.subtype == "init"

        # Verify agents are populated with defaults
        agents = message.data.get("agents", [])
        assert len(agents) > 0
        assert "Bash" in agents
        assert "general-purpose" in agents

        # Verify slash_commands are populated with defaults
        slash_commands = message.data.get("slash_commands", [])
        assert len(slash_commands) > 0
        assert "compact" in slash_commands
        assert "context" in slash_commands

        # Verify other important fields are preserved
        assert message.data.get("session_id") == "test-session-123"
        assert message.data.get("model") == "main"
        assert message.data.get("permissionMode") == "acceptEdits"
        assert message.data.get("cwd") == "/path/to/project"

        # Case 2: Init message with existing agents (should keep existing)
        data2 = {
            "type": "system",
            "subtype": "init",
            "data": {
                "type": "system",
                "subtype": "init",
                "model": "kimi-k2.5",
                "session_id": "test-session-456",
                "agents": ["custom-agent"],
                "slash_commands": ["custom-command"],
            },
        }
        message2 = parse_message(data2)
        assert isinstance(message2, SystemMessage)
        # When agents/slash_commands are not empty, keep them as-is
        assert message2.data.get("agents") == ["custom-agent"]
        assert message2.data.get("slash_commands") == ["custom-command"]
        # Other fields should still be preserved
        assert message2.data.get("model") == "kimi-k2.5"
        assert message2.data.get("session_id") == "test-session-456"

    def test_parse_invalid_message_type(self) -> None:
        """Parse invalid message type raises error."""
        data = {
            "type": "unknown_type",
            "data": {},
        }
        with pytest.raises(MessageParseError, match="Unknown message type"):
            parse_message(data)

    def test_parse_message_missing_type(self) -> None:
        """Parse message without type raises error."""
        data = {"data": {}}
        with pytest.raises(MessageParseError, match="missing 'type'"):
            parse_message(data)

    def test_parse_message_invalid_data_type(self) -> None:
        """Parse non-dict data raises error."""
        with pytest.raises(MessageParseError, match="Invalid message data type"):
            parse_message("not a dict")  # type: ignore


class TestQueryClass:
    """Test Query class for control protocol."""

    @pytest.fixture
    def mock_transport(self) -> MockTransport:
        """Create a mock transport."""
        return MockTransport()

    @pytest.mark.asyncio
    async def test_query_initialization(self, mock_transport: MockTransport) -> None:
        """Test Query initialization."""
        query = Query(
            transport=mock_transport,
            is_streaming_mode=True,
        )
        assert query.transport == mock_transport
        assert query.is_streaming_mode is True
        assert query._initialized is False

    @pytest.mark.asyncio
    async def test_query_send_message(self, mock_transport: MockTransport) -> None:
        """Test sending a message through Query."""
        query = Query(
            transport=mock_transport,
            is_streaming_mode=True,
        )
        await query.start()

        # Send a test message
        await query.send_message("test_type", {"key": "value"})

        # Close the query immediately (no need to receive messages in this test)
        await query.close()

    @pytest.mark.asyncio
    async def test_query_close(self, mock_transport: MockTransport) -> None:
        """Test Query cleanup."""
        query = Query(
            transport=mock_transport,
            is_streaming_mode=True,
        )
        await query.start()
        await query.close()

        assert query._closed is True


class TestSubprocessClient:
    """Test subprocess mode client functionality."""

    def test_client_initialization(self) -> None:
        """Test client creates subprocess components."""
        options = RipperdocAgentOptions()
        client = RipperdocSDKClient(options=options)

        # Subprocess components should be initialized
        assert hasattr(client, "_transport_options")
        assert hasattr(client, "_transport")
        assert hasattr(client, "_query")

    def test_build_transport_options(self) -> None:
        """Test building transport options from RipperdocAgentOptions."""
        options = RipperdocAgentOptions(
            model="model-name",
            permission_mode="bypassPermissions",
            allowed_tools=["Bash", "Read"],
            cwd="/test/path",
        )
        client = RipperdocSDKClient(options=options)

        transport_options = client._build_transport_options()

        assert transport_options["model"] == "model-name"
        assert transport_options["permission_mode"] == "bypassPermissions"
        assert transport_options["allowed_tools"] == ["Bash", "Read"]
        assert transport_options["cwd"] == "/test/path"

    @pytest.mark.asyncio
    async def test_subprocess_connect_mocked(self) -> None:
        """Test subprocess connection with mocked transport."""
        options = RipperdocAgentOptions()

        with patch(
            "ripperdoc_agent_sdk.client._subprocess_transport",
            MockTransport
        ):
            client = RipperdocSDKClient(options=options)

            # Mock the Query class
            mock_query = MagicMock()
            mock_query.start = AsyncMock()
            mock_query._send_control_request = AsyncMock(return_value={
                "response": {
                    "session_id": "test-session-123"
                }
            })

            with patch("ripperdoc_agent_sdk.client._query_class", return_value=mock_query):
                await client._connect_subprocess()

                assert client._session_id == "test-session-123"


class TestControlProtocol:
    """Test JSON Control Protocol messages."""

    def test_initialize_request_format(self) -> None:
        """Test initialize request format."""
        request = {
            "type": "control_request",
            "request_id": "req_1",
            "request": {
                "subtype": "initialize",
                "options": {
                    "model": "model-name",
                    "permission_mode": "default",
                }
            }
        }
        # Validate structure
        assert request["type"] == "control_request"
        assert request["request_id"] == "req_1"
        assert request["request"]["subtype"] == "initialize"
        assert "options" in request["request"]

    def test_query_request_format(self) -> None:
        """Test query request format."""
        request = {
            "type": "control_request",
            "request_id": "req_2",
            "request": {
                "subtype": "query",
                "prompt": "Hello, world!",
            }
        }
        # Validate structure
        assert request["type"] == "control_request"
        assert request["request"]["subtype"] == "query"
        assert request["request"]["prompt"] == "Hello, world!"

    def test_control_response_success_format(self) -> None:
        """Test control response success format."""
        response = {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "req_1",
                "response": {
                    "session_id": "sess-123",
                    "tools": [{"name": "Bash"}],
                }
            }
        }
        # Validate structure
        assert response["type"] == "control_response"
        assert response["response"]["subtype"] == "success"
        assert "session_id" in response["response"]["response"]

    def test_control_response_error_format(self) -> None:
        """Test control response error format."""
        response = {
            "type": "control_response",
            "response": {
                "subtype": "error",
                "request_id": "req_1",
                "error": "Something went wrong",
            }
        }
        # Validate structure
        assert response["type"] == "control_response"
        assert response["response"]["subtype"] == "error"
        assert response["response"]["error"] == "Something went wrong"


class TestBackwardCompatibility:
    """Test backward compatibility with SDK API.

    The SDK now only supports subprocess mode. These tests verify
    that the API remains compatible.
    """

    def test_subprocess_mode_is_default(self) -> None:
        """Test that subprocess mode is the default and only mode."""
        options = RipperdocAgentOptions()
        # Client should have subprocess components initialized
        client = RipperdocSDKClient(options=options)
        assert hasattr(client, "_transport_options")
        assert client._transport is None  # Not connected yet
        assert client._query is None  # Not connected yet

    def test_options_work_with_all_parameters(self) -> None:
        """Test that options work with all parameters."""
        options = RipperdocAgentOptions(
            model="test-model",
            permission_mode="bypassPermissions",
            allowed_tools=["Bash"],
            max_turns=10,
        )

        assert options.model == "test-model"
        assert options.permission_mode == "bypassPermissions"
        assert options.allowed_tools == ["Bash"]
        assert options.max_turns == 10


class TestErrorHandling:
    """Test error handling in subprocess mode."""

    def test_message_parse_error_with_context(self) -> None:
        """Test MessageParseError includes context data."""
        data = {"type": "unknown"}
        with pytest.raises(MessageParseError) as exc_info:
            parse_message(data)

        # The error should include the data
        assert exc_info.value.data == data

    @pytest.mark.asyncio
    async def test_subprocess_connect_failure(self) -> None:
        """Test handling of subprocess connection failure."""
        options = RipperdocAgentOptions()

        # Mock transport that raises on connect
        class FailingTransport(Transport):
            def __init__(self, prompt: str = "", options: Any = None) -> None:
                self._connected = False
                self._ready = False

            async def connect(self) -> None:
                raise CLIConnectionError("Connection failed")

            async def write(self, data: str) -> None:
                pass

            def read_messages(self):
                return asyncio.Queue()

            async def close(self) -> None:
                pass

            def is_ready(self) -> bool:
                return False

            async def end_input(self) -> None:
                pass

        with patch(
            "ripperdoc_agent_sdk.client._subprocess_transport",
            FailingTransport
        ):
            client = RipperdocSDKClient(options=options)

            with pytest.raises(CLIConnectionError):
                await client._connect_subprocess()


class TestIntegration:
    """Integration tests for subprocess mode."""

    @pytest.mark.asyncio
    async def test_full_subprocess_flow_mocked(self) -> None:
        """Test full subprocess flow with mocked components."""
        options = RipperdocAgentOptions(
            model="test-model",
            permission_mode="default",
        )

        # Mock the transport
        mock_transport = MockTransport()

        # Mock the query
        mock_query = MagicMock()
        mock_query.start = AsyncMock()
        mock_query._send_control_request = AsyncMock(return_value={
            "response": {
                "session_id": "test-session",
            }
        })
        mock_query.close = AsyncMock()

        with patch("ripperdoc_agent_sdk.client._subprocess_transport", return_value=mock_transport):
            with patch("ripperdoc_agent_sdk.client._query_class", return_value=mock_query):
                client = RipperdocSDKClient(options=options)

                # Simulate connection
                await client._connect_subprocess()

                assert client._session_id == "test-session"
                assert client._query is not None

                # Simulate disconnect
                await client.disconnect()

                assert client._query is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
