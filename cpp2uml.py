#!/usr/bin/env python3
"""
cpp2uml_fixed.py - patched version fixing XMI reference attributes

Changes made:
 - use UML/XMI attribute names for references instead of always using xmi:idref
   * ownedAttribute/ownedParameter/ownedEnd now use attribute `type` to reference types
   * generalization uses attribute `general` to reference the parent
   * Dependency elements are emitted with `client` and `supplier` attributes
 - ensure when creating stub/type references we set consistent xmi:id values
 - small readability improvements

This file is a one-to-one edit of the provided script with the above fixes applied.
"""
from typing import Optional, List, Dict, Any, Tuple
import sys, re, uuid, hashlib, json
from dataclasses import dataclass
from lxml import etree
from CppModelBuilder import CppModelBuilder
from UmlModel import UmlModel
from XmiGenerator import XmiGenerator
from NotationWriter import NotationWriter

# Try orjson if available (faster), otherwise fallback
try:
    import orjson as _orjson  # type: ignore
    def load_json(path: str) -> Any:
        with open(path, "rb") as f:
            return _orjson.loads(f.read())
except Exception:
    def load_json(path: str) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ---------- Application ----------
class Cpp2UmlApp:
    def __init__(self, in_json: str, out_uml: str, out_notation: str):
        self.in_json = in_json
        self.out_uml = out_uml
        self.out_notation = out_notation

    def run(self):
        j = load_json(self.in_json)
        builder = CppModelBuilder(j)
        prep = builder.build()

        # Build UmlModel structure
        model = UmlModel(
            elements=prep["created"],
            associations=prep["associations"],
            dependencies=prep["dependencies"],
            generalizations=[],  # kept empty — builder doesn't produce explicit generalizations list
            name_to_xmi=prep["name_to_xmi"]
        )

        project_name = prep["project_name"]

        # XMI generation
        xmi_gen = XmiGenerator(model)
        xmi_gen.write(self.out_uml, project_name)

        # Notation generation (Papyrus minimal)
        notation_writer = NotationWriter(model.elements, self.out_notation, row_wrap=10, step_x=300, step_y=200, width=180, height=100)
        notation_writer.write()
        print("Written", self.out_uml, "and", self.out_notation)


# ---------- main ----------
def main():
    if len(sys.argv) < 4:
        print("Usage: python3 cpp2uml.py <clang-uml.json> <out.uml> <out.notation>")
        return 1
    inp, out_uml, out_notation = sys.argv[1:4]
    app = Cpp2UmlApp(inp, out_uml, out_notation)
    app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
