"""Tests for type definitions."""

import pytest

from ripperdoc_agent_sdk.types import (
    AgentDefinition,
    PermissionRuleValue,
    PermissionUpdate,
    PermissionUpdateDestination,
    SystemPromptPreset,
    ToolsPreset,
)


class TestPermissionUpdateDestination:
    """Tests for PermissionUpdateDestination literal."""

    def test_valid_destinations(self):
        """Test valid permission update destinations."""
        valid: list[PermissionUpdateDestination] = [
            "userSettings",
            "projectSettings",
            "localSettings",
            "session",
        ]
        assert len(valid) == 4


class TestSystemPromptPreset:
    """Tests for SystemPromptPreset TypedDict."""

    def test_minimal_preset(self):
        """Test minimal system prompt preset."""
        preset: SystemPromptPreset = {
            "type": "preset",
            "preset": "ripperdoc_code",
        }
        assert preset["type"] == "preset"
        assert preset["preset"] == "ripperdoc_code"

    def test_preset_with_append(self):
        """Test system prompt preset with append."""
        preset: SystemPromptPreset = {
            "type": "preset",
            "preset": "ripperdoc_code",
            "append": "Additional instructions",
        }
        assert preset["append"] == "Additional instructions"


class TestToolsPreset:
    """Tests for ToolsPreset TypedDict."""

    def test_tools_preset(self):
        """Test tools preset."""
        preset: ToolsPreset = {
            "type": "preset",
            "preset": "ripperdoc_code",
        }
        assert preset["type"] == "preset"
        assert preset["preset"] == "ripperdoc_code"


class TestAgentDefinition:
    """Tests for AgentDefinition dataclass."""

    def test_minimal_agent(self):
        """Test minimal agent definition."""
        agent = AgentDefinition(
            description="Test agent",
            prompt="You are a test agent",
        )
        assert agent.description == "Test agent"
        assert agent.prompt == "You are a test agent"
        assert agent.tools is None
        assert agent.model is None

    def test_agent_with_tools(self):
        """Test agent definition with tools."""
        agent = AgentDefinition(
            description="Test agent",
            prompt="You are a test agent",
            tools=["bash", "edit"],
        )
        assert agent.tools == ["bash", "edit"]

    def test_agent_with_model(self):
        """Test agent definition with model."""
        agent = AgentDefinition(
            description="Test agent",
            prompt="You are a test agent",
            model="sonnet",
        )
        assert agent.model == "sonnet"

    def test_agent_with_all_fields(self):
        """Test agent definition with all fields."""
        agent = AgentDefinition(
            description="Full agent",
            prompt="Full prompt",
            tools=["bash", "edit", "grep"],
            model="opus",
        )
        assert agent.description == "Full agent"
        assert agent.prompt == "Full prompt"
        assert agent.tools == ["bash", "edit", "grep"]
        assert agent.model == "opus"


class TestPermissionRuleValue:
    """Tests for PermissionRuleValue dataclass."""

    def test_minimal_rule(self):
        """Test minimal permission rule."""
        rule = PermissionRuleValue(tool_name="bash")
        assert rule.tool_name == "bash"
        assert rule.rule_content is None

    def test_rule_with_content(self):
        """Test permission rule with content."""
        rule = PermissionRuleValue(
            tool_name="edit",
            rule_content="allow",
        )
        assert rule.tool_name == "edit"
        assert rule.rule_content == "allow"


class TestPermissionUpdate:
    """Tests for PermissionUpdate dataclass."""

    def test_add_rules(self):
        """Test add rules permission update."""
        update = PermissionUpdate(
            type="addRules",
            rules=[
                PermissionRuleValue(tool_name="bash"),
                PermissionRuleValue(tool_name="edit"),
            ],
        )
        assert update.type == "addRules"
        assert len(update.rules) == 2

    def test_replace_rules(self):
        """Test replace rules permission update."""
        update = PermissionUpdate(
            type="replaceRules",
            rules=[PermissionRuleValue(tool_name="bash")],
        )
        assert update.type == "replaceRules"

    def test_remove_rules(self):
        """Test remove rules permission update."""
        update = PermissionUpdate(
            type="removeRules",
            rules=[PermissionRuleValue(tool_name="bash")],
        )
        assert update.type == "removeRules"

    def test_set_mode(self):
        """Test set mode permission update."""
        update = PermissionUpdate(type="setMode")
        assert update.type == "setMode"

    def test_add_directories(self):
        """Test add directories permission update."""
        update = PermissionUpdate(type="addDirectories")
        assert update.type == "addDirectories"

    def test_remove_directories(self):
        """Test remove directories permission update."""
        update = PermissionUpdate(type="removeDirectories")
        assert update.type == "removeDirectories"
