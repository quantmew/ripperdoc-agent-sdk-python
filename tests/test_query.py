"""Tests for query function."""

from collections.abc import AsyncIterator

import pytest

from ripperdoc_agent_sdk import query, RipperdocAgentOptions
from ripperdoc_agent_sdk.types import Message, AssistantMessage


class TestQuery:
    """Tests for query function."""

    @pytest.mark.asyncio
    async def test_query_returns_iterator(self):
        """Test that query returns an async iterator."""
        # Just verify the interface, don't actually connect
        result = query(prompt="test")
        assert hasattr(result, "__aiter__")
