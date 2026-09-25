#!/usr/bin/env python3
"""Read-only index of an installed Rack library, for consumers such as a DAW add-on.

Not to be confused with the *build catalog* (``rack-preset-kit.catalog.v1``) that lists native
presets to convert. This indexes Racks that already exist.

The installer's manifest records what one build wrote. Libraries also outlive it: they get
moved, reorganised, and their ``_manifest`` deleted. This module rebuilds the facts a consumer
needs from the Racks themselves:

* **identity** — the single plug-in node's format plus exact identity (VST2 ``UniqueId``,
  VST3 class UID). A display name alone cannot tell VST2 from VST3 or resolve duplicates.
* **content hash** — ``sha256`` of the ``.adg`` file, so a consumer can relink a moved Rack
  only to an unambiguous identical file.
* **metadata** — Instrument/Type/Bank keywords and Collection colours from the per-folder
  ``Ableton Folder Info`` sidecars this kit (and Live) write with bare file names.

It never writes Racks, loads plug-ins, or treats plug-in state as anything but opaque bytes.
Racks that do not hold exactly one VST2/VST3 plug-in node are reported, not guessed at.
"""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath

from . import engine, racks

SCHEMA = "rack-preset-kit.library-index.v1"
_SIDECAR_DIR = "Ableton Folder Info"
_NS = {"ablFR": "https://ns.ableton.com/xmp/fs-resources/1.0/",
       "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
_LI = "{%s}li" % _NS["rdf"]
_UNIQUE_ID = re.compile(rb'<UniqueId Value="(-?\d+)"')
_FIELDS = re.compile(rb'<Fields\.(\d) Value="(-?\d+)"')


def class_uid_from_fields(fields) -> str:
    """Inverse of :func:`rackkit.racks.uid_fields`: four signed int32 -> 32 lowercase hex."""
    if len(fields) != 4:
        raise ValueError("A VST3 class UID needs exactly four fields")
    return "".join("%08x" % (int(value) & 0xFFFFFFFF) for value in fields)


def rack_identity(xml: bytes):
    """Return ``{"format", "unique_id"|"class_uid"}`` for a single-plug-in Rack, else ``None``."""
    vst2 = racks.VST2_NODE.findall(xml)
    vst3 = racks.VST3_NODE.findall(xml)
    if len(vst2) + len(vst3) != 1:
        return None
    if vst2:
        ids = _UNIQUE_ID.findall(vst2[0])
        return {"format": "vst2", "unique_id": int(ids[0])} if len(ids) == 1 else None
    fields = dict((int(i), int(v)) for i, v in _FIELDS.findall(vst3[0]))
    if sorted(fields) != [0, 1, 2, 3]:
        return None
    return {"format": "vst3", "class_uid": class_uid_from_fields([fields[i] for i in range(4)])}


def sidecar_metadata(folder: Path) -> dict:
    """``{file name: {"keywords": {key: value}, "colors": [...]}}`` from a folder's sidecars.

    Per-folder sidecars list bare names; Live prefixes some with ``+``. Unreadable or malformed
    sidecars contribute nothing.
    """
    out = {}
    info = folder / _SIDECAR_DIR
    if not info.is_dir():
        return out
    for sidecar in sorted(info.glob("*.xmp")):
        try:
            root = ET.fromstring(sidecar.read_bytes())
        except (OSError, ET.ParseError):
            continue
        for li in root.iter(_LI):
            path_el = li.find("ablFR:filePath", _NS)
            if path_el is None or not path_el.text:
                continue
            name = path_el.text.lstrip("+")
            record = out.setdefault(name, {"keywords": {}, "colors": []})
            keywords = li.find("ablFR:keywords", _NS)
            if keywords is not None:
                for kw in keywords.iter(_LI):
                    key, sep, value = (kw.text or "").partition("|")
                    if sep and key and value:
                        record["keywords"].setdefault(key, value)
            colors = li.find("ablFR:colors", _NS)
            if colors is not None:
                record["colors"] = sorted({(c.text or "").strip() for c in colors.iter(_LI)} - {""}
                                          | set(record["colors"]))
    return out


def entry_id(identity: dict, rel_path: str) -> str:
    """Location ID: stable while a Rack stays put. Consumers relink moves by content hash."""
    ident = identity.get("unique_id", identity.get("class_uid"))
    key = "%s:%s:%s" % (identity["format"], ident, rel_path)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def index_tree(root: Path) -> dict:
    """Walk ``root`` read-only and return a library index (see :data:`SCHEMA`)."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Library root is not a folder: {root}")
    entries, errors = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != _SIDECAR_DIR)
        folder = Path(dirpath)
        racks_here = sorted(f for f in filenames if f.lower().endswith(".adg"))
        if not racks_here:
            continue
        metadata = sidecar_metadata(folder)
        for name in racks_here:
            path = folder / name
            rel = path.relative_to(root).as_posix()
            try:
                data = engine.stable_read(path)
                identity = rack_identity(engine.gzip_unpack(data))
            except Exception as exc:  # unreadable, not gzip, changed while reading
                errors.append({"path": rel, "reason": "unreadable: %s" % exc})
                continue
            if identity is None:
                errors.append({"path": rel, "reason": "not a single VST2/VST3 plug-in Rack"})
                continue
            meta = metadata.get(name, {"keywords": {}, "colors": []})
            keywords = meta["keywords"]
            parts = PurePath(rel).parts
            entry = {
                "id": entry_id(identity, rel),
                "path": rel,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
                "name": name[:-4],
                "instrument": keywords.get("Instrument") or (parts[-3] if len(parts) >= 3 else None),
                "category": keywords.get("Type") or (parts[-2] if len(parts) >= 2 else None),
                "bank": keywords.get("Bank"),
                "colors": meta["colors"],
            }
            entry.update(identity)
            entries.append(entry)
    entries.sort(key=lambda e: e["path"])
    by_format = {}
    for entry in entries:
        by_format[entry["format"]] = by_format.get(entry["format"], 0) + 1
    return {"schema": SCHEMA, "entries": entries, "errors": errors,
            "counts": {"entries": len(entries), "errors": len(errors), "formats": by_format}}

