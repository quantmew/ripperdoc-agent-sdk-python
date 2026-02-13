"""Tests for error classes."""

import pytest

from ripperdoc_agent_sdk._errors import (
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    MessageParseError,
    ProcessError,
    RipperdocSDKError,
)


class TestRipperdocSDKError:
    """Tests for RipperdocSDKError base exception."""

    def test_base_error(self):
        """Test base error can be raised and caught."""
        with pytest.raises(RipperdocSDKError):
            raise RipperdocSDKError("Test error")


class TestCLIConnectionError:
    """Tests for CLIConnectionError."""

    def test_connection_error(self):
        """Test CLI connection error."""
        with pytest.raises(CLIConnectionError):
            raise CLIConnectionError("Cannot connect")

    def test_is_sdk_error(self):
        """Test CLIConnectionError is a RipperdocSDKError."""
        with pytest.raises(RipperdocSDKError):
            raise CLIConnectionError("Test")


class TestCLINotFoundError:
    """Tests for CLINotFoundError."""

    def test_default_message(self):
        """Test default error message."""
        error = CLINotFoundError()
        assert str(error) == "Ripperdoc Code not found"

    def test_custom_message(self):
        """Test custom error message."""
        error = CLINotFoundError("Custom message")
        assert str(error) == "Custom message"

    def test_with_cli_path(self):
        """Test error message with CLI path."""
        error = CLINotFoundError(cli_path="/usr/bin/ripperdoc")
        assert "ripperdoc" in str(error)

    def test_custom_message_with_path(self):
        """Test custom message with CLI path."""
        error = CLINotFoundError("Not installed", cli_path="/usr/local/bin/ripperdoc")
        assert "Not installed" in str(error)
        assert "/usr/local/bin/ripperdoc" in str(error)


class TestProcessError:
    """Tests for ProcessError."""

    def test_basic_error(self):
        """Test basic process error."""
        error = ProcessError("Process failed")
        assert "Process failed" in str(error)

    def test_with_exit_code(self):
        """Test process error with exit code."""
        error = ProcessError("Process failed", exit_code=1)
        assert "exit code: 1" in str(error)

    def test_with_stderr(self):
        """Test process error with stderr."""
        error = ProcessError("Process failed", stderr="Command not found")
        assert "Command not found" in str(error)

    def test_with_exit_code_and_stderr(self):
        """Test process error with both exit code and stderr."""
        error = ProcessError("Process failed", exit_code=127, stderr="Command not found")
        assert "exit code: 127" in str(error)
        assert "Command not found" in str(error)

    def test_stores_exit_code(self):
        """Test exit code is stored as attribute."""
        error = ProcessError("Test", exit_code=42)
        assert error.exit_code == 42

    def test_stores_stderr(self):
        """Test stderr is stored as attribute."""
        stderr_output = "Error output here"
        error = ProcessError("Test", stderr=stderr_output)
        assert error.stderr == stderr_output


class TestCLIJSONDecodeError:
    """Tests for CLIJSONDecodeError."""

    def test_json_decode_error(self):
        """Test JSON decode error."""
        original_error = ValueError("Expecting value")
        error = CLIJSONDecodeError("invalid json", original_error)
        assert "invalid json" in str(error)

    def test_stores_line(self):
        """Test line is stored as attribute."""
        line = '{"invalid": json}'
        error = CLIJSONDecodeError(line, ValueError())
        assert error.line == line

    def test_stores_original_error(self):
        """Test original error is stored."""
        original = ValueError("test")
        error = CLIJSONDecodeError("{}", original)
        assert error.original_error == original


class TestMessageParseError:
    """Tests for MessageParseError."""

    def test_basic_error(self):
        """Test basic message parse error."""
        error = MessageParseError("Invalid message format")
        assert "Invalid message format" in str(error)

    def test_with_data(self):
        """Test message parse error with data."""
        data = {"type": "unknown"}
        error = MessageParseError("Unknown message type", data=data)
        assert error.data == data

    def test_stores_data(self):
        """Test data is stored as attribute."""
        data = {"foo": "bar"}
        error = MessageParseError("Test", data=data)
        assert error.data == data
