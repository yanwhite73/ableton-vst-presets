#!/usr/bin/env python3
"""Read Ableton Live's own plug-in database for plug-in identities.

This is the portable discovery source: Live has already scanned every plug-in and
recorded its name, vendor, version, category and a ``dev_identifier`` that encodes the
VST2 unique id and/or VST3 class UID. The schema is the same on macOS and Windows -- only
the file location differs -- so a scanner built on this needs no OS-specific plug-in-folder
walking or bundle parsing.

Read-only. Never writes, never loads a plug-in.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import sqlite3


@dataclass
class Identity:
    name: str
    vendor: str
    vst2_unique_id: "int | None" = None
    vst3_class_uid: "str | None" = None  # 32-hex (with dashes), as stored
    formats: list = field(default_factory=list)
    is_instrument: bool = False
    versions: list = field(default_factory=list)

    def uid_for(self, container: str):
        """The identity value a rack builder needs: unique id (vst2) or class UID (vst3)."""
        return self.vst2_unique_id if container == "vst2" else self.vst3_class_uid


def default_db_paths() -> "list[Path]":
    """Likely Live plug-in DB locations for the current OS (newest schemas first)."""
    roots = []
    home = Path.home()
    roots.append(home / "Library/Application Support/Ableton/Live Database")   # macOS
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Ableton/Live Database")                   # Windows
    roots.append(home / "AppData/Roaming/Ableton/Live Database")                # Windows fallback
    found = []
    for root in roots:
        if root.is_dir():
            found.extend(sorted(root.glob("Live-plugins*.db")))
    return found


def find_db(explicit: "Path | None" = None) -> Path:
    if explicit:
        if not explicit.is_file():
            raise ValueError(f"Live plug-in DB not found: {explicit}")
        return explicit
    candidates = default_db_paths()
    if not candidates:
        raise ValueError("Could not locate a Live plug-in DB; pass --live-db explicitly.")
    return candidates[-1]


def _parse_dev_identifier(devid: str):
    """Return (format, category, value) from a dev_identifier, or None."""
    m = re.match(r"device:(vst3?|au):([a-z]+):(.+)", devid or "")
    if not m:
        return None
    kind, category, rest = m.groups()
    fmt = {"vst": "VST2", "vst3": "VST3", "au": "AU"}[kind]
    if fmt == "VST2":
        num = re.match(r"(\d+)", rest)
        return fmt, category, ("uid", int(num.group(1))) if num else None
    return fmt, category, ("classuid", rest.split("?")[0])


def load_identities(db: Path) -> "dict[str, Identity]":
    """Map plug-in name -> merged Identity across its VST2/VST3/AU rows. Read-only."""
    uri = "file:" + db.resolve().as_uri()[len("file:"):] + "?mode=ro"
    identities: "dict[str, Identity]" = {}
    with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        rows = con.execute(
            "SELECT name, vendor, version, subcategories, dev_identifier FROM plugins"
        ).fetchall()
    for row in rows:
        parsed = _parse_dev_identifier(row["dev_identifier"])
        if not parsed:
            continue
        fmt, category, value = parsed
        ident = identities.setdefault(row["name"], Identity(name=row["name"], vendor=row["vendor"] or ""))
        if fmt not in ident.formats:
            ident.formats.append(fmt)
        if row["version"] and row["version"] not in ident.versions:
            ident.versions.append(row["version"])
        if "Instrument" in (row["subcategories"] or "") or category == "instr":
            ident.is_instrument = True
        if value and value[0] == "uid":
            ident.vst2_unique_id = value[1]
        elif value and value[0] == "classuid":
            ident.vst3_class_uid = value[1]
    return identities
