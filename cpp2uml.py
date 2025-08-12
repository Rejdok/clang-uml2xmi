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
from typing import Optional, List, Dict, Any
import sys, re, uuid, hashlib, json

from build.cpp.builder import CppModelBuilder
from utils.logging_config import configure_logging
from core.uml_model import UmlModel, ElementName, XmiId
from gen.xmi.generator import XmiGenerator
from gen.notation.writer import NotationWriter
from app.config import GeneratorConfig, DEFAULT_CONFIG
import json as _json

# Try orjson if available (faster), otherwise use json
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
        # Build using current configuration
        builder = CppModelBuilder(j, enable_template_binding=self.config.__dict__.get('enable_template_binding', True))
        prep = builder.build()

        # Prefer UmlGraph if available
        graph = prep.get("graph") if isinstance(prep, dict) else None

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

        # XMI generation (pass graph when available)
        xmi_gen = XmiGenerator(model, graph=graph)
        xmi_gen.write(self.out_uml, project_name, pretty=self.config.__dict__.get('pretty_print', False))

        # Notation generation (Papyrus minimal) using configuration and model
        notation_writer = NotationWriter(
            model.elements, 
            self.out_notation, 
            config=self.config.diagram
        )
        notation_writer.write()
        print("Written", self.out_uml, "and", self.out_notation)


def _parse_cli(argv: list[str], config: GeneratorConfig) -> tuple[str, str, str, GeneratorConfig]:
    if len(argv) < 4:
        print("Usage: python3 cpp2uml.py <clang-uml.json> <out.uml> <out.notation> [--strict] [--no-template-binding]")
        raise SystemExit(1)
    inp, out_uml, out_notation = argv[1:4]
    i = 4
    while i < len(argv):
        arg = argv[i]
        # types profiles are disabled for now
        if arg == "--strict":
            config.strict_validation = True
            i += 1
            continue
        if arg == "--no-template-binding":
            config.enable_template_binding = False
            i += 1
            continue
        if arg == "--types-profile" and i + 1 < len(argv):
            config.types_profiles = (config.types_profiles or []) + [argv[i + 1]]
            i += 2
            continue
        # pretty-print
        if arg == "--pretty":
            config.pretty_print = True
            i += 1
            continue
        # skip unknown
        i += 1
    return inp, out_uml, out_notation, config


# ---------- main ----------
def main():
    # Configure logging once
    try:
        configure_logging()
    except Exception:
        pass

    # Parse CLI with optional flags
    try:
        inp, out_uml, out_notation, cfg = _parse_cli(sys.argv, DEFAULT_CONFIG)
    except SystemExit as e:
        return int(str(e)) if str(e).isdigit() else 1

    # Optional diagnostics: list builder phases and exit
    if "--list-phases" in sys.argv:
        j = load_json(inp)
        from build.cpp.builder import CppModelBuilder as PhaseBuilder
        pb = PhaseBuilder(j, enable_template_binding=cfg.enable_template_binding)
        phases = []
        try:
            phases = pb.get_phases()  # type: ignore[attr-defined]
        except Exception:
            phases = []
        if phases:
            print("Phases:")
            for i, ph in enumerate(phases, 1):
                print(f"  {i}. {ph}")
        else:
            print("Phases information not available for this builder")
        return 0

    # Use the new pipeline to orchestrate build and generation
    try:
        from build.pipeline import BuildPipeline
        # Inject default std profile unless explicitly disabled
        if cfg.types_profiles is None:
            cfg.types_profiles = []
        if "--no-std-profile" not in sys.argv:
            try:
                import os
                std_profile_path = os.path.join(os.path.dirname(__file__), 'types_profiles', 'std.json')
                if os.path.isfile(std_profile_path) and std_profile_path not in cfg.types_profiles:
                    cfg.types_profiles.append(std_profile_path)
            except Exception:
                pass
        pipe = BuildPipeline(config=cfg)
        j = load_json(inp)
        artifacts = pipe.build(j)
        pipe.generate(artifacts, out_uml, out_notation)
        print("Written", out_uml, "and", out_notation)
    except Exception:
        # Execute CLI app
        app = Cpp2UmlApp(inp, out_uml, out_notation, config=cfg)
        app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
