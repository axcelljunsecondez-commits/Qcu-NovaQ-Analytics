"""Artifact storage for large payloads that exceed JSON column limits."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    """Protocol for storing opaque byte payloads under generated names."""

    def put(self, data: bytes) -> str:
        """Store bytes and return the generated artifact name."""
        ...

    def get(self, name: str) -> bytes:
        """Retrieve bytes for a previously stored artifact name."""
        ...

    def delete(self, name: str) -> None:
        """Remove a stored artifact; raise FileNotFoundError if missing."""
        ...


class LocalFileArtifactStore:
    """File-system backed artifact store.

    Artifact names are generated as uuid4 hex strings, so callers never
    influence paths (no traversal / injection surface).
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"Invalid artifact name: {name!r}")
        return self.root / name

    def put(self, data: bytes) -> str:
        name = uuid.uuid4().hex
        self._resolve(name).write_bytes(data)
        return name

    def get(self, name: str) -> bytes:
        return self._resolve(name).read_bytes()

    def delete(self, name: str) -> None:
        path = self._resolve(name)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact not found: {name}")
        path.unlink()
