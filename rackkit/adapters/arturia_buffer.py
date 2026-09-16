#!/usr/bin/env python3
"""Adapter: Arturia-style VST2 "two-archive Buffer" instrument Racks.

Observed in a hand-saved Pigments Instrument Rack and shared by other Arturia VST2
plug-ins that serialise the same way: the single ``<VstPreset>`` in the Rack holds a
``<Buffer>`` of hex whose first 16 bytes are two little-endian ``uint64`` lengths,
followed by two byte-identical serialization archives (each starting
``22 serialization::archive``). Recalling the sound means replacing those two copies
with two copies of the native preset file, and changing nothing else.

Unlike the original Pigments-only probe, this adapter does **not** hardcode a plug-in
Type/UniqueId. It validates the *structure* and records whatever identity the template
carries, so it works for any Arturia VST2 plug-in using this scheme. It stays a
duplicate-of-opaque-bytes mechanism -- it never parses, migrates or rebuilds state.
"""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET

NAME = "arturia-buffer"
ARCHIVE_PREFIX = b"22 serialization::archive "
BUFFER = re.compile(rb"<Buffer>(.*?)</Buffer>", re.DOTALL)
PRESET_PATH = "./GroupDevicePreset/BranchPresets/InstrumentBranchPreset/DevicePresets/VstPreset"


def _decode_states(buffer: bytes) -> "tuple[bytes, bytes]":
    if len(buffer) < 16:
        raise ValueError("Truncated state framing")
    first, second = struct.unpack_from("<QQ", buffer)
    if not first or not second or 16 + first + second != len(buffer):
        raise ValueError("State lengths do not match Buffer size")
    states = buffer[16:16 + first], buffer[16 + first:]
    if any(not state.startswith(ARCHIVE_PREFIX) for state in states):
        raise ValueError("Expected two Arturia serialization archives")
    return states


def _encode_states(states: "tuple[bytes, bytes]") -> bytes:
    return struct.pack("<QQ", *(len(state) for state in states)) + b"".join(states)


def _inspect_xml(xml: bytes) -> dict:
    """Validate one clean single-instrument Arturia VST2 Rack and describe it."""
    root = ET.fromstring(xml)
    presets = root.findall(PRESET_PATH)
    if root.tag != "Ableton" or len(presets) != 1 or len(root.findall(".//VstPreset")) != 1:
        raise ValueError("Expected exactly one VstPreset in one Instrument Rack branch")
    preset = presets[0]
    buffers = root.findall(".//Buffer")
    if len(buffers) != 1 or preset.find("Buffer") is not buffers[0] or len(BUFFER.findall(xml)) != 1:
        raise ValueError("Ambiguous or missing Buffer")
    buffer = bytes.fromhex(buffers[0].text or "")
    _decode_states(buffer)

    def value(tag):
        node = preset.find(tag)
        return node.get("Value") if node is not None else None

    return {
        "buffer": buffer,
        "parameter_count": len(preset.findall("./ParameterSettings/PluginParameterSettings")),
        "plugin_type": value("Type"),
        "plugin_unique_id": value("UniqueId"),
    }


def _replace_buffer(xml: bytes, buffer: bytes) -> bytes:
    matches = list(BUFFER.finditer(xml))
    if len(matches) != 1:
        raise ValueError("Expected exactly one Buffer")
    match = matches[0]
    body = match.group(1)
    leading = re.match(rb"\s*", body).group()
    trailing = re.search(rb"\s*$", body).group()
    lines = body.strip().splitlines()
    width = len(lines[0].strip()) if lines else 0
    if not width or width % 2:
        raise ValueError("Unsupported Buffer line format")
    separator = b"\n" + leading.rsplit(b"\n", 1)[-1]
    encoded = buffer.hex().upper().encode("ascii")
    wrapped = separator.join(encoded[i:i + width] for i in range(0, len(encoded), width))
    return xml[:match.start(1)] + leading + wrapped + trailing + xml[match.end(1):]


class ArturiaBufferAdapter:
    name = NAME

    def detect(self, template_xml: bytes) -> bool:
        try:
            info = _inspect_xml(template_xml)
            states = _decode_states(info["buffer"])
        except (ET.ParseError, ValueError):
            return False
        return states[0] == states[1]

    def inspect(self, template_xml: bytes) -> dict:
        info = _inspect_xml(template_xml)
        states = _decode_states(info["buffer"])
        return {
            "adapter": self.name,
            "container": "VST2 two-archive Buffer",
            "plugin_type": info["plugin_type"],
            "plugin_unique_id": info["plugin_unique_id"],
            "configured_parameters": info["parameter_count"],
            "state_bytes": len(states[0]),
            "duplicate_state": states[0] == states[1],
            "ready_as_template": states[0] == states[1],
        }

    def build(self, template_xml: bytes, native: bytes, *, preset_name: str = "") -> "tuple[bytes, dict]":
        if not native.startswith(ARCHIVE_PREFIX):
            raise ValueError("Native preset has no supported Arturia archive header")
        info = _inspect_xml(template_xml)
        original_states = _decode_states(info["buffer"])
        if original_states[0] != original_states[1]:
            raise ValueError("Template is not the observed duplicate-state mechanism")
        if _replace_buffer(template_xml, _encode_states(original_states)) != template_xml:
            raise ValueError("No-change template round trip was not byte-exact")

        candidate = _replace_buffer(template_xml, _encode_states((native, native)))
        new_info = _inspect_xml(candidate)
        if _decode_states(new_info["buffer"]) != (native, native):
            raise ValueError("Candidate did not preserve the full native state")
        if BUFFER.sub(b"<Buffer/>", candidate) != BUFFER.sub(b"<Buffer/>", template_xml):
            raise ValueError("Non-Buffer XML changed")
        if new_info["parameter_count"] != info["parameter_count"]:
            raise ValueError("Configured parameter layout changed")

        report = {
            "qualification": "EXPERIMENTAL; Live load, sound and save/reopen must be confirmed by ear",
            "container": "VST2 two-archive Buffer",
            "plugin_type": info["plugin_type"],
            "plugin_unique_id": info["plugin_unique_id"],
            "native_state_bytes": len(native),
            "buffer_bytes": len(new_info["buffer"]),
            "configured_parameters_preserved": info["parameter_count"],
            "template_xml_roundtrip_exact": True,
            "non_buffer_xml_unchanged": True,
            "both_embedded_states_match_native": True,
        }
        return candidate, report


ADAPTER = ArturiaBufferAdapter()
