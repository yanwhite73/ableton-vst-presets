#!/usr/bin/env python3
"""Best-effort discovery of the folders this kit reads and writes, per OS.

Everything here is a *default* that can be overridden with an explicit path. Nothing is
required; a location that isn't found (or can't be read for permission reasons) is simply
reported by the caller. Vendor preset roots are user-configurable in each plug-in, so this
covers the common install locations and no more -- users point --root elsewhere otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()
_PROGRAMDATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
_DOCS = HOME / "Documents"


def _first_dir(paths):
    for p in paths:
        try:
            if Path(p).is_dir():
                return Path(p)
        except OSError:
            continue
    return None


def _first_file(paths):
    for p in paths:
        try:
            if Path(p).is_file():
                return Path(p)
        except OSError:
            continue
    return None


def arturia_db():
    return _first_file([
        Path("/Library/Arturia/Presets/db.db3"),          # macOS
        _PROGRAMDATA / "Arturia/Presets/db.db3",           # Windows
    ])


def user_library_instruments():
    """Live's User Library Instruments folder (default install target)."""
    return _first_dir([
        HOME / "Music/Ableton/User Library/Presets/Instruments",     # macOS
        _DOCS / "Ableton/User Library/Presets/Instruments",          # Windows
    ])


# Vendor -> function(plug-in name) -> candidate preset roots (first existing wins).
_VENDOR_ROOTS = {
    "u-he": lambda name: [Path("/Library/Audio/Presets/u-he") / name,
                          HOME / "Library/Audio/Presets/u-he" / name,
                          _DOCS / "u-he" / name],
    "Vital Audio": lambda name: [HOME / "Music/Vital", _DOCS / "Vital"],
    # Only Surge XT itself; other Surge Synth Team plug-ins (Shortcircuit XT) store presets
    # elsewhere and must not be handed Surge's patches.
    "Surge Synth Team": lambda name: ([_DOCS / "Surge XT/Patches",
                                       HOME / "Library/Application Support/Surge XT/Patches",
                                       _PROGRAMDATA / "Surge XT/patches_3rdparty"]
                                      if name == "Surge XT" else []),
}


def preset_root(name: str, vendor: str):
    """A default preset folder for a plug-in, or None if we don't know one."""
    maker = _VENDOR_ROOTS.get(vendor)
    if maker is None:
        return None
    return _first_dir(maker(name))
