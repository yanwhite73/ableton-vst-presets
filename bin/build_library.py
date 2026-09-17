#!/usr/bin/env python3
"""Build a folder tree of Racks from a catalogue, into a fresh staging directory.

Reads a ``catalog.json`` (from find_presets or catalog_arturia), synthesizes a Rack per
preset into ``--staging/<output_relative>``, and writes a checksum manifest. Nothing is
installed here; verify staging, then use install.py. Nothing is overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import builder, engine, skeletons  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path, help="New or empty directory to build into")
    parser.add_argument("--skeleton-vst2", type=Path, default=None)
    parser.add_argument("--skeleton-vst3", type=Path, default=None)
    parser.add_argument("--live-db", type=Path, default=None)
    parser.add_argument("--xmp", action="store_true", help="Write Ableton Folder Info keyword sidecars")
    parser.add_argument("--favourite-color", default=None,
                        help="Ableton colour index for favourites (your choice; omit for no colour)")
    parser.add_argument("--vendor-folders", action="store_true",
                        help="Nest output under the plug-in vendor: <vendor>/<instrument>/<category>/")
    args = parser.parse_args()

    if args.staging.exists() and any(args.staging.iterdir()):
        parser.error("Staging must be a new or empty directory")
    catalog = json.loads(engine.stable_read(args.catalog))
    if catalog.get("schema") != "rack-preset-kit.catalog.v1":
        parser.error("Unsupported catalog schema")

    identities = builder.load_identities(args.live_db)
    skel = {c: engine.gzip_unpack(engine.stable_read(p or skeletons.default(c)))
            for c, p in (("vst2", args.skeleton_vst2), ("vst3", args.skeleton_vst3))}
    manifest = builder.build_catalog(catalog["entries"], args.staging, identities, skel,
                                     xmp_tags=args.xmp, favourite_color=args.favourite_color,
                                     vendor_folders=args.vendor_folders)
    meta = args.staging / "_manifest"
    meta.mkdir(exist_ok=True)
    engine.publish_new(meta / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    print(f"built {manifest['built']} racks ({manifest['by_source']}), {manifest['failed']} failed -> {args.staging}")
    for e in manifest["errors"][:10]:
        print("  FAILED:", e["error"])


if __name__ == "__main__":
    main()
