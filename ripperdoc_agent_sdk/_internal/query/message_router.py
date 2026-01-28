"""Message router for handling incoming message routing and dispatch.

This module contains the logic for routing incoming messages from the transport
to appropriate handlers based on message type.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any

import anyio

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes incoming messages to appropriate handlers.

    This class handles:
    - Routing control responses to pending request handlers
    - Dispatching control requests to the control handler
    - Broadcasting regular messages to queue manager
    - Tracking message counts and errors
    """

    def __init__(
        self,
        queue_manager_send: Callable[[dict[str, Any] | None], Awaitable[None]],
        control_request_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize the message router.

        Args:
            queue_manager_send: Async function to broadcast to queue manager.
            control_request_handler: Optional async function to handle control requests.
        """
        self._queue_manager_send = queue_manager_send
        self._control_request_handler = control_request_handler

        # Pending control response tracking
        self._pending_control_responses: dict[str, anyio.Event] = {}
        self._pending_control_results: dict[str, dict[str, Any] | Exception] = {}

    def set_control_request_handler(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Set the control request handler.

        Args:
            handler: Async function to handle control requests.
        """
        self._control_request_handler = handler

    async def route_message(
        self,
        message: dict[str, Any],
    ) -> bool:
        """Route an incoming message to the appropriate handler.

        Args:
            message: The message to route.

        Returns:
            True if the message was routed (not a regular stream message),
            False if it should be handled as a regular stream message.
        """
        msg_type = message.get("type")

        # Route control responses
        if msg_type == "control_response":
            await self._handle_control_response(message)
            return True

        # Route control requests (from CLI to SDK)
        if msg_type == "control_request":
            await self._handle_control_request(message)
            return True

        # Regular stream messages will be handled by caller
        return False

    async def _handle_control_response(
        self,
        message: dict[str, Any],
    ) -> None:
        """Handle a control response message.

        Args:
            message: The control response message.
        """
        response = message.get("response", {})
        request_id = response.get("request_id")

        if request_id in self._pending_control_responses:
            event = self._pending_control_responses[request_id]
            if response.get("subtype") == "error":
                self._pending_control_results[request_id] = Exception(
                    response.get("error", "Unknown error")
                )
            else:
                self._pending_control_results[request_id] = response
            event.set()
        else:
            logger.debug(
                f"[MessageRouter] Received response for unknown request_id: {request_id}"
            )

    async def _handle_control_request(
        self,
        message: dict[str, Any],
    ) -> None:
        """Handle a control request message.

        Args:
            message: The control request message.
        """
        if self._control_request_handler:
            await self._control_request_handler(message)
        else:
            logger.warning(
                "[MessageRouter] Received control request but no handler registered"
            )

    def register_pending_request(
        self,
        request_id: str,
    ) -> anyio.Event:
        """Register a pending control request.

        Args:
            request_id: The unique request ID.

        Returns:
            An event that will be set when the response arrives.
        """
        event = anyio.Event()
        self._pending_control_responses[request_id] = event
        return event

    def set_pending_result(
        self,
        request_id: str,
        result: dict[str, Any] | Exception,
    ) -> None:
        """Set the result for a pending request.

        Args:
            request_id: The request ID.
            result: The result (response dict or Exception).
        """
        self._pending_control_results[request_id] = result

    def pop_pending_result(
        self,
        request_id: str,
    ) -> dict[str, Any] | Exception:
        """Pop and return the result for a pending request.

        Args:
            request_id: The request ID.

        Returns:
            The result (response dict or Exception).

        Raises:
            KeyError: If no result is found for the request_id.
        """
        return self._pending_control_results.pop(request_id)

    def unregister_pending_request(
        self,
        request_id: str,
    ) -> anyio.Event | None:
        """Unregister a pending control request.

        Args:
            request_id: The request ID.

        Returns:
            The event if it was registered, None otherwise.
        """
        return self._pending_control_responses.pop(request_id, None)

    async def broadcast_to_queues(
        self,
        message: dict[str, Any] | None,
    ) -> None:
        """Broadcast a message to all registered queues.

        Args:
            message: The message to broadcast (or None for end of stream).
        """
        await self._queue_manager_send(message)


__all__ = [
    "MessageRouter",
]
