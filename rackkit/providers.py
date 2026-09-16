#!/usr/bin/env python3
"""Catalogue providers: turn a source of presets into catalogue entries.

A catalogue entry is ``{instrument, native, source, output_relative, keywords, favourite}``.
``build_catalog`` (in :mod:`rackkit.builder`) synthesizes a Rack per entry.

Two providers ship:

* ``folder_entries`` -- presets already laid out in category folders on disk (u-he, Vital,
  Surge, and most vendors). The on-disk folder structure becomes the category path.
* ``arturia_entries`` -- Arturia keeps categories in its ``db.db3``; this reads it and lays
  presets out as ``<instrument>/<category>/<name>``.

Other DB/metadata-driven vendors get a new provider here (see docs/ADD_A_PLUGIN.md).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath
import re
import sqlite3

from . import engine, statesources

_SAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def component(value) -> str:
    return _SAFE.sub("-", str(value or "")).strip(" .") or "Uncategorised"


def _short(value: str) -> str:
    return engine.digest(value.encode("utf-8"))[:8]


def folder_entries(root: Path, name: str, forced_source: str = None, flat: bool = False) -> list:
    """Catalogue preset files under ``root``, keeping their folder structure as categories."""
    forced = statesources.get(forced_source) if forced_source else None
    root = Path(root).resolve(strict=True)
    entries = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            head = engine.stable_read(path)
        except ValueError:
            continue
        src = forced or next((s for s in statesources.SOURCES if s.detect(head, path.name)), None)
        if src is None or (forced and not forced.detect(head, path.name)):
            continue
        rel = path.relative_to(root)
        parts = [component(name)] if flat else [component(name), *[component(p) for p in rel.parts[:-1]]]
        entries.append({
            "instrument": name, "native": str(path), "source": src.name,
            "output_relative": str(PurePosixPath(*parts, component(rel.stem) + ".adg")),
            "keywords": [f"Instrument|{name}"], "favourite": False,
        })
    return entries


def _connect(db: Path, immutable: bool = False):
    """Open the DB read-only, WAL-aware.

    Arturia's DB is in WAL mode. A closed WAL database (no -wal/-shm) cannot be read with
    ``mode=ro`` -- SQLite fails at the first table read -- so for a closed DB we use
    ``immutable`` (no lock, no WAL needed). When the DB is active (journal files present),
    ``mode=ro`` reads the live database safely.
    """
    db = Path(db)
    active = any((db.parent / (db.name + s)).exists() for s in ("-wal", "-shm", "-journal"))
    uri = db.as_uri() + ("?mode=ro" if (active and not immutable) else "?immutable=1")
    con = sqlite3.connect(uri, uri=True, timeout=2)
    con.execute("PRAGMA query_only=ON")
    con.row_factory = sqlite3.Row
    return con


def _folder_of(file_path: str):
    parts = Path(file_path).parts
    if "Presets" in parts:
        i = parts.index("Presets")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def arturia_entries(db: Path, folder: str = None, subtype: bool = False, immutable: bool = False) -> list:
    """Catalogue Arturia presets by DB category. ``folder`` limits to one plug-in folder."""
    con = _connect(db, immutable)
    rows = con.execute("""
        SELECT p.name AS name, p.file_path AS fp, p.favorite AS fav,
               t.name AS type, s.name AS subtype, b.name AS bank, d.name AS designer
        FROM Preset_Id p JOIN Instruments i ON i.key_id = p.instrument_key
        LEFT JOIN Types_V2 t ON t.key_id = p.type_v2
        LEFT JOIN Subtypes_V2 s ON s.key_id = p.subtype_v2
        LEFT JOIN Packs b ON b.key_id = p.pack
        LEFT JOIN Sound_Designers d ON d.key_id = p.sound_designer
    """).fetchall()
    con.close()

    entries, groups = [], defaultdict(list)
    for r in rows:
        this_folder = _folder_of(r["fp"])
        if not this_folder or (folder and this_folder != folder) or not Path(r["fp"]).is_file():
            continue
        parts = [component(this_folder), component(r["type"])]
        if subtype:
            parts.append(component(r["subtype"]))
        rel = PurePosixPath(*parts, component(r["name"] or Path(r["fp"]).stem) + ".adg")
        groups[str(rel).casefold()].append(len(entries))
        keywords = [f"Instrument|{this_folder}"] + [
            f"{label}|{val}" for label, val in
            (("Type", r["type"]), ("Bank", r["bank"]), ("Designer", r["designer"])) if val]
        entries.append({"instrument": this_folder, "native": r["fp"], "source": "arturia",
                        "output_relative": str(rel), "keywords": keywords, "favourite": bool(r["fav"])})
    for idxs in groups.values():
        if len(idxs) > 1:
            for i in idxs:
                rel = PurePosixPath(entries[i]["output_relative"])
                entries[i]["output_relative"] = str(rel.with_name(rel.stem + " " + _short(entries[i]["native"]) + ".adg"))
    return entries
