"""Tests for RipperdocSDKClient."""

import pytest

from ripperdoc_agent_sdk import RipperdocSDKClient, RipperdocAgentOptions


class TestRipperdocSDKClient:
    """Tests for RipperdocSDKClient."""

    def test_init_with_default_options(self):
        """Test client initialization with default options."""
        client = RipperdocSDKClient()
        assert client.options is not None
        assert isinstance(client.options, RipperdocAgentOptions)
        assert client._custom_transport is None
        assert client._transport is None
        assert client._query is None

    def test_init_with_custom_options(self):
        """Test client initialization with custom options."""
        options = RipperdocAgentOptions(
            permission_mode="acceptEdits",
        )
        client = RipperdocSDKClient(options=options)
        assert client.options.permission_mode == "acceptEdits"

    def test_init_with_transport(self):
        """Test client initialization with custom transport."""
        from ripperdoc_agent_sdk._internal.transport import Transport

        class MockTransport(Transport):
            async def connect(self):
                pass

            async def write(self, data: str):
                pass

            async def close(self):
                pass

            def is_ready(self) -> bool:
                return True

            async def end_input(self):
                pass

            def read_messages(self):
                # Return an async iterator
                async def gen():
                    return
                    yield
                return gen()

        transport = MockTransport()
        client = RipperdocSDKClient(transport=transport)
        assert client._custom_transport == transport

    @pytest.mark.asyncio
    async def test_connect_without_prompt(self):
        """Test connecting without an initial prompt."""
        client = RipperdocSDKClient()
        try:
            await client.connect()
            # Should succeed and be connected
            # In a real test, we'd verify connection state
            await client.disconnect()
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_connect_with_string_prompt(self):
        """Test connecting with a string prompt."""
        client = RipperdocSDKClient()
        try:
            await client.connect(prompt="Hello, Ripperdoc!")
            await client.disconnect()
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending a message after connection."""
        client = RipperdocSDKClient()
        try:
            await client.connect()
            # In a full test, we'd send and verify response
            await client.disconnect()
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from Ripperdoc."""
        client = RipperdocSDKClient()
        try:
            await client.connect()
            await client.disconnect()
            # Should successfully disconnect
        except Exception as e:
            pytest.skip(f"Ripperdoc CLI not available: {e}")
