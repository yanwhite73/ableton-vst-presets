#!/usr/bin/env python3
"""Strip a Rack into a reusable, shareable skeleton (no plug-in sound).

Takes a Rack containing exactly one instrument and blanks the plug-in's state and
configured parameters, leaving only the generic Ableton Rack structure and the plug-in
node's identity fields. The result carries no preset sound, so it is safe to reuse or
share; synthesize/build_library fill in identity + state per preset.

    python3 bin/make_skeleton.py --rack "Some Arturia Rack.adg" --output skeletons/vst2.adg
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rackkit import engine  # noqa: E402

PARAMS = re.compile(rb"<ParameterSettings\b.*?</ParameterSettings>|<ParameterSettings\s*/>", re.DOTALL)


def blank_tag(node: bytes, tag: bytes) -> bytes:
    pattern = re.compile(rb"<%s\b[^>]*>.*?</%s>|<%s\s*/>" % (tag, tag, tag), re.DOTALL)
    return pattern.sub(b"<%s />" % tag, node, count=1)


def strip(xml: bytes) -> tuple:
    vst2 = re.search(rb"<VstPreset\b.*?</VstPreset>", xml, re.DOTALL)
    vst3 = re.search(rb"<Vst3Preset\b.*?</Vst3Preset>", xml, re.DOTALL)
    if bool(vst2) == bool(vst3):
        raise ValueError("Rack must contain exactly one VstPreset or one Vst3Preset")
    match, kind = (vst2, "vst2") if vst2 else (vst3, "vst3")
    node = PARAMS.sub(b"<ParameterSettings />", match.group(0), count=1)
    if kind == "vst2":
        node = blank_tag(node, b"Buffer")
    else:
        node = blank_tag(node, b"ProcessorState")
        node = blank_tag(node, b"ControllerState")
    return xml[:match.start()] + node + xml[match.end():], kind


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rack", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    xml = engine.gzip_unpack(engine.stable_read(args.rack))
    stripped, kind = strip(xml)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    engine.publish_new(args.output, engine.gzip_pack(stripped))
    print(f"{kind} skeleton written: {args.output}")


if __name__ == "__main__":
    main()
