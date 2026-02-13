"""Tests for version exports."""

from ripperdoc_agent_sdk import __version__
from ripperdoc_agent_sdk._version import __version__ as _module_version


def test_version_is_string():
    """Test that version is a string."""
    assert isinstance(__version__, str)


def test_version_format():
    """Test that version follows semantic versioning format."""
    # Should match pattern like "0.0.2"
    parts = __version__.split(".")
    assert len(parts) >= 2
    # All parts should be numeric (except possibly pre-release tags)
    for part in parts[:3]:
        assert part.isdigit()


def test_version_consistency():
    """Test that exported version matches module version."""
    assert __version__ == _module_version
