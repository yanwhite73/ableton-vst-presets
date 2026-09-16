#!/usr/bin/env python3
"""Catalogue Arturia presets by CATEGORY, from Arturia's preset database.

Arturia stores presets flat on disk but keeps each preset's musical category (Type) in
``/Library/Arturia/Presets/db.db3`` (Windows: ``%PROGRAMDATA%\\Arturia\\Presets\\db.db3``).
This reads it (read-only) and writes a catalogue that lays presets out as
``<instrument>/<category>/<name>.adg``. The instrument folder comes from each preset's own
file path, which matches Live's plug-in name, so build_library needs no name map.

Example vendor-specific provider (see docs/ADD_A_PLUGIN.md). Vendors that already store
presets in category folders just use find_presets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import locations, providers  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=None, help="Arturia db.db3 (default: auto-detect)")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--instrument", default=None, help="Limit to one plug-in folder (e.g. 'CS-80 V3')")
    parser.add_argument("--subtype", action="store_true", help="Add a Subtype level: instrument/type/subtype/name")
    args = parser.parse_args()

    db = args.db or locations.arturia_db()
    if db is None:
        parser.error("Could not find Arturia's db.db3; pass --db")
    entries = providers.arturia_entries(db, folder=args.instrument, subtype=args.subtype)
    catalog = {"schema": "rack-preset-kit.catalog.v1", "provider": "arturia-db",
               "instrument": args.instrument, "count": len(entries), "entries": entries}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    cats = {e["output_relative"].split("/")[1] for e in entries}
    print(f"{len(entries)} presets catalogued into {len(cats)} categories -> {args.out}")


if __name__ == "__main__":
    main()
