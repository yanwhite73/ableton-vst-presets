#!/usr/bin/env python3
"""Synthesize a Rack from a plug-in identity + a native preset, without a saved template.

This is the general path proven for Arturia VST2, u-he VST3 and Vital VST3 (see
docs/SYNTHESIS.md): read the plug-in's identity from Live's cache, turn the native
preset into the plug-in's state with a state source, and place both into a clean
skeleton Rack. No plug-in is loaded; pure stdlib byte work.

It works only where the native preset *is* the plug-in's own state and matches the
installed plug-in version. Loading the result in Live is what qualifies it.
"""

from __future__ import annotations

from pathlib import Path

from . import cache, engine, racks, skeletons, statesources


def resolve_identity(container: str, *, name=None, unique_id=None, class_uid=None, live_db=None):
    """Return the id a builder needs, from an explicit value or Live's plug-in cache."""
    explicit = unique_id if container == "vst2" else class_uid
    if explicit is not None:
        return explicit
    if not name:
        raise ValueError("Provide --name (looked up in Live's cache) or an explicit --unique-id/--class-uid")
    identities = cache.load_identities(cache.find_db(Path(live_db) if live_db else None))
    ident = identities.get(name)
    if ident is None:
        raise ValueError(f"Plug-in {name!r} is not in Live's plug-in cache")
    value = ident.uid_for(container)
    if value is None:
        raise ValueError(f"{name!r} has no {container.upper()} identity in the cache")
    return value


def synthesize(*, native, output, skeleton=None, source=None, name=None,
               unique_id=None, class_uid=None, live_db=None) -> dict:
    native_path, output_path = Path(native), Path(output)
    native_bytes = engine.stable_read(native_path)
    src = statesources.get(source) if source else statesources.detect(native_bytes, native_path.name)

    identity = resolve_identity(src.container, name=name, unique_id=unique_id,
                                class_uid=class_uid, live_db=live_db)
    skeleton_path = Path(skeleton) if skeleton else skeletons.default(src.container)
    skeleton_bytes = engine.stable_read(skeleton_path)
    skeleton_xml = engine.gzip_unpack(skeleton_bytes)
    payload = src.build(native_bytes, native_path.name)

    if src.container == "vst2":
        candidate = racks.build_vst2_rack(skeleton_xml, int(identity), payload)
    else:
        processor, controller = payload
        candidate = racks.build_vst3_rack(skeleton_xml, str(identity), processor, controller)

    if engine.stable_read(native_path) != native_bytes or engine.stable_read(skeleton_path) != skeleton_bytes:
        raise ValueError("Inputs changed while building; nothing was published")

    return engine.publish_candidate(candidate, output_path, extra={
        "mode": "synthesis",
        "source": src.name,
        "container": src.container,
        "plugin": name,
        "identity": identity,
        "skeleton": str(skeleton_path.resolve()),
        "skeleton_sha256": engine.digest(skeleton_bytes),
        "native": str(native_path.resolve()),
        "native_sha256": engine.digest(native_bytes),
        "native_bytes": len(native_bytes),
        "qualification": "EXPERIMENTAL until loaded in Live; native preset must match the "
                         "installed plug-in version",
    })
