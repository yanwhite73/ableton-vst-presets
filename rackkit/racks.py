#!/usr/bin/env python3
"""Place a plug-in's identity + state into a clean skeleton Rack.

Two container families, matching how the plug-in serialises its state:

* **VST2 chunk** (e.g. Arturia): identity is ``<Type>`` + ``<UniqueId>``; the state is
  the plug-in's chunk, framed inside ``<Buffer>``.
* **VST3**: identity is a 16-byte class UID stored as four signed int32 ``<Fields>``;
  the state is ``<ProcessorState>`` and optional ``<ControllerState>``.

A builder changes ONLY the single plug-in node and proves every other byte of the Rack
XML is unchanged. It returns candidate XML for :mod:`rackkit.engine` to compress and
publish. No plug-in is loaded; this is pure XML/byte work, identical on every OS.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

VST2_NODE = re.compile(rb"<VstPreset\b.*?</VstPreset>", re.DOTALL)
VST3_NODE = re.compile(rb"<Vst3Preset\b.*?</Vst3Preset>", re.DOTALL)
_BUFFER = re.compile(rb"<Buffer\b[^>]*>.*?</Buffer>|<Buffer\s*/>", re.DOTALL)
_PARAMS = re.compile(rb"<ParameterSettings\b.*?</ParameterSettings>|<ParameterSettings\s*/>", re.DOTALL)


def _one(xml: bytes, pattern: re.Pattern, label: str):
    matches = list(pattern.finditer(xml))
    if len(matches) != 1:
        raise ValueError(f"Skeleton must contain exactly one {label}; found {len(matches)}")
    return matches[0]


def _buffer_width(node: bytes) -> int:
    """Reuse the skeleton Buffer's hex line width; a proven-good default otherwise."""
    m = re.search(rb"<Buffer\b[^>]*>(.*?)</Buffer>", node, re.DOTALL)
    if m:
        lines = m.group(1).strip().splitlines()
        if lines and lines[0].strip() and len(lines[0].strip()) % 2 == 0:
            return len(lines[0].strip())
    return 120


def _hexblock(data: bytes, width: int) -> bytes:
    enc = data.hex().upper().encode("ascii")
    body = b"\n".join(enc[i:i + width] for i in range(0, len(enc), width))
    return b"\n" + body + b"\n"


def uid_fields(class_uid_hex: str) -> "list[int]":
    """VST3 32-hex class UID -> four signed int32 <Fields> values (big-endian groups)."""
    digits = class_uid_hex.replace("-", "").lower()
    if len(digits) != 32 or any(c not in "0123456789abcdef" for c in digits):
        raise ValueError(f"Not a 32-hex VST3 class UID: {class_uid_hex!r}")
    out = []
    for i in range(0, 32, 8):
        value = int(digits[i:i + 8], 16)
        out.append(value - 2 ** 32 if value >= 2 ** 31 else value)
    return out


def build_vst2_rack(skeleton_xml: bytes, unique_id: int, buffer_bytes: bytes) -> bytes:
    """Retarget a clean Arturia-style VST2 rack to ``unique_id`` and set its Buffer."""
    match = _one(skeleton_xml, VST2_NODE, "VstPreset")
    node = match.group(0)
    if node.count(b"<UniqueId Value=") != 1 or not _BUFFER.search(node):
        raise ValueError("Skeleton VstPreset needs one UniqueId and a Buffer")
    width = _buffer_width(node)
    node = re.sub(rb'<UniqueId Value="-?\d+"', b'<UniqueId Value="%d"' % int(unique_id), node, count=1)
    node = _PARAMS.sub(b"<ParameterSettings />", node, count=1)  # drop skeleton's configured params
    node = _BUFFER.sub(b"<Buffer>" + _hexblock(buffer_bytes, width) + b"</Buffer>", node, count=1)
    candidate = skeleton_xml[:match.start()] + node + skeleton_xml[match.end():]
    _verify(candidate, skeleton_xml, VST2_NODE)
    check = _one(candidate, VST2_NODE, "VstPreset").group(0)
    if not re.search(rb'<UniqueId Value="%d"' % int(unique_id), check):
        raise ValueError("UniqueId was not applied")
    if _read_buffer(check) != buffer_bytes:
        raise ValueError("Buffer was not applied exactly")
    return candidate


def build_vst3_rack(skeleton_xml: bytes, class_uid_hex: str, processor: bytes,
                    controller: bytes = b"") -> bytes:
    """Retarget a clean single-instrument VST3 rack to ``class_uid_hex`` and set state."""
    match = _one(skeleton_xml, VST3_NODE, "Vst3Preset")
    node = match.group(0)
    fields = uid_fields(class_uid_hex)
    if any(node.count(b"<Fields.%d Value=" % i) != 1 for i in range(4)):
        raise ValueError("Skeleton Vst3Preset needs four Uid Fields")
    for i, value in enumerate(fields):
        node = re.sub(rb'<Fields\.%d Value="-?\d+"' % i,
                      b'<Fields.%d Value="%d"' % (i, value), node, count=1)
    node = _PARAMS.sub(b"<ParameterSettings />", node, count=1)
    node = _set_state(node, b"ProcessorState", processor)
    node = _set_state(node, b"ControllerState", controller)
    candidate = skeleton_xml[:match.start()] + node + skeleton_xml[match.end():]
    _verify(candidate, skeleton_xml, VST3_NODE)
    check = _one(candidate, VST3_NODE, "Vst3Preset").group(0)
    got = [int(v) for v in re.findall(rb'<Fields\.\d Value="(-?\d+)"', check)]
    if got != fields:
        raise ValueError("Class UID fields were not applied")
    if _read_state(check, b"ProcessorState") != processor or _read_state(check, b"ControllerState") != controller:
        raise ValueError("Processor/controller state was not applied exactly")
    return candidate


def _set_state(node: bytes, tag: bytes, data: bytes) -> bytes:
    pattern = re.compile(rb"<%s\b[^>]*>.*?</%s>|<%s\s*/>" % (tag, tag, tag), re.DOTALL)
    if not pattern.search(node):
        raise ValueError(f"Skeleton Vst3Preset lacks {tag.decode()}")
    if not data:
        return pattern.sub(b"<%s />" % tag, node, count=1)
    block = _hexblock(data, 120)
    return pattern.sub(b"<%s>" % tag + block + b"</%s>" % tag, node, count=1)


def _read_buffer(node: bytes) -> bytes:
    m = re.search(rb"<Buffer\b[^>]*>(.*?)</Buffer>", node, re.DOTALL)
    return bytes.fromhex(b"".join(m.group(1).split()).decode()) if m and m.group(1).strip() else b""


def _read_state(node: bytes, tag: bytes) -> bytes:
    m = re.search(rb"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), node, re.DOTALL)
    return bytes.fromhex(b"".join(m.group(1).split()).decode()) if m and m.group(1).strip() else b""


def _verify(candidate: bytes, skeleton: bytes, pattern: re.Pattern) -> None:
    ET.fromstring(candidate)  # still well-formed XML
    if pattern.sub(b"<X/>", candidate) != pattern.sub(b"<X/>", skeleton):
        raise ValueError("Rack bytes changed outside the plug-in node")
