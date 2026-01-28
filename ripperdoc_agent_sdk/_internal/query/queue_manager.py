"""Message queue manager for handling multiple message consumers.

This module manages the registration, broadcasting, and cleanup of message queues
used by the Query class to support multiple concurrent message consumers.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import anyio

logger = logging.getLogger(__name__)


# Field name mapping for converting Python-safe names to CLI format
_FIELD_NAME_MAPPING = {
    "async_": "async",
    "continue_": "continue",
}


def convert_hook_output_for_cli(hook_output: dict[str, Any]) -> dict[str, Any]:
    """Convert Python-safe field names to CLI-expected field names.

    The Python SDK uses `async_` and `continue_` to avoid keyword conflicts,
    but the CLI expects `async` and `continue`.

    Args:
        hook_output: Dictionary with Python-safe field names.

    Returns:
        Dictionary with CLI-expected field names.
    """
    return {
        _FIELD_NAME_MAPPING.get(k, k): v
        for k, v in hook_output.items()
    }


class MessageQueueManager:
    """Manages message queues for multiple concurrent consumers.

    This class handles:
    - Registration of message queues
    - Broadcasting messages to all registered queues
    - Cleanup of closed queues
    - Graceful shutdown of all queues
    """

    def __init__(self) -> None:
        """Initialize the queue manager."""
        self._queues: dict[str, anyio.MemoryObjectStreamSend[Any]] = {}
        self._request_counter = 0

    @property
    def queue_count(self) -> int:
        """Return the number of registered queues."""
        return len(self._queues)

    def register_queue(
        self,
        queue_send: anyio.MemoryObjectStreamSend[Any],
    ) -> str:
        """Register a new message queue.

        Args:
            queue_send: The send end of the memory object stream.

        Returns:
            The unique queue ID assigned to this queue.
        """
        self._request_counter += 1
        queue_id = f"recv_{self._request_counter}"
        self._queues[queue_id] = queue_send
        logger.debug(
            f"[MessageQueueManager] Registered queue {queue_id}, "
            f"total queues: {self.queue_count}"
        )
        return queue_id

    def unregister_queue(self, queue_id: str) -> None:
        """Unregister a message queue.

        Args:
            queue_id: The ID of the queue to unregister.
        """
        if queue_id in self._queues:
            del self._queues[queue_id]
            logger.debug(
                f"[MessageQueueManager] Unregistered queue {queue_id}, "
                f"total queues: {self.queue_count}"
            )

    async def broadcast(
        self,
        message: dict[str, Any] | None,
    ) -> None:
        """Broadcast a message to all registered queues.

        Automatically removes any queues that are closed or raise errors.

        Args:
            message: The message to broadcast. If None, signals end of stream.
        """
        if not self._queues:
            return

        msg_type = message.get("type") if message else "None"
        logger.debug(
            f"[MessageQueueManager] Broadcasting {msg_type} to {self.queue_count} queues"
        )

        # Create a list of items to avoid modifying dict during iteration
        queues_to_process = list(self._queues.items())

        for queue_id, queue_send in queues_to_process:
            try:
                await queue_send.send(message)
                logger.debug(f"[MessageQueueManager] Sent to queue {queue_id}")
            except Exception as e:
                # Queue is closed or error occurred, remove it
                logger.debug(
                    f"[MessageQueueManager] Queue {queue_id} closed, removing: {e}"
                )
                self._queues.pop(queue_id, None)

    async def close_all(self) -> None:
        """Close all registered queues.

        Sends None to each queue to signal end of stream, then closes
        the send streams.
        """
        logger.debug(f"[MessageQueueManager] Closing {self.queue_count} queues")

        queues_to_close = list(self._queues.items())

        for queue_id, queue_send in queues_to_close:
            try:
                # Send end of stream marker
                await queue_send.send(None)
                logger.debug(f"[MessageQueueManager] Sent None to queue {queue_id}")
            except Exception:
                # Queue might already be closed
                pass
            finally:
                # Always close the queue send stream
                try:
                    await queue_send.aclose()
                except Exception:
                    pass

        self._queues.clear()

    def create_queue_pair(
        self,
        max_buffer_size: int = 1000,
    ) -> tuple[str, anyio.MemoryObjectStreamSend[Any], anyio.MemoryObjectStreamReceive[Any]]:
        """Create a new queue pair and register it.

        Args:
            max_buffer_size: Maximum buffer size for the queue.

        Returns:
            A tuple of (queue_id, send_stream, receive_stream).
        """
        queue_send, queue_receive = anyio.create_memory_object_stream[
            dict[str, Any] | None
        ](max_buffer_size=max_buffer_size)

        queue_id = self.register_queue(queue_send)

        return queue_id, queue_send, queue_receive


__all__ = [
    "MessageQueueManager",
    "convert_hook_output_for_cli",
]
