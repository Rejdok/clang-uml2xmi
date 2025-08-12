#!/usr/bin/env python3
"""
Simple XMI validator: finds unresolved idrefs and prints compact context.

Usage:
  python tools/validate_xmi.py path/to/model.uml [--max 5] [--context 8]
"""
from __future__ import annotations

import argparse
from typing import List, Tuple, Dict, Any
from lxml import etree
import io
import os


def collect_ids(root: etree._Element) -> set[str]:
    NS_XMI = "http://www.omg.org/XMI"
    ids: set[str] = set()
    for el in root.iter():
        v = el.get(f"{{{NS_XMI}}}id")
        if v:
            ids.add(v)
    return ids


def find_unresolved(root: etree._Element, ids: set[str], limit: int) -> List[Tuple[str, etree._Element]]:
    NS_XMI = "http://www.omg.org/XMI"
    unresolved: List[Tuple[str, etree._Element]] = []
    # Attributes that commonly refer to xmi:id values
    ref_attrs = [f"{{{NS_XMI}}}idref", "type", "general", "client", "supplier"]
    for el in root.iter():
        # memberEnd elements use @xmi:idref on themselves
        if el.tag.endswith("memberEnd"):
            v = el.get(f"{{{NS_XMI}}}idref")
            if v and v.startswith("id_") and v not in ids:
                unresolved.append((v, el))
                if len(unresolved) >= limit:
                    break
        # generic attributes
        for attr in ref_attrs:
            v = el.get(attr)
            if v and v.startswith("id_") and v not in ids:
                unresolved.append((v, el))
                break
        if len(unresolved) >= limit:
            break
    return unresolved


def print_context(path: str, target: str, around: int) -> None:
    try:
        lines = io.open(path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    except Exception:
        print("<context unavailable>")
        return
    for i, line in enumerate(lines):
        if target in line:
            s = max(0, i - around)
            e = min(len(lines) - 1, i + around)
            print("-- context start --")
            for j in range(s, e + 1):
                print(lines[j])
            print("-- context end --")
            return
    print("<id not found in text>")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xmi_path")
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--context", type=int, default=8)
    args = ap.parse_args()

    if not os.path.isfile(args.xmi_path):
        print(f"File not found: {args.xmi_path}")
        return 2

    parser = etree.XMLParser(recover=True)
    try:
        tree = etree.parse(args.xmi_path, parser)
    except Exception as e:
        print(f"XML parse error: {e}")
        return 3
    root = tree.getroot()

    ids = collect_ids(root)
    bad = find_unresolved(root, ids, args.max)
    if not bad:
        print("OK: no unresolved idrefs")
        return 0

    print(f"Unresolved references: {len(bad)} (showing up to {args.max})")
    for idx, (rid, el) in enumerate(bad, 1):
        parent = el.getparent()
        print(f"[{idx}] id: {rid}")
        print(f"    element: <{el.tag}> attrs={dict(el.attrib)}")
        if parent is not None:
            print(f"    parent:  <{parent.tag}> attrs={dict(parent.attrib)}")
        print_context(args.xmi_path, rid, args.context)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


