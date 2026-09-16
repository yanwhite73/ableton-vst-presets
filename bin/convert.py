#!/usr/bin/env python3
"""Convert one native preset into a Rack, using a template you saved.

Usage:
    python3 bin/convert.py \
        --template "My Clean Rack.adg" \
        --template-sha256 <hash from inspect_template> \
        --preset "/path/to/native/preset" \
        --output "My Sound [capture test].adg"

Safety by default: the output must be an ``.adg`` whose name contains
``[capture test]`` until you have loaded one result in Live and confirmed the sound.
Once a plug-in/format is confirmed, pass ``--qualified`` to drop the label. Existing
files are never overwritten; a plug-in is never loaded.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import adapters, engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--preset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--adapter", default="auto", help="Adapter name, or 'auto'. "
                        "Known: " + ", ".join(adapters.names()))
    parser.add_argument("--template-sha256", default=None,
                        help="Pin the template hash (from inspect_template). Strongly recommended.")
    parser.add_argument("--qualified", action="store_true",
                        help="Drop the '[capture test]' output-name requirement (only after a real Live test).")
    args = parser.parse_args()

    if args.output.suffix.lower() != ".adg":
        parser.error("Output must be a .adg file")
    if not args.qualified and "[capture test]" not in args.output.stem:
        parser.error("Until qualified, output name must contain '[capture test]' (or pass --qualified)")
    if os.path.lexists(args.output):
        parser.error("Output already exists; nothing will be overwritten")

    template_xml = engine.gzip_unpack(engine.stable_read(args.template))
    adapter = adapters.detect(template_xml) if args.adapter == "auto" else adapters.get(args.adapter)

    report = engine.convert(
        args.template, args.preset, args.output, adapter,
        pinned_sha=args.template_sha256,
    )
    print(json.dumps(report, indent=2))
    if not args.template_sha256:
        print("\nNOTE: template hash was not pinned. Record output_sha256/template_sha256 "
              "and pin --template-sha256 for repeatable builds.", file=sys.stderr)


if __name__ == "__main__":
    main()
