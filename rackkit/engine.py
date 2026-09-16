#!/usr/bin/env python3
"""Device-neutral machinery for the rack-preset kit.

The kit puts a plug-in's already-saved state into a *genuine* Ableton Instrument
Rack template that YOU saved yourself, so the sound becomes a browsable ``.adg``.
It never loads a plug-in, drives Live, reads or writes any DAW/database, opens a
socket, or uses a third-party package. Standard library only, so it runs the same
on macOS, Windows and Linux.

The mechanism is intentionally narrow and honest about its limits:

* The plug-in's serialized state is treated as **opaque bytes**. The kit swaps those
  bytes inside your real Rack and proves that *every other byte* of the Rack is
  unchanged. It does not parse, migrate or synthesise plug-in state.
* It cannot build a Rack from nothing and it cannot enumerate a plug-in's internal
  preset bank. That is why each user brings a template they saved in Live.
* "It appears in the browser" is not success. Only loading the produced Rack in Live
  and hearing the right sound qualifies a given plug-in/format. See docs/LIMITS.md.

This module has no device knowledge. The per-plug-in logic lives in :mod:`rackkit.adapters`.
"""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import stat
import tempfile

MAX_BYTES = 16 * 1024 * 1024


def digest(data: bytes) -> str:
    """SHA-256 hex digest, used for pinning inputs and recording provenance."""
    return hashlib.sha256(data).hexdigest()


def stable_read(path: Path) -> bytes:
    """Read a regular file, refusing anything that changes underfoot during the read.

    A preset may be mid-save when we look at it; this rejects that instead of
    exporting a half-written file. Portable: ``st_ino``/``st_dev`` are populated on
    Windows too, so the identity check holds across platforms.
    """
    path = Path(path)

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError(f"Expected a regular file <= {MAX_BYTES} bytes: {path}")
        data = handle.read(MAX_BYTES + 1)
        after = os.fstat(handle.fileno())
    if identity(before) != identity(after) or identity(after) != identity(path.stat()):
        raise ValueError(f"Input changed during read: {path}")
    if len(data) != before.st_size:
        raise ValueError(f"Incomplete input: {path}")
    return data


def gzip_pack(xml: bytes) -> bytes:
    """Compress Rack XML deterministically and verify the round trip in memory."""
    packed = gzip.compress(xml, compresslevel=9, mtime=0)
    if gzip.decompress(packed) != xml:
        raise ValueError("Compressed candidate round trip failed")
    return packed


def gzip_unpack(packed: bytes) -> bytes:
    """Decompress an ``.adg``/``.adv`` container, with a clear error if it is not gzip."""
    try:
        return gzip.decompress(packed)
    except (OSError, EOFError) as error:
        raise ValueError(f"Not a gzipped Ableton preset: {error}") from error


def publish_new(path: Path, data: bytes) -> None:
    """Publish a complete file without ever replacing an existing target.

    Preferred path (POSIX and NTFS): write a temp file in the destination directory,
    ``fsync`` it, then hard-link it into place. The link is atomic and fails if the
    name already exists (a symlink included), so a reader never sees a partial file
    and we never clobber user data.

    Fallback (filesystems without hard links -- exFAT, FAT32, some network shares,
    older Windows setups): reserve the name with ``O_CREAT | O_EXCL`` -- which also
    fails if it exists -- and write into it. Slightly less crash-atomic, still
    non-destructive.
    """
    path = Path(path)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".rackkit-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)  # Atomic; fails if `path` (incl. a symlink) exists.
            return
        except FileExistsError:
            raise
        except (AttributeError, NotImplementedError, OSError):
            _exclusive_write(path, data)  # Hard links unsupported here.
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def _exclusive_write(path: Path, data: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o644)  # Raises FileExistsError if the name is taken.
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def publish_candidate(candidate_xml: bytes, output_path: Path, *, extra: dict | None = None) -> dict:
    """Compress candidate Rack XML, verify the round trip, and publish without overwriting."""
    output_path = Path(output_path)
    output = gzip_pack(candidate_xml)
    publish_new(output_path, output)
    if stable_read(output_path) != output:
        raise ValueError("Published file changed after writing; inspect it before use")
    report = {
        "output": str(output_path.resolve()),
        "output_bytes": len(output),
        "output_sha256": digest(output),
    }
    if extra:
        report.update(extra)
    return report


def convert(
    template_path: Path,
    preset_path: Path,
    output_path: Path,
    adapter,
    *,
    pinned_sha: str | None = None,
    preset_name: str | None = None,
) -> dict:
    """Build one Rack from a template + a native preset, using the given adapter.

    The adapter owns all plug-in-format knowledge. This function owns the safety
    contract that must hold for *every* device: pin the template, read inputs
    stably, verify the compressed round trip, confirm the inputs did not change
    while building, and publish atomically without overwriting anything.
    """
    template_path, preset_path, output_path = Path(template_path), Path(preset_path), Path(output_path)
    template = stable_read(template_path)
    template_sha = digest(template)
    if pinned_sha is not None and template_sha != pinned_sha:
        raise ValueError(
            "Template hash differs from the pinned value; re-inspect the template with "
            "inspect_template before converting."
        )
    native = stable_read(preset_path)
    template_xml = gzip_unpack(template)

    candidate_xml, report = adapter.build(template_xml, native, preset_name=preset_name or preset_path.name)
    output = gzip_pack(candidate_xml)

    if stable_read(template_path) != template or stable_read(preset_path) != native:
        raise ValueError("Inputs changed while building; nothing was published")
    publish_new(output_path, output)
    if stable_read(output_path) != output:
        raise ValueError("Published file changed after writing; inspect it before use")

    report.update({
        "adapter": adapter.name,
        "template": str(template_path.resolve()),
        "template_sha256": template_sha,
        "template_pinned": pinned_sha is not None,
        "preset": str(preset_path.resolve()),
        "preset_sha256": digest(native),
        "output": str(output_path.resolve()),
        "output_bytes": len(output),
        "output_sha256": digest(output),
    })
    return report
