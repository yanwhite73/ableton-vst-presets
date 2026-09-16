#!/usr/bin/env python3
"""Catalogue an instrument's native presets under a folder (folder structure = category).

Point it at the folder where a plug-in keeps its presets; it recurses, keeps the files a
state source recognises, and writes a neutral ``catalog.json`` that build_library consumes.
The on-disk folder layout under --root becomes the category path in the built Racks.

For a plug-in whose presets live in a database or inside the plug-in, use a dedicated
provider instead (e.g. bin/catalog_arturia.py) -- see docs/ADD_A_PLUGIN.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import providers, statesources  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path, help="Folder to search for native presets")
    parser.add_argument("--name", required=True, help="Instrument name (used for identity lookup at build)")
    parser.add_argument("--source", default=None, help="Force a state source. Known: "
                        + ", ".join(s.name for s in statesources.SOURCES))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--flat", action="store_true", help="One folder per instrument, no sub-categories")
    args = parser.parse_args()

    entries = providers.folder_entries(args.root, args.name, forced_source=args.source, flat=args.flat)
    catalog = {"schema": "rack-preset-kit.catalog.v1", "provider": "folder", "root": str(args.root.resolve()),
               "instrument": args.name, "count": len(entries), "entries": entries}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} presets catalogued -> {args.out}")


if __name__ == "__main__":
    main()
