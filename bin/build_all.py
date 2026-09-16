#!/usr/bin/env python3
"""One command: build categorised Racks for every installed instrument the kit can handle.

Scans Live's plug-in cache, then for each instrument picks a provider automatically:
Arturia -> its database (categories); u-he / Vital / Surge and other folder-organised
vendors -> their preset folder (folders become categories). Everything is synthesized into
one staging tree with a manifest. Use --install (or run install.py) to publish it into
Live's User Library.

Locations are auto-detected per OS and can be overridden. Anything it can't place -- an
unknown vendor, a folder it can't read -- is reported and skipped, never fatal. Nothing is
overwritten; no plug-in is loaded. Results are EXPERIMENTAL until loaded in Live.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import builder, engine, installer, locations, providers, skeletons  # noqa: E402


def gather(identities, only, exclude, arturia_db):
    """Return (entries, plan). plan is a list of (instrument, provider, detail)."""
    entries, plan, done = [], [], set()

    def wanted(name):
        return name not in exclude and not (only and name not in only)

    if arturia_db:
        try:
            arturia = providers.arturia_entries(arturia_db, folder=None)
        except Exception as error:  # noqa: BLE001 - report and continue, never crash
            arturia = []
            plan.append(("(Arturia DB)", "error", str(error)))
        grouped = defaultdict(list)
        for entry in arturia:
            if entry["instrument"] in identities:
                grouped[entry["instrument"]].append(entry)
        for name, group in sorted(grouped.items()):
            if not wanted(name):
                continue
            entries.extend(group)
            done.add(name)
            plan.append((name, "arturia-db", f"{len(group)} presets"))

    for name, ident in sorted(identities.items()):
        if name in done or not ident.is_instrument or not wanted(name):
            continue
        root = locations.preset_root(name, ident.vendor)
        if root is None:
            plan.append((name, "skip", f"no known preset folder for vendor {ident.vendor!r}"))
            continue
        try:
            found = providers.folder_entries(root, name)
        except PermissionError:
            plan.append((name, "skip", f"permission denied reading {root} (grant access and retry)"))
            continue
        except OSError as error:
            plan.append((name, "skip", f"cannot read {root}: {error}"))
            continue
        if found:
            entries.extend(found)
            plan.append((name, "folder", f"{len(found)} presets from {root}"))
        else:
            plan.append((name, "skip", f"no recognised presets under {root}"))
    return entries, plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--staging", required=True, type=Path, help="New or empty directory to build into")
    parser.add_argument("--live-db", type=Path, default=None)
    parser.add_argument("--arturia-db", type=Path, default=None, help="Override Arturia db.db3 location")
    parser.add_argument("--only", default=None, help="Comma-separated instrument names to limit to")
    parser.add_argument("--exclude", default=None, help="Comma-separated instrument names to skip")
    parser.add_argument("--install", action="store_true", help="Install into the User Library after building")
    parser.add_argument("--destination", type=Path, default=None, help="Install target (default: auto)")
    parser.add_argument("--xmp", action="store_true", help="Write Ableton Folder Info keyword sidecars")
    parser.add_argument("--favourite-color", default=None,
                        help="Ableton colour index for favourites (your choice; omit for no colour)")
    args = parser.parse_args()

    if args.staging.exists() and any(args.staging.iterdir()):
        parser.error("Staging must be a new or empty directory")
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    exclude = {s.strip() for s in args.exclude.split(",")} if args.exclude else set()

    # Never build instruments already installed at the destination (avoids a collision at install).
    destination = args.destination or locations.user_library_instruments()
    if destination and Path(destination).is_dir():
        for child in Path(destination).iterdir():
            if child.is_dir():
                exclude.add(child.name)

    identities = builder.load_identities(args.live_db)
    arturia_db = args.arturia_db or locations.arturia_db()
    entries, plan = gather(identities, only, exclude, arturia_db)

    print("Plan:")
    for name, provider, detail in plan:
        print(f"  {name:24} {provider:11} {detail}")

    skel = {c: engine.gzip_unpack(engine.stable_read(skeletons.default(c))) for c in ("vst2", "vst3")}
    manifest = builder.build_catalog(entries, args.staging, identities, skel,
                                     xmp_tags=args.xmp, favourite_color=args.favourite_color)
    meta = args.staging / "_manifest"
    meta.mkdir(exist_ok=True)
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    engine.publish_new(meta / "manifest.json", manifest_bytes)

    print(f"\nBuilt {manifest['built']} racks across {len(manifest['by_instrument'])} instruments "
          f"({manifest['by_source']}); {manifest['failed']} failed"
          + (f"; {manifest['xmp_sidecars']} XMP sidecars" if args.xmp else "") + ".")
    print(f"Staging: {args.staging}")
    sha = engine.digest(manifest_bytes)
    if args.install:
        if destination is None:
            print("Could not auto-detect the User Library; pass --destination to install.")
        else:
            result = installer.install_tree(args.staging, destination, sha)
            print("Installed:", json.dumps(result))
    else:
        print(f"\nTo install: python3 bin/install.py --staging '{args.staging}' "
              f"--destination '{destination or '<User Library Instruments>'}' --manifest-sha256 {sha}")


if __name__ == "__main__":
    main()
