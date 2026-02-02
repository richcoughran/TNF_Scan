#!/usr/bin/env python3
"""
Write lot_folder and its subfolders to an XML file in working_dir so the setNextCaptureFolder applescript in Capture One can find it.
The file is overwritten on each call so it only contains the latest directories.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_XML_FILENAME = "next_capture_folder.xml"


def setNextCaptureFolder(
    working_dir: Path,
    lot_folder: Path,
    subfolders: list[Path] | None = None,
    *,
    xml_filename: str | None = None,
) -> None:
    """
    Write lot_folder and each subfolder to an XML file in working_dir.

    :param working_dir: Session folder (where the XML file is written).
    :param lot_folder: The capture lot folder (e.g. Capture/001_LotName).
    :param subfolders: List of subfolders under lot_folder created by process_one.
    :param xml_filename: Name of the XML file in working_dir. Default: next_capture_folder.xml.
    """
    subfolders = subfolders or []
    name = xml_filename or DEFAULT_XML_FILENAME
    xml_path = working_dir / name

    root = ET.Element("next_capture")
    root.set("version", "1.0")

    wd_el = ET.SubElement(root, "working_dir")
    wd_el.text = str(working_dir.resolve())

    lot_el = ET.SubElement(root, "lot_folder")
    lot_el.text = lot_folder.name

    current_el = ET.SubElement(root, "current_subfolder")
    current_el.text = "1"

    subs_el = ET.SubElement(root, "subfolders")
    for sub in subfolders:
        sub_el = ET.SubElement(subs_el, "subfolder")
        sub_el.text = sub.name

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(
        xml_path,
        encoding="utf-8",
        xml_declaration=True,
        default_namespace="",
        method="xml",
    )
