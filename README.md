uml2papyrus (refactored)

Overview
This project converts clang-uml JSON into Papyrus UML/XMI. 

Layout
- meta/: XMI/UML meta-models (XmlMetaModel, UmlMetaModel, DEFAULT_META)
- core/: Core domain types (UmlGraph, namespace tree)
- build/: Builders and pipeline
  - build/contracts.py: Protocols for SourceAdapter, ModelBuilder, DiagramBuilder, Exporter
  - build/pipeline.py: Orchestrates build and generation
  - build/cpp/: C++ builder split into phases
    - builder.py: Phased builder wrapper (public API: CppModelBuilder)
    - prepare.py, prepare_impl.py: element preparation
    - details.py: element/member/operation/template details
    - indices.py: indices for lookups
    - associations.py, dependencies.py, inheritance.py: relations
    - template_utils.py: helpers (names, templates)
- gen/: XMI/notation generation (XmiGenerator, XmiWriter, NotationWriter)
- app/: CLI (cpp2uml.py), config
- tests/: pytest test suite

Usage
CLI:
python cpp2uml.py --input input.json --out outdir [--types-profile path1.json] [--types-profile path2.yaml] [--no-std-profile]

Programmatic:
from build.cpp.builder import CppModelBuilder
b = CppModelBuilder(json_data, enable_template_binding=True)
result = b.build()

Pipeline (programmatic):
from build.pipeline import BuildPipeline
artifacts = BuildPipeline().build(json_data)

Notes
- Type profiles (declarative container/pointer rules) are supported via `--types-profile path.json|yaml`; multiple flags allowed. When provided, the association phase is re-applied using registry rules.
- A default std profile is applied automatically unless `--no-std-profile` is passed.
- Legacy `CppModelBuilder.py` was removed; use `build.cpp.builder.CppModelBuilder`.


