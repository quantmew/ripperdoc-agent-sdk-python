"""Query class for handling bidirectional control protocol.

This module implements the Query class that manages:
- Control request/response routing
- Hook callbacks
- Tool permission callbacks
- Message streaming
- Initialization handshake

It uses anyio for cross-event-loop compatibility and clean async patterns.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any

import anyio

from ripperdoc_agent_sdk._errors import MessageParseError
from ripperdoc_agent_sdk._internal.transport import Transport
from ripperdoc_agent_sdk._internal import message_parser
from ripperdoc_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    Message,
    SystemMessage,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)


def _convert_hook_output_for_cli(hook_output: dict[str, Any]) -> dict[str, Any]:
    """Convert Python-safe field names to CLI-expected field names.

    The Python SDK uses `async_` and `continue_` to avoid keyword conflicts,
    but the CLI expects `async` and `continue`. This function performs the
    necessary conversion.
    """
    converted = {}
    for key, value in hook_output.items():
        # Convert Python-safe names to JavaScript names
        if key == "async_":
            converted["async"] = value
        elif key == "continue_":
            converted["continue"] = value
        else:
            converted[key] = value
    return converted


class Query:
    """Handles bidirectional control protocol on top of Transport.

    This class manages the low-level control protocol communication with the CLI.
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

        # Control protocol state
        self.pending_control_responses: dict[str, anyio.Event] = {}
        self.pending_control_results: dict[str, dict[str, Any] | Exception] = {}
        self.hook_callbacks: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}
        self.next_callback_id = 0
        self._request_counter = 0

        # Message stream (using anyio memory object stream)
        self._message_send, self._message_receive = anyio.create_memory_object_stream[
            dict[str, Any]
        ](max_buffer_size=100)

        # Task group for concurrent operations
        self._tg: anyio.TaskGroup | None = None
        self._initialized = False
        self._closed = False
        self._initialization_result: dict[str, Any] | None = None

        # Track first result for proper stream closure with SDK MCP servers
        self._first_result_event = anyio.Event()
        self._stream_close_timeout = (
            float(os.environ.get("RIPPERDOC_STREAM_CLOSE_TIMEOUT", "60000")) / 1000.0
        )  # Convert ms to seconds

    async def start(self) -> None:
        """Start reading messages from transport."""
        if self._tg is None:
            self._tg = anyio.create_task_group()
            await self._tg.__aenter__()
            self._tg.start_soon(self._read_messages)

    async def _read_messages(self) -> None:
        """Background task that reads messages from transport and routes them."""
        try:
            message_count = 0
            async for message in self.transport.read_messages():
                if self._closed:
                    logger.debug(f"[_read_messages] Closed, stopping after {message_count} messages")
                    break

                msg_type = message.get("type")
                message_count += 1

                # Route control responses
                if msg_type == "control_response":
                    response = message.get("response", {})
                    request_id = response.get("request_id")
                    if request_id in self.pending_control_responses:
                        event = self.pending_control_responses[request_id]
                        if response.get("subtype") == "error":
                            self.pending_control_results[request_id] = Exception(
                                response.get("error", "Unknown error")
                            )
                        else:
                            self.pending_control_results[request_id] = response
                        event.set()
                    continue

                # Route control requests (from CLI to SDK)
                elif msg_type == "control_request":
                    if self._tg:
                        self._tg.start_soon(self._handle_control_request, message)
                    continue

                # Stream regular messages to all registered queues
                # (this includes result messages)
                # Send to legacy _message_send stream
                await self._message_send.send(message)

                # Also send to any per-call queues
                message_queues = getattr(self, "_message_queues", {})
                logger.debug(f"[_read_messages] Broadcasting message type={msg_type} to {len(message_queues)} queues")
                for queue_id, queue_send in list(message_queues.items()):
                    try:
                        await queue_send.send(message)
                        logger.debug(f"[_read_messages] Sent to queue {queue_id}")
                    except Exception as e:
                        # Queue is closed, remove it
                        logger.debug(f"[_read_messages] Queue {queue_id} closed, removing: {e}")
                        message_queues.pop(queue_id, None)

                # Track results for proper stream closure (after broadcasting)
                if msg_type == "result":
                    self._first_result_event.set()
                    # Send to legacy _message_send stream
                    await self._message_send.send(message)

                    # Also send to any per-call queues
                    message_queues = getattr(self, "_message_queues", {})
                    logger.debug(f"[_read_messages] Broadcasting message to {len(message_queues)} queues")
                    for queue_id, queue_send in list(message_queues.items()):
                        try:
                            await queue_send.send(message)
                            logger.debug(f"[_read_messages] Sent to queue {queue_id}")
                        except Exception as e:
                            # Queue is closed, remove it
                            logger.debug(f"[_read_messages] Queue {queue_id} closed, removing: {e}")
                            message_queues.pop(queue_id, None)

            logger.debug(f"[read_messages] Transport stream ended after {message_count} messages")

        except Exception as e:
            logger.error(f"Error in _read_messages: {e}")
            error_message = {"type": "error", "error": str(e)}
            if not self._closed:
                try:
                    await self._message_send.send(error_message)
                except Exception:
                    pass

            # Also send error to all per-call queues
            message_queues = getattr(self, "_message_queues", {})
            for queue_id, queue_send in list(message_queues.items()):
                try:
                    await queue_send.send(error_message)
                    logger.debug(f"[_read_messages] Sent error to queue {queue_id}")
                except Exception:
                    # Queue might already be closed
                    message_queues.pop(queue_id, None)

        finally:
            logger.debug("[read_messages] Closing message send stream and all queues")
            await self._message_send.aclose()

            # Signal end of stream to all per-call queues by sending None
            message_queues = getattr(self, "_message_queues", {})
            logger.debug(f"[_read_messages] Closing {len(message_queues)} queues")
            for queue_id, queue_send in list(message_queues.items()):
                try:
                    await queue_send.send(None)
                    logger.debug(f"[_read_messages] Sent None to queue {queue_id}")
                except Exception:
                    pass  # Queue might already be closed
                finally:
                    # Always close the queue send stream
                    try:
                        await queue_send.aclose()
                    except Exception:
                        pass
            message_queues.clear()

    async def _handle_control_request(self, request: dict[str, Any]) -> None:
        """Handle incoming control request from CLI."""
        request_subtype = request.get("request", {}).get("subtype")
        request_id = request.get("request_id")

        try:
            if request_subtype == "can_use_tool":
                await self._handle_can_use_tool(request, request_id)
            elif request_subtype == "hook_callback":
                await self._handle_hook_callback(request, request_id)
            elif request_subtype == "mcp_message":
                await self._handle_mcp_message(request, request_id)
            else:
                # Unknown request subtype
                await self._send_control_response(
                    request_id,
                    error=f"Unknown request subtype: {request_subtype}"
                )

        except Exception as e:
            await self._send_control_response(request_id, error=str(e))

    async def _handle_can_use_tool(
        self, request: dict[str, Any], request_id: str
    ) -> None:
        """Handle tool permission request from CLI."""
        if not self.can_use_tool:
            await self._send_control_response(
                request_id,
                error="can_use_tool callback not provided"
            )
            return

        req = request.get("request", {})
        tool_name = req.get("tool_name", "")
        tool_input = req.get("input", {})

        # Create context
        context = ToolPermissionContext(
            signal=None,
            suggestions=[],
        )

        # Call the permission callback
        try:
            result = await self.can_use_tool(tool_name, tool_input, context)

            # Convert result to response format
            if isinstance(result, PermissionResultAllow):
                await self._send_control_response(
                    request_id,
                    response={
                        "decision": "allow",
                        "updated_input": result.updated_input,
                    }
                )
            else:  # PermissionResultDeny
                await self._send_control_response(
                    request_id,
                    response={
                        "decision": "deny",
                        "message": result.message,
                        "interrupt": result.interrupt,
                    }
                )

        except Exception as e:
            await self._send_control_response(request_id, error=str(e))

    async def _handle_hook_callback(
        self, request: dict[str, Any], request_id: str
    ) -> None:
        """Handle hook callback request from CLI."""
        req = request.get("request", {})
        callback_id = req.get("callback_id")
        input_data = req.get("input", {})
        tool_use_id = req.get("tool_use_id")

        callback = self.hook_callbacks.get(callback_id)
        if not callback:
            await self._send_control_response(
                request_id,
                error=f"Hook callback not found: {callback_id}"
            )
            return

        try:
            # Create hook context
            context = {"signal": None}

            # Call the hook callback
            result = await callback(input_data, tool_use_id, context)

            # Convert Python field names to CLI format
            converted_result = _convert_hook_output_for_cli(result)

            await self._send_control_response(
                request_id,
                response=converted_result.get("response", {})
            )

        except Exception as e:
            await self._send_control_response(request_id, error=str(e))

    async def _handle_mcp_message(
        self, request: dict[str, Any], request_id: str
    ) -> None:
        """Handle MCP message request from CLI for SDK MCP servers.

        This acts as a bridge between JSONRPC messages from the CLI
        and the in-process MCP server.
        """
        req = request.get("request", {})
        server_name = req.get("server_name")
        mcp_message = req.get("message")

        if not server_name or not mcp_message:
            await self._send_control_response(
                request_id,
                error="Missing server_name or message for MCP request"
            )
            return

        # Check if server exists
        if server_name not in self.sdk_mcp_servers:
            await self._send_control_response(
                request_id,
                response={
                    "jsonrpc": "2.0",
                    "id": mcp_message.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Server '{server_name}' not found",
                    },
                }
            )
            return

        # For now, return not implemented
        # Full MCP SDK server support would require the mcp.server package
        # and proper routing of MCP methods
        await self._send_control_response(
            request_id,
            response={
                "jsonrpc": "2.0",
                "id": mcp_message.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method '{mcp_message.get('method')}' not fully implemented yet",
                },
            }
        )

    async def _send_control_request(
        self,
        request: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a control request and wait for response."""
        self._request_counter += 1
        request_id = f"req_{self._request_counter}"

        # Build the control request message
        message = {
            "type": "control_request",
            "request_id": request_id,
            "request": request,
        }

        # Create event for response
        event = anyio.Event()
        self.pending_control_responses[request_id] = event

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
            result = self.pending_control_results.pop(request_id)

            if isinstance(result, Exception):
                raise result

            return result

        finally:
            self.pending_control_responses.pop(request_id, None)

    async def _send_control_response(
        self,
        request_id: str,
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Send a control response to the CLI."""
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
        """
        return self._receive_messages_with_queue()

    async def _receive_messages_with_queue(self) -> AsyncIterator[Message]:
        """Receive messages using a per-call queue to avoid consumer competition."""
        # Create a dedicated queue for this receive call
        queue: anyio.MemoryObjectStream[dict[str, Any] | None]
        queue_send, queue_receive = anyio.create_memory_object_stream[
            dict[str, Any] | None
        ](max_buffer_size=1000)

        # Register this queue to receive messages
        queue_id = f"recv_{self._request_counter}"
        self._request_counter += 1

        # Store the queue send end
        self._message_queues = getattr(self, "_message_queues", {})
        self._message_queues[queue_id] = queue_send
        logger.debug(f"[_receive_messages_with_queue] Registered queue {queue_id}, total queues: {len(self._message_queues)}")

        try:
            message_count = 0
            async for msg_dict in queue_receive:
                message_count += 1
                logger.debug(f"[_receive_messages_with_queue] {queue_id} received message {message_count}: {msg_dict.get('type')}")
                if msg_dict is None:  # End of stream marker
                    break
                message = message_parser.parse_message(msg_dict)
                yield message
            logger.debug(f"[_receive_messages_with_queue] {queue_id} ended after {message_count} messages")
        finally:
            # Clean up
            logger.debug(f"[_receive_messages_with_queue] Cleaning up queue {queue_id}")
            if queue_id in self._message_queues:
                del self._message_queues[queue_id]
            await queue_send.aclose()
            await queue_receive.aclose()

    async def _receive_messages_impl(self) -> AsyncIterator[Message]:
        """Internal implementation of message receiving."""
        try:
            message_count = 0
            async for message_dict in self._message_receive:
                message_count += 1
                msg_type = message_dict.get('type', 'unknown')
                logger.debug(f"[_receive_messages_impl] Received message {message_count}: {msg_type}")
                if msg_type == "result":
                    logger.debug(f"[_receive_messages_impl] ResultMessage received: {message_dict}")
                message = message_parser.parse_message(message_dict)
                if isinstance(message, ResultMessage):
                    logger.debug(f"[_receive_messages_impl] Parsed ResultMessage, yielding...")
                yield message
            logger.debug(f"[_receive_messages_impl] Stream ended after {message_count} messages")

        except Exception as e:
            # Wrap parsing errors
            logger.error(f"[_receive_messages_impl] Error: {e}")
            if isinstance(e, MessageParseError):
                raise
            raise MessageParseError(f"Failed to receive message: {e}") from e
        finally:
            logger.debug("[_receive_messages_impl] Closing stream")

    async def send_message(
        self,
        message_type: str,
        message_data: dict[str, Any],
    ) -> None:
        """Send a message to the CLI."""
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
                if self._closed:
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
                try:
                    with anyio.move_on_after(self._stream_close_timeout):
                        await self._first_result_event.wait()
                        logger.debug("Received first result, closing input stream")
                except Exception:
                    logger.debug(
                        "Timed out waiting for first result, closing input stream"
                    )

            # After all messages sent (and result received if needed), end input
            if hasattr(self.transport, 'end_input'):
                await self.transport.end_input()
        except Exception as e:
            logger.debug(f"Error streaming input: {e}")

    async def set_permission_mode(self, mode: str) -> None:
        """Change permission mode during conversation."""
        request = {
            "subtype": "set_permission_mode",
            "mode": mode,
        }

        await self._send_control_request(request)

    async def set_model(self, model: str | None = None) -> None:
        """Change the AI model during conversation."""
        request = {
            "subtype": "set_model",
            "model": model,
        }

        await self._send_control_request(request)

    async def interrupt(self) -> None:
        """Interrupt the current query."""
        request = {
            "subtype": "interrupt",
        }

        await self._send_control_request(request)

    async def rewind_files(self, user_message_id: str) -> None:
        """Rewind tracked files to their state at a specific user message."""
        request = {
            "subtype": "rewind_files",
            "user_message_id": user_message_id,
        }

        await self._send_control_request(request)

    async def close(self) -> None:
        """Close the query and clean up resources."""
        self._closed = True

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
