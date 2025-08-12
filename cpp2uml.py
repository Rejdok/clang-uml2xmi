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
 - replaced magic constants with object-oriented configuration model

This file is a one-to-one edit of the provided script with the above fixes applied.
"""
from typing import Optional, List, Dict, Any, Tuple
import sys, re, uuid, hashlib, json
from dataclasses import dataclass

from CppModelBuilder import CppModelBuilder
from UmlModel import UmlModel, ElementName, XmiId
from XmiGenerator import XmiGenerator
from NotationWriter import NotationWriter
from Config import GeneratorConfig, DEFAULT_CONFIG

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
    def __init__(self, in_json: str, out_uml: str, out_notation: str, config: GeneratorConfig = None):
        self.in_json = in_json
        self.out_uml = out_uml
        self.out_notation = out_notation
        
        # Use provided config or default
        if config is None:
            config = DEFAULT_CONFIG
        self.config = config
        
        # Update output paths in config
        self.config.output_uml = out_uml
        self.config.output_notation = out_notation

    def run(self):
        j = load_json(self.in_json)
        builder = CppModelBuilder(j, enable_template_binding=self.config.__dict__.get('enable_template_binding', True))
        prep = builder.build()

        # Build UmlModel structure
        # Convert name-based elements to XMI ID-based elements
        elements_by_xmi = {elem.xmi: elem for elem in prep["created"].values()}
        
        model = UmlModel(
            elements=elements_by_xmi,
            associations=prep["associations"],
            dependencies=prep["dependencies"],
            generalizations=prep.get("generalizations", []),  # Use generalizations from builder
            name_to_xmi=prep["name_to_xmi"]
        )

        project_name = prep["project_name"]
        
        # Update project name in config
        self.config.project_name = project_name

        # XMI generation
        xmi_gen = XmiGenerator(
            model,
            enable_template_binding=self.config.__dict__.get('enable_template_binding', True),
            strict_validation=self.config.__dict__.get('strict_validation', False)
        )
        xmi_gen.write(self.out_uml, project_name)

        # Notation generation (Papyrus minimal) using configuration and model
        notation_writer = NotationWriter(
            model.elements, 
            self.out_notation, 
            config=self.config.diagram
        )
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
