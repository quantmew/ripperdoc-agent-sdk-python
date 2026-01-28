"""Stream state manager for handling stream lifecycle and timing.

This module manages the state related to stream closure timing,
particularly for SDK MCP servers and hooks that require bidirectional
communication.
"""

from __future__ import annotations

import logging
import os
from typing import Final

import anyio

logger = logging.getLogger(__name__)


# Configuration constants
DEFAULT_STREAM_CLOSE_TIMEOUT_MS: Final = 60000
ENV_STREAM_CLOSE_TIMEOUT_KEY: Final = "RIPPERDOC_STREAM_CLOSE_TIMEOUT"


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
            timeout_ms = float(
                os.environ.get(
                    ENV_STREAM_CLOSE_TIMEOUT_KEY,
                    DEFAULT_STREAM_CLOSE_TIMEOUT_MS,
                )
            )
            stream_close_timeout = timeout_ms / 1000.0  # Convert ms to seconds

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
        """
        timeout = timeout if timeout is not None else self._stream_close_timeout

        logger.debug(
            f"[StreamManager] Waiting for first result "
            f"(timeout={timeout}s)"
        )

        try:
            with anyio.move_on_after(timeout):
                await self._first_result_event.wait()
                logger.debug("[StreamManager] First result received")
                return True
        except Exception:
            logger.debug("[StreamManager] Timed out waiting for first result")

        return False

    def reset(self) -> None:
        """Reset the stream manager state.

        This is useful for reusing the stream manager for multiple streams.
        """
        self._first_result_event = anyio.Event()
        self._closed = False
        logger.debug("[StreamManager] Stream manager reset")


__all__ = [
    "StreamManager",
    "DEFAULT_STREAM_CLOSE_TIMEOUT_MS",
    "ENV_STREAM_CLOSE_TIMEOUT_KEY",
]
