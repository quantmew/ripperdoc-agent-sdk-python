"""Hybrid Pydantic model that provides dataclass-like compatibility.

This module provides a base class that makes Pydantic models behave like
dataclasses for backward compatibility, while maintaining Pydantic's
validation benefits.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict
from pydantic.functional_validators import model_validator


class HybridModel(BaseModel):
    """Pydantic model with dataclass-like compatibility.

    This base class provides:
    - Immutable field access (dataclass-like __repr__)
    - to_dict() method for backward compatibility
    - Support for equality comparison
    - Lightweight serialization
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        # Validate assignment to catch errors early
        validate_assignment=True,
        # Use enum values for serialization
        use_enum_values=True,
    )

    def to_dict(self, *, exclude_none: bool = False) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Args:
            exclude_none: Whether to exclude None values.

        Returns:
            Dictionary representation of the model.
        """
        return self.model_dump(exclude_none=exclude_none, by_alias=True, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HybridModel:
        """Create instance from dictionary.

        Args:
            data: Dictionary to create instance from.

        Returns:
            New instance of the model.
        """
        return cls(**data)

    def __repr__(self) -> str:
        """Dataclass-like representation."""
        fields = []
        for name, value in self.model_dump(exclude_none=True).items():
            fields.append(f"{name}={repr(value)}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

    def replace(self, **kwargs: Any) -> HybridModel:
        """Create a new instance with replaced fields (dataclasses.replace-like).

        Args:
            **kwargs: Fields to replace.

        Returns:
            New instance with replaced fields.
        """
        return self.model_copy(update=kwargs)

    def as_dataclass(self) -> type:
        """Return a dataclass version for backward compatibility.

        This creates a lightweight dataclass adapter that wraps the Pydantic model.
        The returned dataclass delegates attribute access to the underlying model.

        Returns:
            A dataclass that wraps this model.
        """
        from dataclasses import dataclass, field
        from typing import Any

        @dataclass(frozen=True)
        class DataclassAdapter:
            """Lightweight dataclass adapter for backward compatibility."""

            _model: HybridModel = field(repr=False)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._model, name)

            def to_dict(self) -> dict[str, Any]:
                return self._model.to_dict()

        # Create instance with this model
        return DataclassAdapter(_model=self)


__all__ = ["HybridModel"]
