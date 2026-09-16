#!/usr/bin/env python3
"""Install a verified staging tree into a destination folder, without overwriting.

Verifies staging against its manifest, refuses to merge or replace any existing top-level
folder, copies into a hidden temporary sibling, verifies again, then publishes each new
folder by an atomic rename. Never touches files outside the new folders it creates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from . import engine


def safe_relative(rel: str) -> PurePosixPath:
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe manifest path: {rel}")
    return path


def _verify(root: Path, manifest: dict) -> None:
    for entry in manifest["files"]:
        path = root / safe_relative(entry["path"])
        if path.is_symlink() or engine.digest(engine.stable_read(path)) != entry["sha256"]:
            raise ValueError(f"File hash mismatch: {path}")


def install_tree(staging: Path, destination: Path, manifest_sha256: str) -> dict:
    staging, destination = Path(staging), Path(destination).resolve(strict=True)
    manifest_path = staging / "_manifest" / "manifest.json"
    manifest_bytes = engine.stable_read(manifest_path)
    if engine.digest(manifest_bytes) != manifest_sha256:
        raise ValueError("Manifest does not match the approved build hash")
    if not destination.is_dir():
        raise ValueError("Destination must be an existing directory")
    manifest = json.loads(manifest_bytes)

    branches = sorted({safe_relative(f["path"]).parts[0] for f in manifest["files"]} | {"_manifest"})
    for branch in branches:
        if os.path.lexists(destination / branch):
            raise FileExistsError(f"Refusing to merge/replace existing folder: {destination / branch}")

    _verify(staging, manifest)
    temporary = Path(tempfile.mkdtemp(prefix=".rackkit-install-", dir=destination.parent))
    try:
        for entry in manifest["files"]:
            rel = safe_relative(entry["path"])
            target = temporary / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging / rel, target)
        (temporary / "_manifest").mkdir(exist_ok=True)
        shutil.copyfile(manifest_path, temporary / "_manifest" / "manifest.json")
        _verify(temporary, manifest)
        installed = []
        for branch in branches:
            os.replace(temporary / branch, destination / branch)  # target absent -> atomic on POSIX+Windows
            installed.append(branch)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return {"installed": installed, "files": len(manifest["files"]), "destination": str(destination)}
