#!/usr/bin/env python3
"""Locate the packaged skeleton Racks (empty-state Rack shells, no plug-in sound).

The kit ships one skeleton per container so synthesis works out of the box. Users may
override with their own clean Rack (see bin/make_skeleton.py) -- e.g. to match a Rack's
exact formatting -- by passing an explicit skeleton path.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parents[1] / "skeletons"


def default(container: str) -> Path:
    path = _DIR / f"{container}.adg"
    if not path.is_file():
        raise ValueError(f"No packaged {container} skeleton at {path}; pass an explicit --skeleton")
    return path
