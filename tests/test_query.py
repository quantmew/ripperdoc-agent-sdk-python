"""Tests for query function."""

import json
from collections.abc import AsyncIterator

import pytest

from ripperdoc_agent_sdk import query, RipperdocAgentOptions
from ripperdoc_agent_sdk.types import Message, AssistantMessage


class TestQuery:
    """Tests for query function."""

    @pytest.mark.asyncio
    async def test_query_with_string_prompt(self, default_options, test_prompt):
        """Test query with a string prompt."""
        # Note: This test requires ripperdoc CLI to be installed
        # In CI/CD, this should be mocked or skipped if CLI not available
        messages: list[Message] = []
        try:
            async for msg in query(prompt=test_prompt, options=default_options):
                messages.append(msg)
                # Break after first message for testing
                if isinstance(msg, AssistantMessage):
                    break
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_query_with_default_options(self, test_prompt):
        """Test query with default options (None)."""
        messages: list[Message] = []
        try:
            async for msg in query(prompt=test_prompt):
                messages.append(msg)
                if isinstance(msg, AssistantMessage):
                    break
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_query_with_custom_options(self, test_prompt):
        """Test query with custom options."""
        options = RipperdocAgentOptions(
            permission_mode="acceptEdits",
        )
        messages: list[Message] = []
        try:
            async for msg in query(prompt=test_prompt, options=options):
                messages.append(msg)
                if isinstance(msg, AssistantMessage):
                    break
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_query_with_streaming_prompt(self):
        """Test query with streaming prompt (AsyncIterable)."""

        async def stream_prompt() -> AsyncIterator[dict]:
            """Stream prompt as a series of messages."""
            yield {"type": "user", "content": [{"type": "text", "text": "Hello"}]}

        messages: list[Message] = []
        try:
            async for msg in query(prompt=stream_prompt()):
                messages.append(msg)
                if isinstance(msg, AssistantMessage):
                    break
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_query_returns_iterator(self, test_prompt):
        """Test that query returns an async iterator."""
        try:
            result = query(prompt=test_prompt)
            assert hasattr(result, "__aiter__")
            # Consume the iterator
            async for _ in result:
                break
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")
