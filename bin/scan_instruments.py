#!/usr/bin/env python3
"""List installed plug-in instruments from Live's own plug-in database.

This is the portable "what do I have -> a usable list" step. It reads Live's plug-in
cache (same schema on macOS and Windows; located automatically or via --live-db) and
writes an ``instruments.json`` catalogue plus a readable ``INSTRUMENTS.md``. Each entry
carries the identity a rack builder needs (VST2 UniqueId / VST3 class UID), so the list
feeds straight into synthesize / build_library.

Read-only. No plug-in is loaded, no folder is walked, nothing is written to Live.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import cache  # noqa: E402


def markdown(entries: list) -> str:
    lines = ["# Installed instruments", "",
             "From Live's plug-in cache. Identity is what a rack builder needs; a native",
             "preset in a matching format is still required to make a Rack.", "",
             "| Instrument | Vendor | Formats | VST2 UniqueId | VST3 class UID |",
             "|---|---|---|---|---|"]
    for e in entries:
        lines.append("| {name} | {vendor} | {fmts} | {u} | {c} |".format(
            name=e["name"], vendor=e["vendor"], fmts="/".join(e["formats"]),
            u=e["vst2_unique_id"] if e["vst2_unique_id"] is not None else "",
            c=e["vst3_class_uid"] or ""))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live-db", type=Path, default=None, help="Path to Live-plugins*.db (else auto-locate)")
    parser.add_argument("--out", type=Path, default=None, help="Directory for instruments.json + INSTRUMENTS.md")
    parser.add_argument("--all", action="store_true", help="Include effects, not just instruments")
    args = parser.parse_args()

    db = cache.find_db(args.live_db)
    identities = cache.load_identities(db)
    entries = [asdict(i) for i in identities.values() if args.all or i.is_instrument]
    entries.sort(key=lambda e: (e["vendor"].casefold(), e["name"].casefold()))
    snapshot = {"schema": "rack-preset-kit.instruments.v1", "source_db": str(db), "count": len(entries),
                "instruments": entries}

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "instruments.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        (args.out / "INSTRUMENTS.md").write_text(markdown(entries), encoding="utf-8")
        print(f"{len(entries)} instruments -> {args.out/'instruments.json'} and INSTRUMENTS.md")
    else:
        print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
