#!/usr/bin/env python3
"""Turn catalogue entries into a staging tree of Racks, with a manifest.

Shared by build_library (one catalogue) and build_all (every instrument). Each entry is
synthesized independently; a failure -- a missing identity, an unreadable file, a
permission error -- is recorded and skipped, never fatal. Nothing is overwritten.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath

from . import cache, engine, racks, statesources, xmp


def safe_relative(rel: str) -> PurePosixPath:
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe output path: {rel}")
    return path


def build_one(entry: dict, staging: Path, identities: dict, skeleton_xml: dict) -> dict:
    native_path = Path(entry["native"])
    native = engine.stable_read(native_path)  # raises OSError (incl. PermissionError) or ValueError
    src = statesources.get(entry["source"]) if entry.get("source") \
        else statesources.detect(native, native_path.name)
    if src.container not in skeleton_xml:
        raise ValueError(f"No skeleton for {src.container}")
    ident = identities.get(entry["instrument"])
    uid = ident.uid_for(src.container) if ident else None
    if uid is None:
        raise ValueError(f"No {src.container} identity for {entry['instrument']!r} in Live's cache")
    payload = src.build(native, native_path.name)
    if src.container == "vst2":
        candidate = racks.build_vst2_rack(skeleton_xml["vst2"], int(uid), payload)
    else:
        candidate = racks.build_vst3_rack(skeleton_xml["vst3"], str(uid), *payload)
    out = staging / safe_relative(entry["output_relative"])
    out.parent.mkdir(parents=True, exist_ok=True)
    report = engine.publish_candidate(candidate, out)
    return {"path": entry["output_relative"], "sha256": report["output_sha256"],
            "instrument": entry["instrument"], "source": src.name,
            "native": entry["native"], "native_sha256": engine.digest(native),
            "keywords": entry.get("keywords", []), "favourite": bool(entry.get("favourite"))}


def build_catalog(entries: list, staging: Path, identities: dict, skeleton_xml: dict,
                  xmp_tags: bool = False, favourite_color: str = None) -> dict:
    """Build every entry into ``staging``; return a manifest dict (caller writes it).

    With ``xmp_tags``, also write an Ableton Folder Info XMP sidecar per folder (keywords,
    and a favourite colour only if ``favourite_color`` is given).
    """
    staging = Path(staging)
    staging.mkdir(parents=True, exist_ok=True)
    files, errors, by_source, by_instrument = [], [], Counter(), Counter()
    for entry in entries:
        try:
            record = build_one(entry, staging, identities, skeleton_xml)
        except PermissionError as error:
            errors.append({"native": entry.get("native"), "instrument": entry.get("instrument"),
                           "error": f"permission denied: {error}"})
        except (ValueError, OSError, KeyError) as error:
            errors.append({"native": entry.get("native"), "instrument": entry.get("instrument"),
                           "error": str(error)})
        else:
            files.append(record)
            by_source[record["source"]] += 1
            by_instrument[record["instrument"]] += 1

    sidecars = 0
    if xmp_tags and files:
        for rel, data in xmp.sidecar_records(files, favourite_color):
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            engine.publish_new(target, data)
            files.append({"path": rel, "sha256": engine.digest(data), "kind": "xmp"})
            sidecars += 1

    return {"schema": "rack-preset-kit.manifest.v1", "built": len(files) - sidecars, "failed": len(errors),
            "xmp_sidecars": sidecars, "favourite_color": favourite_color,
            "by_source": dict(by_source), "by_instrument": dict(by_instrument),
            "qualification": "EXPERIMENTAL until each plug-in/format is loaded in Live; native "
                             "presets must match installed plug-in versions",
            "files": files, "errors": errors}


def load_identities(live_db=None) -> dict:
    return cache.load_identities(cache.find_db(Path(live_db) if live_db else None))
