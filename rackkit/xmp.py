#!/usr/bin/env python3
"""Write Ableton "Folder Info" XMP sidecars so Racks show keywords / a colour in Live.

Optional. When enabled, each built folder gets ``Ableton Folder Info/<uuid>.xmp`` listing
its Racks with descriptive keywords (``Category|Value``). A favourite colour is attached
ONLY when the user chooses one (Ableton's colour index) -- colour is a personal preference,
never assumed. Matches the structure Live itself writes; Live must re-index for tags to show.
"""

from __future__ import annotations

from pathlib import PurePosixPath
import sys
import uuid
import xml.etree.ElementTree as ET

NS = {
    "x": "adobe:ns:meta/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ablFR": "https://ns.ableton.com/xmp/fs-resources/1.0/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
}
for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)


def _q(name: str) -> str:
    prefix, local = name.split(":")
    return "{" + NS[prefix] + "}" + local


def folder_xmp_bytes(items: list, platform: str = None) -> bytes:
    """items: list of {filePath, keywords: [str], colors: [str]}. Returns XMP bytes."""
    root = ET.Element(_q("x:xmpmeta"), {_q("x:xmptk"): "rack-preset-kit"})
    rdf = ET.SubElement(root, _q("rdf:RDF"))
    desc = ET.SubElement(rdf, _q("rdf:Description"), {_q("rdf:about"): ""})
    ET.SubElement(desc, _q("dc:format")).text = "application/vnd.ableton.folder"
    ET.SubElement(desc, _q("ablFR:resource")).text = "folder"
    ET.SubElement(desc, _q("ablFR:platform")).text = platform or ("win" if sys.platform.startswith("win") else "mac")
    bag = ET.SubElement(ET.SubElement(desc, _q("ablFR:items")), _q("rdf:Bag"))
    for item in sorted(items, key=lambda i: i["filePath"]):
        li = ET.SubElement(bag, _q("rdf:li"), {_q("rdf:parseType"): "Resource"})
        ET.SubElement(li, _q("ablFR:filePath")).text = item["filePath"]
        for field, values in (("keywords", item.get("keywords") or []), ("colors", item.get("colors") or [])):
            if values:
                inner = ET.SubElement(ET.SubElement(li, _q("ablFR:" + field)), _q("rdf:Bag"))
                for value in values:
                    ET.SubElement(inner, _q("rdf:li")).text = str(value)
    ET.indent(root, space="   ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=False) + b"\n"


def sidecar_name(folder_relative: str) -> str:
    """Stable per-folder sidecar filename (so rebuilds don't churn)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "rackkit:" + folder_relative)) + ".xmp"


def sidecar_records(files: list, favourite_color: str = None) -> "list[tuple[str, bytes]]":
    """Group manifest file records by folder and return (relative_path, xmp_bytes) sidecars.

    Each file record has ``path``, ``keywords`` and ``favourite``. ``favourite_color`` is an
    Ableton colour index string applied to favourites, or None to attach no colour.
    """
    by_folder: "dict[str, list]" = {}
    for record in files:
        folder = str(PurePosixPath(record["path"]).parent)
        by_folder.setdefault(folder, []).append(record)
    sidecars = []
    for folder, records in by_folder.items():
        items = [{
            "filePath": PurePosixPath(r["path"]).name,
            "keywords": r.get("keywords") or [],
            "colors": [favourite_color] if (favourite_color and r.get("favourite")) else [],
        } for r in records]
        rel = str(PurePosixPath(folder, "Ableton Folder Info", sidecar_name(folder)))
        sidecars.append((rel, folder_xmp_bytes(items)))
    return sidecars
