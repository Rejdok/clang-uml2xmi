#!/usr/bin/env python3
"""
Model structures for UML2Papyrus project.
Contains XMI and UML data models, not configuration.
"""

from dataclasses import dataclass
from typing import Dict, Any, Literal, Union
from enum import Enum

from uml_types import (
    Namespace, AttributeName, ElementType, MultiplicityValue,
    AggregationType
)

@dataclass
class XmlModel:
    """XML/XMI namespace and attribute model."""
    # Namespaces - XMI 2.1 compliant
    xmi_ns: Namespace = "http://www.omg.org/XMI"
    uml_ns: Namespace = "http://www.eclipse.org/uml2/5.0.0/UML"
    notation_ns: Namespace = "http://www.eclipse.org/papyrus/notation/1.0"
    
    # XMI attributes - XMI 2.1 compliant
    @property
    def xmi_id(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}id"
    
    @property
    def xmi_idref(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}idref"
    
    @property
    def xmi_type(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}type"
    
    @property
    def xmi_version(self) -> AttributeName:
        return f"{{{self.xmi_ns}}}version"
    
    # Namespace maps - XMI 2.1 compliant
    @property
    def uml_nsmap(self) -> Dict[str, Namespace]:
        return {
            "xmi": self.xmi_ns,
            "uml": self.uml_ns
        }
    
    @property
    def notation_nsmap(self) -> Dict[str, Namespace]:
        return {
            "notation": self.notation_ns,
            "xmi": self.xmi_ns
        }

@dataclass
class UmlModel:
    """UML-specific model structures - XMI 2.1 compliant."""
    # Element types - XMI 2.1 compliant
    class_type: ElementType = "uml:Class"
    enum_type: ElementType = "uml:Enumeration"
    datatype_type: ElementType = "uml:DataType"
    association_type: ElementType = "uml:Association"
    package_type: ElementType = "uml:Package"
    dependency_type: ElementType = "uml:Dependency"
    generalization_type: ElementType = "uml:Generalization"
    
    # Template types - XMI 2.1 compliant
    template_signature_type: ElementType = "uml:RedefinableTemplateSignature"
    template_parameter_type: ElementType = "uml:TemplateParameter"
    template_parameter_substitution_type: ElementType = "uml:TemplateParameterSubstitution"
    
    # Property types - XMI 2.1 compliant
    property_type: ElementType = "uml:Property"
    operation_type: ElementType = "uml:Operation"
    parameter_type: ElementType = "uml:Parameter"
    
    # Literal types - XMI 2.1 compliant
    literal_integer_type: ElementType = "uml:LiteralInteger"
    literal_unlimited_natural_type: ElementType = "uml:LiteralUnlimitedNatural"
    literal_string_type: ElementType = "uml:LiteralString"
    literal_boolean_type: ElementType = "uml:LiteralBoolean"
    
    # Default values - XMI 2.1 compliant
    default_multiplicity_lower: MultiplicityValue = "1"
    default_multiplicity_upper: MultiplicityValue = "1"
    unlimited_multiplicity: MultiplicityValue = "*"
    
    # Aggregation defaults - XMI 2.1 compliant
    default_aggregation: str = AggregationType.NONE.value
    
    # Visibility defaults - XMI 2.1 compliant
    default_visibility: str = "public"
    
    def get_element_type(self, kind: str) -> ElementType:
        """Get UML type string for given element kind."""
        type_mapping: Dict[str, ElementType] = {
            "class": self.class_type,
            "enum": self.enum_type,
            "datatype": self.datatype_type,
            "typedef": self.datatype_type,
            "template": self.class_type,  # Templates are classes with template signature
            "struct": self.class_type,     # Structs are classes
            "union": self.class_type       # Unions are classes
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
