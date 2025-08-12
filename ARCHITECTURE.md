## Architecture Overview

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
  - xmi/generator.py: pure serialization from `core.UmlModel` (+optional `core.UmlGraph`)
  - xmi/writer.py: low-level XML writing helpers
  - notation/writer.py: Papyrus notation (layout)
- app/: CLI and config
  - cli.py: argument parsing and entrypoint helpers
  - config.py: generator and diagram config
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

## Public API
- `build.cpp.builder.CppModelBuilder` — phased builder for C++
- `gen.xmi.generator.XmiGenerator` — XMI generator
- `gen.notation.writer.NotationWriter` — notation writer

## Testing
- All tests under tests/ executed with pytest
- Added pipeline test to ensure end-to-end flow


