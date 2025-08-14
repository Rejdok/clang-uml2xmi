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
except ImportError:
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


def _parse_cli(argv: list[str], config: GeneratorConfig) -> tuple[str, str, str, GeneratorConfig, str]:
    # Default language detection
    language = "cpp"  # Default to C++
    
    # First pass: extract flags and language
    filtered_args = []
    i = 1  # Skip script name
    while i < len(argv):
        arg = argv[i]
        if arg == "--language" and i + 1 < len(argv):
            language = argv[i + 1]
            if language not in ["c", "cpp"]:
                print(f"Error: Unsupported language '{language}'. Use 'c' or 'cpp'")
                raise SystemExit(1)
            i += 2
            continue
        else:
            filtered_args.append(arg)
            i += 1
    
    # Check minimum required positional arguments
    if len(filtered_args) < 3:
        print("Usage: python3 cpp2uml.py <input> <out.uml> <out.notation> [--language c|cpp] [--strict] [--no-template-binding]")
        print("  C++ mode: <input> = clang-uml JSON file")  
        print("  C mode:   <input> = C source files (comma-separated)")
        raise SystemExit(1)
    
    inp, out_uml, out_notation = filtered_args[0:3]
    
    # Second pass: process other flags  
    i = 3  # Start after positional args
    while i < len(filtered_args):
        arg = filtered_args[i]
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
        # association policy
        if arg == "--no-owned-end":
            config.allow_owned_end = False
            i += 1
            continue
        if arg == "--no-owned-end-annotation":
            config.annotate_owned_end = False
            i += 1
            continue
        # skip unknown flags  
        i += 1
    return inp, out_uml, out_notation, config, language


# ---------- main ----------
def main():
    # Configure logging once
    try:
        configure_logging()
    except Exception:
        # Don't fail CLI just because logging couldn't be configured
        pass

    # Parse CLI with optional flags and language detection
    try:
        inp, out_uml, out_notation, cfg, language = _parse_cli(sys.argv, DEFAULT_CONFIG)
    except SystemExit as e:
        return int(str(e)) if str(e).isdigit() else 1

    # Language-specific processing
    if language == "c":
        print(f"🚀 UML2Papyrus: Processing C source files → XMI")
        # C language processing path
        c_files = inp.split(',') if ',' in inp else [inp]
        artifacts = _build_c_artifacts(c_files, cfg)
    else:
        print(f"🚀 UML2Papyrus: Processing C++ JSON → XMI")
        # Optional diagnostics: list builder phases and exit  
        if "--list-phases" in sys.argv:
            j = load_json(inp)
            from build.cpp.builder import CppModelBuilder as PhaseBuilder
            pb = PhaseBuilder(j, enable_template_binding=cfg.enable_template_binding)
            try:
                phases = pb.get_phases()  # type: ignore[attr-defined]
            except AttributeError:
                phases = []
            except Exception as e:
                print(f"Failed to list phases: {e}")
                return 1
            if phases:
                print("Phases:")
                for i, ph in enumerate(phases, 1):
                    print(f"  {i}. {ph}")
            else:
                print("Phases information not available for this builder")
            return 0
        
        # C++ language processing path (existing)
        j = load_json(inp)
        artifacts = _build_cpp_artifacts(j, cfg)

    # Common XMI generation for both languages
    try:
        from build.pipeline import BuildPipeline
        
        # Inject default std profile unless explicitly disabled (C++ only)
        if language == "cpp":
            if cfg.types_profiles is None:
                cfg.types_profiles = []
            if "--no-std-profile" not in sys.argv:
                import os
                std_profile_path = os.path.join(os.path.dirname(__file__), 'types_profiles', 'std.json')
                if os.path.isfile(std_profile_path) and std_profile_path not in cfg.types_profiles:
                    cfg.types_profiles.append(std_profile_path)
        
        # Generate XMI using unified pipeline
        pipe = BuildPipeline(config=cfg)
        pipe.generate(artifacts, out_uml, out_notation)
        print(f"✅ Written {out_uml} and {out_notation}")
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        # Fallback for C++ only
        if language == "cpp":
            app = Cpp2UmlApp(inp, out_uml, out_notation, config=cfg)
            app.run()
        else:
            raise
    return 0


# ===============================================
# HELPER FUNCTIONS FOR LANGUAGE PROCESSING
# ===============================================

def _build_cpp_artifacts(j: Dict[str, Any], cfg: GeneratorConfig):
    """Build artifacts from C++ JSON (existing logic)"""
    from build.pipeline import BuildPipeline
    pipe = BuildPipeline(config=cfg)
    return pipe.build(j)


def _build_c_artifacts(c_files: list[str], cfg: GeneratorConfig):
    """Build artifacts from C source files (new C integration)"""
    from core.c_model_builder import build_c_uml_model
    from build.pipeline import BuildArtifacts
    
    print(f"📁 Processing {len(c_files)} C source files")
    
    # Build UML model from C sources using integrated builder
    uml_model = build_c_uml_model(c_files)
    
    # Extract project name from first C file
    from pathlib import Path
    project_name = Path(c_files[0]).stem if c_files else "CProject"
    
    print(f"✅ Built C model: {len(uml_model.elements)} elements")
    
    return BuildArtifacts(
        model=uml_model,
        graph=None,  # C doesn't need complex graph structure
        project_name=project_name
    )


if __name__ == "__main__":
    sys.exit(main())
