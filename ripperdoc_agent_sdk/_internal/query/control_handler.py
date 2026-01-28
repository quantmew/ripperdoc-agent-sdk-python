"""Control request handlers for processing control protocol requests.

This module contains handlers for various control request types from the CLI,
including tool permission requests, hook callbacks, and MCP messages.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ripperdoc_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from .queue_manager import convert_hook_output_for_cli

logger = logging.getLogger(__name__)


class ControlHandler:
    """Handles control protocol requests from the CLI.

    This class processes incoming control requests and routes them
    to appropriate callbacks.
    """

    def __init__(
        self,
        transport_send: Callable[[str], Awaitable[None]],
        can_use_tool: Callable[
            [str, dict[str, Any], ToolPermissionContext],
            Awaitable[PermissionResultAllow | PermissionResultDeny],
        ]
        | None = None,
        hook_callbacks: dict[str, Callable[..., Awaitable[dict[str, Any]]]] | None = None,
        sdk_mcp_servers: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the control handler.

        Args:
            transport_send: Async function to send responses via transport.
            can_use_tool: Optional callback for tool permission requests.
            hook_callbacks: Dictionary of registered hook callbacks.
            sdk_mcp_servers: Dictionary of SDK MCP server instances.
        """
        self._transport_send = transport_send
        self._can_use_tool = can_use_tool
        self._hook_callbacks = hook_callbacks or {}
        self._sdk_mcp_servers = sdk_mcp_servers or {}

    async def handle_control_request(
        self,
        request: dict[str, Any],
        send_response: Callable[[str, dict[str, Any] | None, str | None], Awaitable[None]],
    ) -> None:
        """Handle an incoming control request from the CLI.

        Args:
            request: The control request message.
            send_response: Async function to send a control response.
        """
        request_subtype = request.get("request", {}).get("subtype")
        request_id = request.get("request_id")

        try:
            if request_subtype == "can_use_tool":
                await self._handle_can_use_tool(request, request_id, send_response)
            elif request_subtype == "hook_callback":
                await self._handle_hook_callback(request, request_id, send_response)
            elif request_subtype == "mcp_message":
                await self._handle_mcp_message(request, request_id, send_response)
            else:
                await send_response(
                    request_id,
                    None,
                    f"Unknown request subtype: {request_subtype}"
                )

        except Exception as e:
            logger.error(f"Error handling control request: {e}")
            await send_response(request_id, None, str(e))

    async def _handle_can_use_tool(
        self,
        request: dict[str, Any],
        request_id: str,
        send_response: Callable[[str, dict[str, Any] | None, str | None], Awaitable[None]],
    ) -> None:
        """Handle tool permission request from CLI.

        Args:
            request: The control request message.
            request_id: The request ID for the response.
            send_response: Async function to send a control response.
        """
        if not self._can_use_tool:
            await send_response(
                request_id,
                None,
                "can_use_tool callback not provided"
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
            result = await self._can_use_tool(tool_name, tool_input, context)

            # Convert result to response format
            if isinstance(result, PermissionResultAllow):
                await send_response(
                    request_id,
                    {
                        "decision": "allow",
                        "updated_input": result.updated_input,
                    },
                    None
                )
            else:  # PermissionResultDeny
                await send_response(
                    request_id,
                    {
                        "decision": "deny",
                        "message": result.message,
                        "interrupt": result.interrupt,
                    },
                    None
                )

        except Exception as e:
            logger.error(f"Error in can_use_tool handler: {e}")
            await send_response(request_id, None, str(e))

    async def _handle_hook_callback(
        self,
        request: dict[str, Any],
        request_id: str,
        send_response: Callable[[str, dict[str, Any] | None, str | None], Awaitable[None]],
    ) -> None:
        """Handle hook callback request from CLI.

        Args:
            request: The control request message.
            request_id: The request ID for the response.
            send_response: Async function to send a control response.
        """
        req = request.get("request", {})
        callback_id = req.get("callback_id")
        input_data = req.get("input", {})
        tool_use_id = req.get("tool_use_id")

        callback = self._hook_callbacks.get(callback_id)
        if not callback:
            await send_response(
                request_id,
                None,
                f"Hook callback not found: {callback_id}"
            )
            return

        try:
            # Create hook context
            context = {"signal": None}

            # Call the hook callback
            result = await callback(input_data, tool_use_id, context)

            # Convert Python field names to CLI format
            converted_result = convert_hook_output_for_cli(result)

            await send_response(
                request_id,
                converted_result.get("response", {}),
                None
            )

        except Exception as e:
            logger.error(f"Error in hook_callback handler: {e}")
            await send_response(request_id, None, str(e))

    async def _handle_mcp_message(
        self,
        request: dict[str, Any],
        request_id: str,
        send_response: Callable[[str, dict[str, Any] | None, str | None], Awaitable[None]],
    ) -> None:
        """Handle MCP message request from CLI for SDK MCP servers.

        This acts as a bridge between JSONRPC messages from the CLI
        and the in-process MCP server.

        Args:
            request: The control request message.
            request_id: The request ID for the response.
            send_response: Async function to send a control response.
        """
        req = request.get("request", {})
        server_name = req.get("server_name")
        mcp_message = req.get("message")

        if not server_name or not mcp_message:
            await send_response(
                request_id,
                None,
                "Missing server_name or message for MCP request"
            )
            return

        # Check if server exists
        if server_name not in self._sdk_mcp_servers:
            await send_response(
                request_id,
                {
                    "jsonrpc": "2.0",
                    "id": mcp_message.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Server '{server_name}' not found",
                    },
                },
                None
            )
            return

        # For now, return not implemented
        # Full MCP SDK server support would require the mcp.server package
        # and proper routing of MCP methods
        await send_response(
            request_id,
            {
                "jsonrpc": "2.0",
                "id": mcp_message.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method '{mcp_message.get('method')}' not fully implemented yet",
                },
            },
            None
        )

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
        self._hook_callbacks[callback_id] = callback
        logger.debug(f"[ControlHandler] Registered hook callback {callback_id}")

    def unregister_hook_callback(self, callback_id: str) -> None:
        """Unregister a hook callback.

        Args:
            callback_id: The callback ID to unregister.
        """
        self._hook_callbacks.pop(callback_id, None)
        logger.debug(f"[ControlHandler] Unregistered hook callback {callback_id}")


__all__ = [
    "ControlHandler",
]
