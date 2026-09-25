#!/usr/bin/env python3
"""Index an installed Rack library (read-only) into a JSON file other tools can consume.

Works on any library of single-plug-in Racks, including ones installed long ago whose
``_manifest`` no longer exists. Each entry records the plug-in format and exact identity
(VST2 UniqueId / VST3 class UID), the file's SHA-256, its path relative to --root, and the
Instrument/Type/Bank keywords and Collection colours from the folder sidecars. Racks that are
not a single VST2/VST3 plug-in (for example native Live racks) are listed under "errors".

Nothing is written except --out, which must not already exist.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import engine, library_index, locations  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=None,
                        help="Library folder (default: Live's User Library Presets/Instruments)")
    parser.add_argument("--out", required=True, type=Path, help="New JSON file (never overwritten)")
    args = parser.parse_args()

    root = args.root or locations.user_library_instruments()
    if root is None:
        parser.error("No User Library found; pass --root")
    index = library_index.index_tree(root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        engine.publish_new(args.out, (json.dumps(index, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    except FileExistsError:
        parser.error(f"{args.out} already exists; choose a new --out (indexes are never overwritten)")
    counts = index["counts"]
    print(f"{counts['entries']} Racks indexed ({counts['formats']}), {counts['errors']} skipped -> {args.out}")


if __name__ == "__main__":
    main()
