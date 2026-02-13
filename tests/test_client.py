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
