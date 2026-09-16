#!/usr/bin/env python3
"""Offline test suite for rack-preset-kit. No Live, no plug-ins, no network required.

Run: python3 tests/test_rackkit.py
Uses the packaged skeletons plus synthetic states, and checks the safety invariants that
must hold for every device: identity/state applied exactly, everything else byte-identical,
atomic no-overwrite publishing, and format detection.
"""

from __future__ import annotations

import gzip
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rackkit import cache, engine, racks, skeletons, statesources, xmp  # noqa: E402

_XNS = {"ablFR": "https://ns.ableton.com/xmp/fs-resources/1.0/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}


def read_skel(container):
    return engine.gzip_unpack(engine.stable_read(skeletons.default(container)))


def buffer_states(candidate):
    node = re.search(rb"<VstPreset\b.*?</VstPreset>", candidate, re.DOTALL).group(0)
    buf = bytes.fromhex(b"".join(re.search(rb"<Buffer\b[^>]*>(.*?)</Buffer>", node, re.DOTALL).group(1).split()).decode())
    first, second = struct.unpack_from("<QQ", buf)
    return buf[16:16 + first], buf[16 + first:]


class Engine(unittest.TestCase):
    def test_gzip_roundtrip(self):
        data = b"<Ableton>x</Ableton>"
        self.assertEqual(engine.gzip_unpack(engine.gzip_pack(data)), data)

    def test_publish_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "a.bin"
            engine.publish_new(target, b"one")
            self.assertEqual(target.read_bytes(), b"one")
            with self.assertRaises(FileExistsError):
                engine.publish_new(target, b"two")
            self.assertEqual(target.read_bytes(), b"one")


class Racks(unittest.TestCase):
    def test_uid_fields_roundtrip(self):
        uid = "56535456-6974-6176-6974-616c00000000"
        fields = racks.uid_fields(uid)
        rebuilt = "".join(f"{f & 0xffffffff:08x}" for f in fields)
        self.assertEqual(rebuilt, uid.replace("-", ""))

    def test_build_vst2_applies_only_the_node(self):
        skel = read_skel("vst2")
        native = statesources.ARTURIA_ARCHIVE + b"payload-bytes"
        buf = statesources.ArturiaBuffer().build(native, "x")
        candidate = racks.build_vst2_rack(skel, 1129535027, buf)
        self.assertIn(b'<UniqueId Value="1129535027"', candidate)
        self.assertEqual(buffer_states(candidate), (native, native))
        self.assertEqual(racks.VST2_NODE.sub(b"<X/>", candidate), racks.VST2_NODE.sub(b"<X/>", skel))

    def test_build_vst3_applies_only_the_node(self):
        skel = read_skel("vst3")
        uid = "56535456-6974-6176-6974-616c00000000"
        candidate = racks.build_vst3_rack(skel, uid, b"processor-state", b"")
        fields = [int(v) for v in re.findall(rb'<Fields\.\d Value="(-?\d+)"', candidate)]
        self.assertEqual(fields, racks.uid_fields(uid))
        self.assertEqual(racks.VST3_NODE.sub(b"<X/>", candidate), racks.VST3_NODE.sub(b"<X/>", skel))

    def test_build_rejects_bad_uid(self):
        with self.assertRaises(ValueError):
            racks.uid_fields("not-a-uid")


class StateSources(unittest.TestCase):
    def test_arturia(self):
        src = statesources.ArturiaBuffer()
        native = statesources.ARTURIA_ARCHIVE + b"abc"
        self.assertTrue(src.detect(native, "preset"))
        self.assertFalse(src.detect(b"nope", "preset"))
        buf = src.build(native, "preset")
        self.assertEqual(struct.unpack_from("<QQ", buf), (len(native), len(native)))
        self.assertEqual(buf[16:], native + native)

    def test_uhe(self):
        src = statesources.UheH2P()
        native = b"#nm=Foo\n#AM=ZebraCM\nstuff"
        self.assertTrue(src.detect(native, "Hurrying Home.h2p"))
        proc, ctrl = src.build(native, "Hurrying Home.h2p")
        self.assertEqual(proc, ctrl)
        self.assertTrue(proc.startswith(b"#pgm=Hurrying Home\n"))

    def test_vital(self):
        src = statesources.VitalJson()
        native = b'{"synth_version":"1.5.5","settings":{}}'
        self.assertTrue(src.detect(native, "x.vital"))
        self.assertEqual(src.build(native, "x.vital"), (native, b""))

    def test_surge(self):
        raw = b"sub3" + b"\x00" * 40
        fxp = (b"CcnK" + struct.pack(">I", 0) + b"FPCh" + struct.pack(">I", 1) + b"cjs3"
               + struct.pack(">I", 1) + struct.pack(">I", 1) + b"\x00" * 28
               + struct.pack(">I", len(raw)) + raw)
        src = statesources.SurgeFxp()
        self.assertTrue(src.detect(fxp, "p.fxp"))
        proc, ctrl = src.build(fxp, "p.fxp")
        self.assertEqual(proc, raw + statesources.JUCE_TRAILER)
        self.assertEqual(ctrl, b"")

    def test_detect_is_unambiguous(self):
        native = statesources.ARTURIA_ARCHIVE + b"z"
        self.assertIs(statesources.detect(native, "x"), statesources._BY_NAME["arturia"])


class Cache(unittest.TestCase):
    def test_parse_vst2(self):
        self.assertEqual(cache._parse_dev_identifier("device:vst:instr:1296649779?n=Mini%20V3"),
                         ("VST2", "instr", ("uid", 1296649779)))

    def test_parse_vst3(self):
        got = cache._parse_dev_identifier("device:vst3:instr:56535456-6974-6176-6974-616c00000000")
        self.assertEqual(got, ("VST3", "instr", ("classuid", "56535456-6974-6176-6974-616c00000000")))

    def test_parse_junk(self):
        self.assertIsNone(cache._parse_dev_identifier("garbage"))


class Xmp(unittest.TestCase):
    def test_folder_xmp_structure(self):
        import xml.etree.ElementTree as ET
        data = xmp.folder_xmp_bytes([{"filePath": "a.adg", "keywords": ["Type|Bass"], "colors": ["2"]}])
        root = ET.fromstring(data)
        li = root.find(".//ablFR:items/rdf:Bag/rdf:li", _XNS)
        self.assertEqual(li.findtext("ablFR:filePath", namespaces=_XNS), "a.adg")
        self.assertEqual([n.text for n in li.findall("ablFR:keywords/rdf:Bag/rdf:li", _XNS)], ["Type|Bass"])
        self.assertEqual([n.text for n in li.findall("ablFR:colors/rdf:Bag/rdf:li", _XNS)], ["2"])

    def test_colour_only_when_chosen(self):
        files = [{"path": "Inst/Cat/x.adg", "keywords": ["k"], "favourite": True}]
        (_, plain), = xmp.sidecar_records(files, favourite_color=None)
        (_, coloured), = xmp.sidecar_records(files, favourite_color="2")
        self.assertNotIn(b"<ablFR:colors", plain)      # favourite but no colour chosen -> none
        self.assertIn(b"<ablFR:colors", coloured)

    def test_sidecar_path_per_folder(self):
        files = [{"path": "Inst/A/x.adg", "keywords": [], "favourite": False},
                 {"path": "Inst/B/y.adg", "keywords": [], "favourite": False}]
        rels = [rel for rel, _ in xmp.sidecar_records(files)]
        self.assertTrue(all("Ableton Folder Info" in r for r in rels))
        self.assertEqual(len(rels), 2)  # one sidecar per folder


if __name__ == "__main__":
    unittest.main(verbosity=2)
