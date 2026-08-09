"""ArtifactStore protocol: LocalFileArtifactStore behavior."""

from __future__ import annotations

import pytest

from backend.db.artifacts import LocalFileArtifactStore


def test_put_get_roundtrip(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    name = store.put(b"hello world")
    assert store.get(name) == b"hello world"


def test_generated_names_are_unique(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    first = store.put(b"a")
    second = store.put(b"b")
    assert first != second


def test_delete_removes_payload(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    name = store.put(b"data")
    store.delete(name)
    assert not (store.root / name).exists()


def test_get_missing_raises(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    with pytest.raises(FileNotFoundError):
        store.get("00000000000000000000000000000000")


def test_delete_missing_raises(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    with pytest.raises(FileNotFoundError):
        store.delete("00000000000000000000000000000000")


def test_path_traversal_rejected(tmp_path):
    store = LocalFileArtifactStore(tmp_path / "artifacts")
    with pytest.raises(ValueError):
        store.get("..%2F..%2Fetc%2Fpasswd")
    with pytest.raises(ValueError):
        store.get("../../secret")


def test_store_creates_root_directory(tmp_path):
    root = tmp_path / "nested" / "artifacts"
    LocalFileArtifactStore(root)
    assert root.is_dir()
