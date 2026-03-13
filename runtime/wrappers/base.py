from __future__ import annotations

from abc import ABC, abstractmethod


class BaseModelWrapper(ABC):
    """Unified interface for model wrappers: prompt -> response text only."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response from the model. Must return a non-None string."""
        raise NotImplementedError
