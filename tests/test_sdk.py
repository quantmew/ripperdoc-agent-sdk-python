"""Tests for the headless SDK.

This test module covers basic SDK functionality including:
- Import verification
- Options creation and configuration
- Client initialization
- Properties and methods
"""

import asyncio
import pytest

from ripperdoc_agent_sdk import (
    RipperdocClient,
    RipperdocSDKClient,
    RipperdocAgentOptions,
    query as sdk_query,
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
)
from ripperdoc_agent_sdk.client import McpServerConfig, AgentConfig, HookMatcher, PermissionMode


class TestSDKImports:
    """Test that basic SDK imports work."""

    def test_sdk_imports_work(self):
        """Test that basic SDK imports work."""
        # Verify aliases work
        assert RipperdocClient is RipperdocSDKClient


class TestOptions:
    """Test RipperdocAgentOptions configuration."""

    def test_options_can_be_created(self):
        """Test that options can be created."""
        options = RipperdocAgentOptions(
            allowed_tools=["Bash", "Read", "Task"],
            permission_mode="bypassPermissions",
        )
        assert options.allowed_tools == ["Bash", "Read", "Task"]
        assert options.permission_mode == "bypassPermissions"

    def test_options_yolo_mode_deprecation(self):
        """Test that yolo_mode still works but sets permission_mode."""
        with pytest.warns(DeprecationWarning, match="yolo_mode is deprecated"):
            options = RipperdocAgentOptions(yolo_mode=True)
            assert options.permission_mode == "bypassPermissions"

    def test_options_with_all_parameters(self):
        """Test that options work with all parameters."""
        options = RipperdocAgentOptions(
            model="test-model",
            permission_mode="bypassPermissions",
            allowed_tools=["Bash"],
            max_turns=10,
            cli_path="/path/to/ripperdoc",
            cwd="/test/path",
        )

        assert options.model == "test-model"
        assert options.permission_mode == "bypassPermissions"
        assert options.allowed_tools == ["Bash"]
        assert options.max_turns == 10
        assert options.cli_path == "/path/to/ripperdoc"

    def test_options_extra_instructions(self):
        """Test that extra_instructions returns a list."""
        options = RipperdocAgentOptions(
            additional_instructions="Instruction 1"
        )
        assert options.extra_instructions() == ["Instruction 1"]

        options = RipperdocAgentOptions(
            additional_instructions=["Instruction 1", "Instruction 2"]
        )
        assert options.extra_instructions() == ["Instruction 1", "Instruction 2"]


class TestClient:
    """Test RipperdocSDKClient functionality."""

    def test_client_can_be_created(self):
        """Test that client can be created."""
        options = RipperdocAgentOptions()
        client = RipperdocSDKClient(options=options)
        assert client.options == options
        assert client._connected is False

    def test_client_properties(self):
        """Test that client properties work."""
        options = RipperdocAgentOptions(
            model="test-model",
            user="test-user",
        )
        client = RipperdocSDKClient(options=options)

        assert client.session_id is None
        assert client.turn_count == 0
        assert client.user == "test-user"
        assert client.history == []

    def test_client_has_subprocess_components(self):
        """Test that client has subprocess components initialized."""
        options = RipperdocAgentOptions()
        client = RipperdocSDKClient(options=options)

        # Subprocess components should be initialized
        assert hasattr(client, "_transport_options")
        assert hasattr(client, "_transport")
        assert hasattr(client, "_query")

    def test_build_transport_options(self):
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


class TestMessageTypes:
    """Test message type definitions."""

    def test_user_message_creation(self):
        """Test creating a UserMessage."""
        msg = UserMessage(content="Hello, world!")
        assert msg.content == "Hello, world!"
        assert msg.uuid is None

    def test_assistant_message_creation(self):
        """Test creating an AssistantMessage."""
        msg = AssistantMessage(
            content=[TextBlock(text="Response")],
            model="model-name",
        )
        assert msg.model == "model-name"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)

    def test_system_message_creation(self):
        """Test creating a SystemMessage."""
        msg = SystemMessage(
            subtype="progress",
            data={"key": "value"},
        )
        assert msg.subtype == "progress"
        assert msg.data == {"key": "value"}

    def test_result_message_creation(self):
        """Test creating a ResultMessage."""
        msg = ResultMessage(
            subtype="result",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=2,
            session_id="test-session",
        )
        assert msg.duration_ms == 1000
        assert msg.is_error is False
        assert msg.session_id == "test-session"


