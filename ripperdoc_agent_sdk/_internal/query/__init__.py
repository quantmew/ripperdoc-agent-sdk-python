"""Query class for handling bidirectional control protocol.

This module provides the Query class that coordinates message routing,
control protocol handling, queue management, and stream state management.

It uses anyio for cross-event-loop compatibility and clean async patterns.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from typing import Any

import anyio

from ripperdoc_agent_sdk._errors import MessageParseError
from ripperdoc_agent_sdk._internal.transport import Transport
from ripperdoc_agent_sdk._internal import message_parser
from ripperdoc_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    Message,
    ResultMessage,
    SystemMessage,
    ToolPermissionContext,
)
from ripperdoc_agent_sdk.protocol import (
    ControlInitializeRequest,
    ControlQueryRequest,
    ControlInterruptRequest,
    ControlSetPermissionModeRequest,
    ControlSetModelRequest,
    ControlRewindFilesRequest,
    model_to_dict,
)
from pydantic import BaseModel

from .queue_manager import MessageQueueManager
from .stream_manager import StreamManager
from .control_handler import ControlHandler
from .message_router import MessageRouter

logger = logging.getLogger(__name__)


class Query:
    """Handles bidirectional control protocol on top of Transport.

    This class coordinates the low-level control protocol communication with the CLI,
    delegating specific responsibilities to specialized manager classes.
    """

    def __init__(
        self,
        transport: Transport,
        is_streaming_mode: bool = True,
        can_use_tool: Callable[
            [str, dict[str, Any], ToolPermissionContext],
            Awaitable[PermissionResultAllow | PermissionResultDeny],
        ]
        | None = None,
        hooks: dict[str, list[dict[str, Any]]] | None = None,
        sdk_mcp_servers: dict[str, Any] | None = None,
        initialize_timeout: float = 60.0,
    ):
        """Initialize Query with transport and callbacks.

        Args:
            transport: Low-level transport for I/O
            is_streaming_mode: Whether using streaming (bidirectional) mode
            can_use_tool: Optional callback for tool permission requests
            hooks: Optional hook configurations
            sdk_mcp_servers: Optional SDK MCP server instances
            initialize_timeout: Timeout in seconds for the initialize request
        """
        self._initialize_timeout = initialize_timeout
        self.transport = transport
        self.is_streaming_mode = is_streaming_mode
        self.can_use_tool = can_use_tool
        self.hooks = hooks or {}
        self.sdk_mcp_servers = sdk_mcp_servers or {}

        # Message stream (using anyio memory object stream)
        self._message_send, self._message_receive = anyio.create_memory_object_stream[
            dict[str, Any]
        ](max_buffer_size=100)

        # Task group for concurrent operations
        self._tg: anyio.TaskGroup | None = None
        self._initialized = False
        self._initialization_result: dict[str, Any] | None = None
        self._request_counter = 0

        # Initialize managers (will be fully initialized in start())
        self._queue_manager = MessageQueueManager()
        self._stream_manager = StreamManager()
        self._control_handler: ControlHandler | None = None
        self._message_router: MessageRouter | None = None
        self._closed = False  # For backward compatibility

    async def start(self) -> None:
        """Start reading messages from transport."""
        if self._tg is None:
            # Initialize control handler and message router
            self._control_handler = ControlHandler(
                transport_send=self._send_via_transport,
                can_use_tool=self.can_use_tool,
                hook_callbacks={},  # Will be managed separately
                sdk_mcp_servers=self.sdk_mcp_servers,
            )

            self._message_router = MessageRouter(
                queue_manager_send=self._queue_manager.broadcast,
                control_request_handler=self._handle_control_request_wrapper,
            )

            self._tg = anyio.create_task_group()
            await self._tg.__aenter__()
            self._tg.start_soon(self._read_messages)

    async def _read_messages(self) -> None:
        """Background task that reads messages from transport and routes them."""
        try:
            message_count = 0
            async for message in self.transport.read_messages():
                if self._closed or self._stream_manager.is_closed:
                    logger.debug(
                        f"[_read_messages] Closed, stopping after {message_count} messages"
                    )
                    break

                msg_type = message.get("type")
                message_count += 1

                # Route message through the router
                if self._message_router:
                    is_routed = await self._message_router.route_message(message)

                    # If not a control message, broadcast to queues
                    if not is_routed:
                        await self._message_router.broadcast_to_queues(message)

                        # Also send to legacy stream
                        await self._message_send.send(message)

                        # Track results for proper stream closure
                        if msg_type == "result":
                            self._stream_manager.mark_first_result()

            logger.debug(f"[read_messages] Transport stream ended after {message_count} messages")

        except Exception as e:
            logger.error(f"Error in _read_messages: {e}")
            error_message = {"type": "error", "error": str(e)}
            if not self._closed and not self._stream_manager.is_closed:
                try:
                    await self._message_send.send(error_message)
                except Exception:
                    pass

            # Also send error to all queues
            if self._message_router:
                await self._message_router.broadcast_to_queues(error_message)

        finally:
            logger.debug("[read_messages] Message reading loop ended")
            # Note: We don't close _message_send here because it may still be used
            # for sending messages. It will be closed in the close() method.
            await self._queue_manager.close_all()

    async def _handle_control_request_wrapper(self, request: dict[str, Any]) -> None:
        """Wrapper for handling control requests via the control handler.

        Args:
            request: The control request message.
        """
        if self._control_handler and self._tg:
            await self._tg.start_soon(
                self._control_handler.handle_control_request,
                request,
                self._send_control_response,
            )

    async def _send_via_transport(self, data: str) -> None:
        """Send data via the transport.

        Args:
            data: The JSON string to send.
        """
        await self.transport.write(data + "\n")

    async def _send_control_request(
        self,
        request: dict[str, Any] | BaseModel,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a control request and wait for response.

        Args:
            request: The control request (dict or Pydantic model).
            timeout: Optional timeout in seconds.

        Returns:
            The response data.

        Raises:
            Exception: If the request results in an error.
        """
        self._request_counter += 1
        request_id = f"req_{self._request_counter}"

        # Convert Pydantic model to dict if needed
        if isinstance(request, BaseModel):
            request_dict = model_to_dict(request)
        else:
            request_dict = request

        # Build the control request message
        message = {
            "type": "control_request",
            "request_id": request_id,
            "request": request_dict,
        }

        if not self._message_router:
            raise RuntimeError("Message router not initialized. Call start() first.")

        # Register the pending request
        event = self._message_router.register_pending_request(request_id)

        try:
            # Send the request
            json_data = json.dumps(message)
            await self.transport.write(json_data + "\n")

            # Wait for response
            if timeout:
                with anyio.fail_after(timeout):
                    await event.wait()
            else:
                await event.wait()

            # Get result
            result = self._message_router.pop_pending_result(request_id)

            if isinstance(result, Exception):
                raise result

            return result

        finally:
            self._message_router.unregister_pending_request(request_id)

    async def _send_control_response(
        self,
        request_id: str,
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Send a control response to the CLI.

        Args:
            request_id: The request ID being responded to.
            response: Optional response data.
            error: Optional error message.
        """
        if error:
            response_data = {
                "subtype": "error",
                "request_id": request_id,
                "error": error,
            }
        else:
            response_data = {
                "subtype": "success",
                "request_id": request_id,
                "response": response,
            }

        message = {
            "type": "control_response",
            "response": response_data,
        }

        json_data = json.dumps(message)
        await self.transport.write(json_data + "\n")

    def receive_messages(self) -> AsyncIterator[Message]:
        """Receive messages from the CLI.

        This method creates a new message queue for each call to avoid
        multiple consumers competing for the same stream.

        Returns:
            An async iterator of Message objects.
        """
        return self._receive_messages_with_queue()

    async def _receive_messages_with_queue(self) -> AsyncIterator[Message]:
        """Receive messages using a per-call queue to avoid consumer competition.

        Yields:
            Message objects from the CLI.
        """
        queue_id, queue_send, queue_receive = self._queue_manager.create_queue_pair()

        try:
            message_count = 0
            async for msg_dict in queue_receive:
                message_count += 1
                logger.debug(
                    f"[_receive_messages_with_queue] {queue_id} received message "
                    f"{message_count}: {msg_dict.get('type')}"
                )
                if msg_dict is None:  # End of stream marker
                    break
                message = message_parser.parse_message(msg_dict)
                yield message
            logger.debug(
                f"[_receive_messages_with_queue] {queue_id} ended after "
                f"{message_count} messages"
            )
        finally:
            # Clean up
            logger.debug(f"[_receive_messages_with_queue] Cleaning up queue {queue_id}")
            self._queue_manager.unregister_queue(queue_id)
            await queue_send.aclose()
            await queue_receive.aclose()

    async def send_message(
        self,
        message_type: str,
        message_data: dict[str, Any],
    ) -> None:
        """Send a message to the CLI.

        Args:
            message_type: The type of message to send.
            message_data: The message data.
        """
        message = {
            "type": message_type,
            **message_data
        }

        await self._message_send.send(message)

    async def stream_input(self, stream: AsyncIterable[dict[str, Any]]) -> None:
        """Stream input messages to transport.

        If SDK MCP servers or hooks are present, waits for the first result
        before closing stdin to allow bidirectional control protocol communication.

        Args:
            stream: Async iterable of message dictionaries to send.
        """
        try:
            async for message in stream:
                if self._closed or self._stream_manager.is_closed:
                    break
                await self.transport.write(json.dumps(message) + "\n")

            # If we have SDK MCP servers or hooks that need bidirectional communication,
            # wait for first result before closing the channel
            has_hooks = bool(self.hooks)
            if self.sdk_mcp_servers or has_hooks:
                logger.debug(
                    f"Waiting for first result before closing stdin "
                    f"(sdk_mcp_servers={len(self.sdk_mcp_servers)}, has_hooks={has_hooks})"
                )
                await self._stream_manager.wait_for_first_result()
                logger.debug("Received first result, closing input stream")

            # After all messages sent (and result received if needed), end input
            if hasattr(self.transport, 'end_input'):
                await self.transport.end_input()
        except Exception as e:
            logger.debug(f"Error streaming input: {e}")

    # Hook callback management
    @property
    def hook_callbacks(self) -> dict[str, Callable[..., Awaitable[dict[str, Any]]]]:
        """Get the hook callbacks dictionary.

        This is provided for backward compatibility.
        """
        if self._control_handler:
            # Access internal dict (not ideal but maintains compatibility)
            return self._control_handler._hook_callbacks
        return {}

    def register_hook_callback(
        self,
        callback_id: str,
        callback: Callable[..., Awaitable[dict[str, Any]]],
    ) -> None:
        """Register a hook callback.

        Args:
            callback_id: Unique identifier for the callback.
            callback: The async callback function.
        """
        if self._control_handler:
            self._control_handler.register_hook_callback(callback_id, callback)

    # Control protocol convenience methods
    async def set_permission_mode(self, mode: str) -> None:
        """Change permission mode during conversation.

        Args:
            mode: The permission mode to set.
        """
        request = ControlSetPermissionModeRequest(mode=mode)
        await self._send_control_request(request)

    async def set_model(self, model: str | None = None) -> None:
        """Change the AI model during conversation.

        Args:
            model: The model to switch to.
        """
        request = ControlSetModelRequest(model=model)
        await self._send_control_request(request)

    async def interrupt(self) -> None:
        """Interrupt the current query."""
        request = ControlInterruptRequest()
        await self._send_control_request(request)

    async def rewind_files(self, user_message_id: str) -> None:
        """Rewind tracked files to their state at a specific user message.

        Args:
            user_message_id: The ID of the user message to rewind to.
        """
        request = ControlRewindFilesRequest(user_message_id=user_message_id)
        await self._send_control_request(request)

    async def close(self) -> None:
        """Close the query and clean up resources."""
        self._closed = True
        self._stream_manager.mark_closed()

        # Close transport stdin to signal subprocess to exit
        # This unblocks _read_messages which is waiting for messages
        if hasattr(self.transport, 'end_input'):
            try:
                await self.transport.end_input()
            except Exception:
                pass  # Ignore errors during shutdown

        # Close message stream
        await self._message_send.aclose()
        await self._message_receive.aclose()

        # Close task group if active
        if self._tg:
            await self._tg.__aexit__(None, None, None)
            self._tg = None


# Re-export parse_message for convenience
parse_message = message_parser.parse_message

__all__ = [
    "Query",
    "parse_message",
]
