"""Stream state manager for handling stream lifecycle and timing.

This module manages the state related to stream closure timing,
particularly for SDK MCP servers and hooks that require bidirectional
communication.
"""

from __future__ import annotations

import logging

import anyio

from ripperdoc_agent_sdk._errors import RipperdocSDKError, StreamError, StreamTimeoutError
from ripperdoc_agent_sdk.config import StreamConfig

logger = logging.getLogger(__name__)


class StreamManager:
    """Manages stream state and timing for message streams.

    This class handles:
    - First result tracking for proper stream closure
    - Stream close timeout configuration
    - Waiting for first result before closing input
    """

    def __init__(
        self,
        stream_close_timeout: float | None = None,
    ) -> None:
        """Initialize the stream manager.

        Args:
            stream_close_timeout: Timeout in seconds for waiting for first result.
                If None, uses default from environment or built-in default.
        """
        if stream_close_timeout is None:
            stream_close_timeout = StreamConfig.get_close_timeout()

        self._stream_close_timeout = stream_close_timeout
        self._first_result_event = anyio.Event()
        self._closed = False

    @property
    def stream_close_timeout(self) -> float:
        """Return the stream close timeout in seconds."""
        return self._stream_close_timeout

    @property
    def is_closed(self) -> bool:
        """Return whether the stream is marked as closed."""
        return self._closed

    def mark_first_result(self) -> None:
        """Mark that the first result has been received."""
        self._first_result_event.set()
        logger.debug("[StreamManager] First result marked")

    def mark_closed(self) -> None:
        """Mark the stream as closed."""
        self._closed = True
        logger.debug("[StreamManager] Stream marked as closed")

    async def wait_for_first_result(
        self,
        timeout: float | None = None,
    ) -> bool:
        """Wait for the first result to be received.

        Args:
            timeout: Optional timeout override in seconds.
                If None, uses the configured stream_close_timeout.

        Returns:
            True if first result was received, False if timeout occurred.

        Raises:
            StreamTimeoutError: If timeout occurs and raise_on_timeout is True.
        """
        timeout = timeout if timeout is not None else self._stream_close_timeout

        logger.debug(
            f"[StreamManager] Waiting for first result "
            f"(timeout={timeout}s)"
        )

        try:
            with anyio.move_on_after(timeout) as scope:
                await self._first_result_event.wait()
                if not scope.cancel_called:
                    logger.debug("[StreamManager] First result received")
                    return True

            # Timeout occurred
            logger.debug("[StreamManager] Timed out waiting for first result")
            return False

        except anyio.get_cancelled_exc_class():
            # Task cancellation - expected during shutdown
            logger.debug("[StreamManager] Cancelled while waiting for first result")
            raise

    def reset(self) -> None:
        """Reset the stream manager state.

        This is useful for reusing the stream manager for multiple streams.
        """
        self._first_result_event = anyio.Event()
        self._closed = False
        logger.debug("[StreamManager] Stream manager reset")


__all__ = [
    "StreamManager",
]
