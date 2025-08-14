uml2papyrus

Overview
This project converts clang-uml JSON into Papyrus UML/XMI. 

Layout
- meta/: XMI/UML meta-models (XmlMetaModel, UmlMetaModel, DEFAULT_META)
- core/: Core domain types (UmlGraph, namespace tree, compilation database analysis)
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
- gen/: XMI/notation generation (`gen.xmi.generator`, `gen.xmi.writer`, `gen.notation.writer`)
- app/: CLI (cpp2uml.py), config
- tools/: Analysis tools (compilation database analyzer)
- tests/: pytest test suite

Usage

### **UML Generation from C++**
```bash
# Generate UML from clang-uml JSON
python cpp2uml.py input.json output.uml output.notation
```

### **🚀 NEW: Build Structure UML Generation**
```bash
# Generate UML with build structure from compile_commands.json
python cpp2uml.py compile_commands.json build.uml build.notation --from-compile-commands

# Alternative using dedicated tool
python tools/compile_to_xmi.py compile_commands.json --output build_structure.uml --profile --summary
```

### **Compilation Database Analysis**
```bash
# Analyze compile_commands.json to reconstruct library structure
python tools/analyze_compile_db.py compile_commands.json

# Find and analyze in project directory
python tools/analyze_compile_db.py --project /path/to/project

# Save results to file
python tools/analyze_compile_db.py --output analysis.json compile_commands.json
```

### **Programmatic Usage**
```python
# UML Generation from C++
from build.cpp.builder import CppModelBuilder
b = CppModelBuilder(json_data, enable_template_binding=True)
result = b.build()

# Build Structure UML Generation
from core.compilation_database import analyze_compile_commands
from core.build_uml_generator import generate_build_uml
analysis = analyze_compile_commands("compile_commands.json")
uml_model = generate_build_uml(analysis)

# Compilation Database Analysis
from core.compilation_database import analyze_compile_commands
result = analyze_compile_commands("compile_commands.json")

# Pipeline (programmatic)
from build.pipeline import BuildPipeline
artifacts = BuildPipeline().build(json_data)
```

## 🏗️ **Build Structure UML Generation**

This project now supports generating UML models directly from `compile_commands.json` files, creating a comprehensive view of your build system structure:

### **📦 Generated UML Elements:**
- **Packages** - Build targets (executables, libraries) with stereotypes:
  - `<<executable>>` - Executable targets
  - `<<shared_library>>` - Shared/dynamic libraries (.so, .dll)
  - `<<static_library>>` - Static libraries (.a, .lib)
- **Artifacts** - Source files with stereotype `<<file>>`
- **Dependencies** - Inter-target dependencies from linker flags

### **🏷️ Tagged Values:**
- **For Targets:** compile_flags, link_flags, include_paths, output_file, build_order
- **For Files:** file_path, object_file, compile_flags, include_paths

### **📁 Output Structure:**
```
📦 BuildSystem (root package)
├─ 🎯 myapp <<executable>>
│  ├─ Properties: output_file=myapp, build_order=1
│  ├─ Dependencies: → math, gui
│  └─ 📄 main.cpp <<file>>
├─ 🎯 math <<shared_library>>
│  ├─ Properties: output_file=libmath.so, build_order=2
│  ├─ 📄 geometry.cpp <<file>>
│  └─ 📄 math.cpp <<file>>
└─ 🎯 gui <<static_library>>
   ├─ Properties: output_file=libgui.a, build_order=3
   └─ 📄 window.cpp <<file>>
```

### **🔧 Compatible with Papyrus:**
The generated XMI files are fully compatible with Eclipse Papyrus UML editor, allowing you to visualize and edit your build structure using standard UML tools.

Notes
- Type profiles (declarative container/pointer rules) are supported via `--types-profile path.json|yaml`; multiple flags allowed. When provided, association phase uses registry rules.


