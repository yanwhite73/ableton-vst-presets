#!/usr/bin/env python3
"""Synthesize one Rack from a native preset + a plug-in identity (no saved template).

Example (identity looked up in Live's plug-in cache by name):
    python3 bin/synthesize.py \
        --skeleton "Any clean Arturia Rack.adg" \
        --native "/Library/Arturia/Presets/CS-80 V3/Factory/Factory/16 SQC" \
        --name "CS-80 V3" \
        --output "CS-80 16 SQC [capture test].adg"

The state source (Arturia archive / u-he .h2p / Vital .vital / Surge .fxp) is detected
from the native file, or forced with --source. Use a VST2 skeleton for VST2 sources and
a VST3 skeleton for VST3 sources. Nothing is overwritten; no plug-in is loaded.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import statesources, synth  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skeleton", type=Path, default=None,
                        help="A clean single-instrument Rack (default: the packaged skeleton for the container)")
    parser.add_argument("--native", required=True, type=Path, help="The native preset file to wrap")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", default=None, help="Force a state source. Known: "
                        + ", ".join(s.name for s in statesources.SOURCES))
    parser.add_argument("--name", default=None, help="Plug-in name to look up identity in Live's cache")
    parser.add_argument("--unique-id", type=int, default=None, help="VST2 UniqueId (skip cache lookup)")
    parser.add_argument("--class-uid", default=None, help="VST3 class UID (skip cache lookup)")
    parser.add_argument("--live-db", type=Path, default=None, help="Path to Live-plugins*.db (else auto)")
    parser.add_argument("--qualified", action="store_true",
                        help="Drop the '[capture test]' output-name requirement (after a real Live test)")
    args = parser.parse_args()

    if args.output.suffix.lower() != ".adg":
        parser.error("Output must be a .adg file")
    if not args.qualified and "[capture test]" not in args.output.stem:
        parser.error("Until qualified, output name must contain '[capture test]' (or pass --qualified)")
    if os.path.lexists(args.output):
        parser.error("Output already exists; nothing will be overwritten")

    report = synth.synthesize(
        native=args.native, skeleton=args.skeleton, output=args.output,
        source=args.source, name=args.name, unique_id=args.unique_id,
        class_uid=args.class_uid, live_db=args.live_db,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
