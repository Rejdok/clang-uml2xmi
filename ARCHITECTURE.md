# Architecture Overview

This document summarizes the refactored architecture of the uml2papyrus project.

## Layers
- meta/: XMI/UML meta-models separated from domain model
  - xml_meta.py, uml_meta.py, default_model.py
- core/: Core domain components
  - graph.py: UmlGraph (unified in-memory model)
  - namespace.py: NamespaceNode and tree utilities
- build/: Model building layer
  - contracts.py: Protocols for adapters/builders/exporters
  - pipeline.py: Orchestrates build and generation
  - cpp/: C++ builder split into phases
    - builder.py: public API CppModelBuilder (phased)
    - prepare.py/prepare_impl.py: build initial elements/namespaces
    - details.py: enrich elements (templates, members, operations)
    - indices.py: indices for lookups
    - associations.py, dependencies.py, inheritance.py: relations
    - template_utils.py: helpers (names, templates)
- gen/: XMI/notation generation
  - XmiGenerator.py: pure serialization from UmlModel (+optional UmlGraph)
  - XmiWriter.py: low-level XML writing helpers
  - NotationWriter.py: Papyrus notation (layout)
- app/: CLI and config
  - cpp2uml.py: main entrypoint
  - Config.py: generator and diagram config
- tests/: pytest test suite (moved from root)

## Data Flow
1) Source JSON (clang-uml) -> build.cpp.builder.CppModelBuilder (build phases)
2) Build result -> UmlModel (+ optional UmlGraph)
3) XmiGenerator consumes UmlModel (and UmlGraph if provided) -> .uml file
4) NotationWriter consumes UmlModel and config -> .notation file

## Extensibility
- Builders are modular by language (cpp/, future c/)
- Phases are decoupled (prepare, details, indices, associations, dependencies, inheritance)
- Meta-models isolated in meta/
- Types profiles (types_profiles/) prepared for declarative rules (currently disabled)

## Backward Compatibility
- Legacy CppModelBuilder.py removed; public API is build.cpp.builder.CppModelBuilder
- Model.DEFAULT_MODEL remains as a fallback when meta/ is not used

## Testing
- All tests under tests/ executed with pytest
- Added pipeline test to ensure end-to-end flow


