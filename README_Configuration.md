# UML2Papyrus Configuration and Model Documentation

## Overview

The UML2Papyrus project now uses a clear separation between **Configuration** and **Model**:

- **Configuration** (`Config.py`): Contains behavioral settings like layout, dimensions, and file paths
- **Model** (`Model.py`): Contains data structures like XMI namespaces, UML types, and XML attributes

This separation makes the code more maintainable and follows better architectural principles.

## Configuration Classes (`Config.py`)

### LayoutConfig
Defines layout parameters for diagram elements:
```python
@dataclass
class LayoutConfig:
    row_wrap: int = 10          # Elements per row
    step_x: int = 300           # Horizontal spacing
    step_y: int = 200           # Vertical spacing
    width: int = 180            # Element width
    height: int = 100           # Element height
    margin_x: int = 40          # Left margin
    margin_y: int = 40          # Top margin
```

### DiagramConfig
Aggregates layout configuration:
```python
@dataclass
class DiagramConfig:
    diagram_name: str = "ClassDiagram"
    diagram_version: str = "2.0"
    layout: LayoutConfig = None
```

### GeneratorConfig
Top-level configuration for the entire generator:
```python
@dataclass
class GeneratorConfig:
    diagram: DiagramConfig = None
    output_uml: str = "output.uml"
    output_notation: str = "output.notation"
    project_name: str = "GeneratedUML"
```

## Model Classes (`Model.py`)

### XmlModel
Contains XMI/XML namespace and attribute definitions:
```python
@dataclass
class XmlModel:
    xmi_ns: str = "http://www.omg.org/XMI"
    uml_ns: str = "http://www.eclipse.org/uml2/5.0.0/UML"
    notation_ns: str = "http://www.eclipse.org/papyrus/notation/1.0"
    
    @property
    def xmi_id(self) -> str:
        return f"{{{self.xmi_ns}}}id"
    
    @property
    def uml_nsmap(self) -> Dict[str, str]:
        return {"xmi": self.xmi_ns, "uml": self.uml_ns}
```

### UmlModel
Contains UML-specific type definitions and defaults:
```python
@dataclass
class UmlModel:
    class_type: str = "uml:Class"
    enum_type: str = "uml:Enumeration"
    datatype_type: str = "uml:DataType"
    association_type: str = "uml:Association"
    
    default_multiplicity_lower: str = "1"
    default_multiplicity_upper: str = "1"
    unlimited_multiplicity: str = "*"
```

### DiagramModel
Aggregates XML and UML models:
```python
@dataclass
class DiagramModel:
    xml: XmlModel = None
    uml: UmlModel = None
```

## Usage Examples

### Basic Usage
```python
from Config import DEFAULT_CONFIG
from Model import DEFAULT_MODEL

# Use default configuration and model
config = DEFAULT_CONFIG
model = DEFAULT_MODEL

# Create notation writer with both config and model
notation_writer = NotationWriter(
    elements, 
    output_file, 
    config=config.diagram,
    model=model
)
```

### Custom Configuration
```python
from Config import LayoutConfig, DiagramConfig, GeneratorConfig

# Custom layout
custom_layout = LayoutConfig(
    row_wrap=5,
    step_x=400,
    step_y=250,
    width=200,
    height=120
)

# Custom diagram config
custom_diagram = DiagramConfig(
    diagram_name="CustomDiagram",
    layout=custom_layout
)

# Custom generator config
custom_config = GeneratorConfig(
    diagram=custom_diagram,
    project_name="MyProject"
)
```

### Custom Model
```python
from Model import XmlModel, UmlModel, DiagramModel

# Custom XML model with different namespaces
custom_xml = XmlModel(
    xmi_ns="http://custom.xmi.org",
    uml_ns="http://custom.uml.org"
)

# Custom UML model with different types
custom_uml = UmlModel(
    class_type="custom:Class",
    enum_type="custom:Enumeration"
)

# Custom diagram model
custom_model = DiagramModel(
    xml=custom_xml,
    uml=custom_uml
)
```

## Migration from Old Code

### Before (Mixed Configuration)
```python
# Old way - mixed config and model
from Config import XmlConfig, UmlConfig

class NotationWriter:
    def __init__(self, config: DiagramConfig):
        self.xml = config.xml  # This was actually model data
        self.uml = config.uml  # This was actually model data
```

### After (Separated Configuration and Model)
```python
# New way - clear separation
from Config import DiagramConfig
from Model import DiagramModel

class NotationWriter:
    def __init__(self, config: DiagramConfig, model: DiagramModel):
        self.layout = config.layout  # Configuration
        self.xml = model.xml         # Model data
        self.uml = model.uml         # Model data
```

## Advantages

1. **Clear Separation**: Configuration vs. Model data is now explicit
2. **Better Architecture**: Follows single responsibility principle
3. **Easier Testing**: Can mock configuration and model separately
4. **Flexibility**: Can swap models without changing configuration
5. **Maintainability**: Easier to understand what each class represents

## Default Instances

- `DEFAULT_CONFIG`: Instance of `GeneratorConfig` with default values
- `DEFAULT_MODEL`: Instance of `DiagramModel` with default values

## See Also

- `examples/config_examples.py` - More detailed usage examples
- `Config.py` - Configuration classes implementation
- `Model.py` - Model classes implementation
