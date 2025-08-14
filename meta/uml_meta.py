from dataclasses import dataclass
from typing import Dict

ElementType = str


@dataclass
class UmlMetaModel:
    class_type: ElementType = "uml:Class"
    enum_type: ElementType = "uml:Enumeration"
    datatype_type: ElementType = "uml:DataType"
    association_type: ElementType = "uml:Association"
    package_type: ElementType = "uml:Package"
    artifact_type: ElementType = "uml:Artifact"
    dependency_type: ElementType = "uml:Dependency"
    generalization_type: ElementType = "uml:Generalization"

    template_signature_type: ElementType = "uml:RedefinableTemplateSignature"
    template_parameter_type: ElementType = "uml:TemplateParameter"
    template_parameter_substitution_type: ElementType = "uml:TemplateParameterSubstitution"

    property_type: ElementType = "uml:Property"
    operation_type: ElementType = "uml:Operation"
    parameter_type: ElementType = "uml:Parameter"

    literal_integer_type: ElementType = "uml:LiteralInteger"
    literal_unlimited_natural_type: ElementType = "uml:LiteralUnlimitedNatural"
    literal_string_type: ElementType = "uml:LiteralString"
    literal_boolean_type: ElementType = "uml:LiteralBoolean"

    default_multiplicity_lower: str = "1"
    default_multiplicity_upper: str = "1"
    unlimited_multiplicity: str = "*"

    default_aggregation: str = "none"
    default_visibility: str = "public"

    def get_element_type(self, kind: str) -> ElementType:
        mapping: Dict[str, ElementType] = {
            "class": self.class_type,
            "enum": self.enum_type,
            "datatype": self.datatype_type,
            "typedef": self.datatype_type,
            "template": self.class_type,
            "struct": self.class_type,
            "union": self.class_type,
            "package": self.package_type,
            "artifact": self.artifact_type,
        }
        return mapping.get(kind, self.class_type)


