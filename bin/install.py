#!/usr/bin/env python3
"""Install a verified staging tree into a destination folder, without overwriting.

Point --destination at a folder in Live's User Library (e.g. .../User Library/Presets/
Instruments) -- installing there is just like installing a pack. It refuses to merge or
replace an existing folder and verifies against the manifest hash before and after.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import installer, locations  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--destination", type=Path, default=None,
                        help="Folder to install into (default: auto-detected User Library Instruments)")
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    destination = args.destination or locations.user_library_instruments()
    if destination is None:
        parser.error("Could not auto-detect Live's User Library; pass --destination")
    print(json.dumps(installer.install_tree(args.staging, destination, args.manifest_sha256), indent=2))


if __name__ == "__main__":
    main()
