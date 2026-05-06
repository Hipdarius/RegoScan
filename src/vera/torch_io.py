"""Small, safer wrappers for loading PyTorch artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch


def load_torch_state_dict(path: str | Path, *, map_location: str = "cpu") -> Mapping[str, Any]:
    """Load a model state dict without enabling general pickle loading.

    PyTorch 2.x supports ``weights_only=True``, which restricts deserialization
    to tensor-like state. Older PyTorch releases do not expose that argument, so
    we fall back only for compatibility with the project's declared floor.
    """
    try:
        state = torch.load(path, map_location=map_location, weights_only=True)
    except TypeError:  # pragma: no cover - compatibility with older torch
        state = torch.load(path, map_location=map_location)

    if not isinstance(state, Mapping):
        raise TypeError(f"expected a state-dict mapping in {path}, got {type(state)!r}")
    return state


__all__ = ["load_torch_state_dict"]
