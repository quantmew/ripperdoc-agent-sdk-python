"""Error types for Ripperdoc SDK.

These exceptions follow a standard structure for API compatibility.
"""

from __future__ import annotations

from typing import Any


class RipperdocSDKError(Exception):
    """Base exception for all SDK errors."""

    def __str__(self) -> str:
        return self.args[0] if self.args else "An error occurred in the Ripperdoc SDK"


# =============================================================================
# Connection Errors
# =============================================================================

class CLIConnectionError(RipperdocSDKError):
    """Raised when unable to connect to the CLI service."""


class CLINotFoundError(CLIConnectionError):
    """Raised when the CLI is not found or not installed."""


# =============================================================================
# Process Errors
# =============================================================================

class ProcessError(RipperdocSDKError):
    """Raised when the CLI process fails."""

    def __init__(self, message: str, exit_code: int | None = None, **kwargs):
        super().__init__(message)
        self.exit_code = exit_code
        self.extra = kwargs


class ProcessStartupError(ProcessError):
    """Raised when the CLI process fails to start."""


class ProcessTerminatedError(ProcessError):
    """Raised when the CLI process terminates unexpectedly."""


# =============================================================================
# Data Parsing Errors
# =============================================================================

class CLIJSONDecodeError(RipperdocSDKError):
    """Raised when unable to decode JSON from CLI output."""


class MessageParseError(RipperdocSDKError):
    """Raised when unable to parse a message from CLI output."""

    def __init__(self, message: str, data: Any = None, **kwargs):
        super().__init__(message)
        self.data = data
        self.extra = kwargs


class InvalidMessageError(MessageParseError):
    """Raised when a message has invalid structure or missing required fields."""


class UnknownMessageTypeError(MessageParseError):
    """Raised when a message has an unknown type."""


# =============================================================================
# Transport Errors
# =============================================================================

class TransportError(RipperdocSDKError):
    """Raised when a transport operation fails."""


class TransportWriteError(TransportError):
    """Raised when writing to transport fails."""


class TransportReadError(TransportError):
    """Raised when reading from transport fails."""


class TransportClosedError(TransportError):
    """Raised when attempting to use a closed transport."""


# =============================================================================
# Stream Errors
# =============================================================================

class StreamError(RipperdocSDKError):
    """Raised when a stream operation fails."""


class StreamClosedError(StreamError):
    """Raised when attempting to use a closed stream."""


class StreamTimeoutError(StreamError):
    """Raised when a stream operation times out."""


# =============================================================================
# Queue Errors
# =============================================================================

class QueueError(RipperdocSDKError):
    """Raised when a message queue operation fails."""


class QueueClosedError(QueueError):
    """Raised when attempting to use a closed queue."""


class QueueFullError(QueueError):
    """Raised when a queue is full and cannot accept more messages."""


# =============================================================================
# Control Protocol Errors
# =============================================================================

class ControlRequestError(RipperdocSDKError):
    """Raised when a control request handling fails."""


class ControlResponseError(ControlRequestError):
    """Raised when a control response is invalid or indicates an error."""


class ControlTimeoutError(ControlRequestError):
    """Raised when a control request times out."""


class UnknownControlRequestError(ControlRequestError):
    """Raised when an unknown control request type is received."""


class PermissionError(ControlRequestError):
    """Raised when a permission request fails or is denied."""


class HookError(ControlRequestError):
    """Raised when a hook callback fails."""


class MCPError(ControlRequestError):
    """Raised when an MCP message handling fails."""


# =============================================================================
# Message Processing Errors
# =============================================================================

class MessageProcessingError(RipperdocSDKError):
    """Raised when message processing fails."""


class MessageRoutingError(MessageProcessingError):
    """Raised when message routing fails."""


class MessageBroadcastError(MessageProcessingError):
    """Raised when message broadcasting to queues fails."""


# =============================================================================
# Initialization Errors
# =============================================================================

class InitializationError(RipperdocSDKError):
    """Raised when SDK or component initialization fails."""


class SessionInitializationError(InitializationError):
    """Raised when session initialization fails."""


# =============================================================================
# API Compatibility Aliases
# =============================================================================

SDKError = RipperdocSDKError
JSONDecodeError = CLIJSONDecodeError


__all__ = [
    # Base
    "RipperdocSDKError",
    # Connection
    "CLIConnectionError",
    "CLINotFoundError",
    # Process
    "ProcessError",
    "ProcessStartupError",
    "ProcessTerminatedError",
    # Data Parsing
    "CLIJSONDecodeError",
    "MessageParseError",
    "InvalidMessageError",
    "UnknownMessageTypeError",
    # Transport
    "TransportError",
    "TransportWriteError",
    "TransportReadError",
    "TransportClosedError",
    # Stream
    "StreamError",
    "StreamClosedError",
    "StreamTimeoutError",
    # Queue
    "QueueError",
    "QueueClosedError",
    "QueueFullError",
    # Control Protocol
    "ControlRequestError",
    "ControlResponseError",
    "ControlTimeoutError",
    "UnknownControlRequestError",
    "PermissionError",
    "HookError",
    "MCPError",
    # Message Processing
    "MessageProcessingError",
    "MessageRoutingError",
    "MessageBroadcastError",
    # Initialization
    "InitializationError",
    "SessionInitializationError",
    # Compatibility aliases
    "SDKError",
    "JSONDecodeError",
]