class TestMcpServerConfig:
    """Test McpServerConfig class."""

    def test_stdio_server_config(self):
        """Test stdio MCP server configuration."""
        config = McpServerConfig(
            type="stdio",
            command="server-command",
            args=["--arg1"],
        )
        typed = config.to_typed_dict()
        assert typed["type"] == "stdio"
        assert typed["command"] == "server-command"

    def test_sse_server_config(self):
        """Test SSE MCP server configuration."""
        config = McpServerConfig(
            type="sse",
            url="https://example.com/sse",
        )
        typed = config.to_typed_dict()
        assert typed["type"] == "sse"
        assert typed["url"] == "https://example.com/sse"

    def test_http_server_config(self):
        """Test HTTP MCP server configuration."""
        config = McpServerConfig(
            type="http",
            url="https://example.com",
        )
        typed = config.to_typed_dict()
        assert typed["type"] == "http"
        assert typed["url"] == "https://example.com"


class TestAgentConfig:
    """Test AgentConfig class."""

    def test_agent_config_creation(self):
        """Test creating an AgentConfig."""
        config = AgentConfig(
            description="Test agent",
            prompt="You are a test agent",
            tools=["Bash", "Read"],
        )
        assert config.description == "Test agent"
        assert config.prompt == "You are a test agent"
        assert config.tools == ["Bash", "Read"]

    def test_agent_config_to_definition(self):
        """Test converting AgentConfig to AgentDefinition."""
        config = AgentConfig(
            description="Test agent",
            prompt="You are a test agent",
            model="sonnet",
        )
        definition = config.to_agent_definition()
        assert definition.description == "Test agent"
        assert definition.prompt == "You are a test agent"
        assert definition.model == "sonnet"


class TestHookMatcher:
    """Test HookMatcher class."""

    def test_hook_matcher_creation(self):
        """Test creating a HookMatcher."""
        def my_callback(event_type: str, data: dict) -> dict:
            return {"continue_": True}

        matcher = HookMatcher(
            callback=my_callback,
            tool_pattern="Bash*",
        )
        assert matcher.callback == my_callback
        assert matcher.tool_pattern == "Bash*"


class TestPermissionModes:
    """Test permission mode."""

    def test_permission_mode(self):
        """Test PermissionMode class."""
        assert PermissionMode.DEFAULT == "default"
        assert PermissionMode.ACCEPT_EDITS == "acceptEdits"
        assert PermissionMode.BYPASS_PERMISSIONS == "bypassPermissions"
        assert PermissionMode.PLAN == "plan"

    def test_permission_mode_is_valid(self):
        """Test PermissionMode.is_valid method."""
        assert PermissionMode.is_valid("default")
        assert PermissionMode.is_valid("acceptEdits")
        assert PermissionMode.is_valid("bypassPermissions")
        assert PermissionMode.is_valid("plan")
        assert not PermissionMode.is_valid("invalid")


class TestRegistries:
    """Test programmatic registry functions."""

    def test_get_programmatic_agents(self):
        """Test getting programmatic agents registry."""
        from ripperdoc_agent_sdk import get_programmatic_agents

        agents = get_programmatic_agents()
        assert isinstance(agents, dict)

    def test_get_programmatic_hooks(self):
        """Test getting programmatic hooks registry."""
        from ripperdoc_agent_sdk import get_programmatic_hooks

        hooks = get_programmatic_hooks()
        assert isinstance(hooks, dict)

    def test_clear_programmatic_registries(self):
        """Test clearing programmatic registries."""
        from ripperdoc_agent_sdk import (
            get_programmatic_agents,
            get_programmatic_hooks,
            clear_programmatic_registries,
        )

        # Clear should work without error
        clear_programmatic_registries()

        # Registries should be empty
        assert get_programmatic_agents() == {}
        assert get_programmatic_hooks() == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
