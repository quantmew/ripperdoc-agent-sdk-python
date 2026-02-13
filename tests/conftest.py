"""Pytest configuration and fixtures."""

import pytest

from ripperdoc_agent_sdk import RipperdocAgentOptions


@pytest.fixture
def default_options():
    """Default RipperdocAgentOptions for testing."""
    return RipperdocAgentOptions()


@pytest.fixture
def test_prompt():
    """Sample prompt for testing."""
    return "What is 2 + 2?"
