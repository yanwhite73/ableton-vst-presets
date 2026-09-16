#!/usr/bin/env python3
"""Onboard a template you saved: identify its kind and print the hash to pin.

Usage:
    python3 bin/inspect_template.py --template "My Clean Rack.adg"

You save a *clean* Instrument Rack of a single plug-in in Live (no effects, default
macros) and point this at it. It confirms which adapter recognises it, describes the
plug-in identity and state, and prints the template's SHA-256 so you can pin it when
converting. It never loads a plug-in or writes anything.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import adapters, engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--adapter", default="auto", help="Adapter name, or 'auto' to detect. "
                        "Known: " + ", ".join(adapters.names()))
    args = parser.parse_args()

    template = engine.stable_read(args.template)
    template_xml = engine.gzip_unpack(template)
    adapter = adapters.detect(template_xml) if args.adapter == "auto" else adapters.get(args.adapter)

    report = {
        "template": str(args.template.resolve()),
        "template_sha256": engine.digest(template),
        "detected_adapter": adapter.name,
        **adapter.inspect(template_xml),
    }
    print(json.dumps(report, indent=2))
    if not report.get("ready_as_template", True):
        print("\nNOTE: this template is not in a usable state for its adapter "
              "(see the report). Re-save a clean single-instrument Rack.", file=sys.stderr)


if __name__ == "__main__":
    main()
