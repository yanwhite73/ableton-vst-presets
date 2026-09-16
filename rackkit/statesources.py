#!/usr/bin/env python3
"""State sources: turn a native preset file into the plug-in's serialized state.

Each source knows one vendor's native format and which container it targets. Adding a
new plug-in family is usually just a new source here (see docs/ADD_A_PLUGIN.md) -- the
container builders in :mod:`rackkit.racks` and the safety contract in the engine are
reused unchanged.

A source's ``build`` returns:
* container ``"vst2"``: ``bytes`` -- the full framed ``<Buffer>`` payload.
* container ``"vst3"``: ``(processor, controller)`` -- two ``bytes`` states.

Every source treats the native state as opaque. None parses, migrates or rebuilds it.
All confirmed by loading in Live (see docs/SYNTHESIS.md).
"""

from __future__ import annotations

from pathlib import PurePath
import struct

ARTURIA_ARCHIVE = b"22 serialization::archive "
JUCE_TRAILER = bytes(16) + b"JUCEPrivateData"


def _stem(filename: str) -> str:
    return PurePath(filename).stem


class ArturiaBuffer:
    """Arturia VST2: the native archive, duplicated into the two-archive Buffer."""

    name = "arturia"
    container = "vst2"

    def detect(self, native: bytes, filename: str) -> bool:
        return native.startswith(ARTURIA_ARCHIVE)

    def build(self, native: bytes, filename: str) -> bytes:
        if not native.startswith(ARTURIA_ARCHIVE):
            raise ValueError("Not an Arturia serialization archive")
        return struct.pack("<QQ", len(native), len(native)) + native + native


class UheH2P:
    """u-he VST3 (Tyrell/Zebra/Bazille/...): '#pgm=<name>' + the .h2p, in both states."""

    name = "u-he"
    container = "vst3"

    def detect(self, native: bytes, filename: str) -> bool:
        return filename.lower().endswith(".h2p") and b"#AM=" in native[:512]

    def build(self, native: bytes, filename: str):
        if b"#pgm=" in native[:64]:
            raise ValueError("Native .h2p already has a program-name header")
        state = b"#pgm=" + _stem(filename).encode("utf-8") + b"\n" + native
        return state, state


class VitalJson:
    """Vital VST3: the raw .vital JSON is the processor state (version must match)."""

    name = "vital"
    container = "vst3"

    def detect(self, native: bytes, filename: str) -> bool:
        head = native.lstrip()[:256]
        return filename.lower().endswith(".vital") or (head[:1] == b"{" and b'"synth_version"' in head)

    def build(self, native: bytes, filename: str):
        if native.lstrip()[:1] != b"{":
            raise ValueError("Vital preset is not JSON")
        return native, b""


class SurgeFxp:
    """Surge XT VST3: the sub3 chunk lifted out of the .fxp wrapper as processor state."""

    name = "surge"
    container = "vst3"

    def detect(self, native: bytes, filename: str) -> bool:
        return native[:4] == b"CcnK" and native[16:20] == b"cjs3"

    def build(self, native: bytes, filename: str):
        if len(native) < 60 or native[:4] != b"CcnK" or native[8:12] != b"FPCh":
            raise ValueError("Not a Surge FPCh .fxp")
        magic_id, version, fx_id = struct.unpack_from(">4sI4s", native, 16)  # 'cjs3',1,...
        if native[16:20] != b"cjs3":
            raise ValueError("Unexpected Surge plug-in id in .fxp")
        chunk_len = struct.unpack_from(">I", native, 56)[0]
        raw = native[60:]
        if chunk_len != len(raw) or raw[:4] != b"sub3":
            raise ValueError("Surge .fxp chunk length / sub3 header mismatch")
        return raw + JUCE_TRAILER, b""


SOURCES = [ArturiaBuffer(), UheH2P(), VitalJson(), SurgeFxp()]
_BY_NAME = {s.name: s for s in SOURCES}


def get(name: str):
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(f"Unknown state source '{name}'. Known: {', '.join(sorted(_BY_NAME))}") from None


def detect(native: bytes, filename: str):
    matches = [s for s in SOURCES if s.detect(native, filename)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"No state source recognised {filename!r}; pass --source explicitly.")
    raise ValueError("Native matched multiple state sources (" +
                     ", ".join(s.name for s in matches) + "); pass --source.")
