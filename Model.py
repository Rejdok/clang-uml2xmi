#!/usr/bin/env python3
"""
Model structures for UML2Papyrus project.
Contains XMI and UML data models, not configuration.
"""

from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum


class AggregationType(Enum):
    """Association aggregation types."""
    NONE = "none"
    SHARED = "shared"
    COMPOSITE = "composite"


@dataclass
class XmlModel:
    """XML/XMI namespace and attribute model."""
    # Namespaces
    xmi_ns: str = "http://www.omg.org/XMI"
    uml_ns: str = "http://www.eclipse.org/uml2/5.0.0/UML"
    notation_ns: str = "http://www.eclipse.org/papyrus/notation/1.0"
    
    # XMI attributes
    @property
    def xmi_id(self) -> str:
        return f"{{{self.xmi_ns}}}id"
    
    @property
    def xmi_idref(self) -> str:
        return f"{{{self.xmi_ns}}}idref"
    
    @property
    def xmi_type(self) -> str:
        return f"{{{self.xmi_ns}}}type"
    
    @property
    def xmi_version(self) -> str:
        return f"{{{self.xmi_ns}}}version"
    
    # Namespace maps
    @property
    def uml_nsmap(self) -> Dict[str, str]:
        return {
            "xmi": self.xmi_ns,
            "uml": self.uml_ns
        }
    
    @property
    def notation_nsmap(self) -> Dict[str, str]:
        return {
            "notation": self.notation_ns,
            "xmi": self.xmi_ns
        }


@dataclass
class UmlModel:
    """UML-specific model structures."""
    # Element types
    class_type: str = "uml:Class"
    enum_type: str = "uml:Enumeration"
    datatype_type: str = "uml:DataType"
    association_type: str = "uml:Association"
    
    # Literal types
    literal_integer_type: str = "uml:LiteralInteger"
    literal_unlimited_natural_type: str = "uml:LiteralUnlimitedNatural"
    
    # Default values
    default_multiplicity_lower: str = "1"
    default_multiplicity_upper: str = "1"
    unlimited_multiplicity: str = "*"
    
    # Aggregation defaults
    default_aggregation: str = AggregationType.NONE.value
    
    def get_element_type(self, kind: str) -> str:
        """Get UML type string for given element kind."""
        type_mapping = {
            "class": self.class_type,
            "enum": self.enum_type,
            "datatype": self.datatype_type,
            "typedef": self.datatype_type
        }
        return type_mapping.get(kind, self.class_type)


@dataclass
class DiagramModel:
    """Model for diagram generation."""
    # XML model
    xml: XmlModel = None
    
    # UML model
    uml: UmlModel = None
    
    def __post_init__(self):
        """Initialize default models if not provided."""
        if self.xml is None:
            self.xml = XmlModel()
        if self.uml is None:
            self.uml = UmlModel()


# Default model instance
DEFAULT_MODEL = DiagramModel()
