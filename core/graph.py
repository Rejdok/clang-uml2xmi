from dataclasses import dataclass
from typing import Dict, List, Tuple
from uml_types import XmiId, ElementName, TypeName
from core.uml_model import UmlElement, UmlAssociation, UmlGeneralization
from .namespace import NamespaceNode, build_namespace_tree


@dataclass
class UmlGraph:
    elements_by_id: Dict[XmiId, UmlElement]
    name_to_xmi: Dict[ElementName, XmiId]
    associations: List[UmlAssociation]
    dependencies: List[Tuple[ElementName, TypeName]]
    generalizations: List[UmlGeneralization]
    namespaces: NamespaceNode

    @classmethod
    def from_builder_payload(
        cls,
        created: Dict[ElementName, UmlElement],
        name_to_xmi: Dict[ElementName, XmiId],
        associations: List[UmlAssociation],
        dependencies: List[Tuple[ElementName, TypeName]],
        generalizations: List[UmlGeneralization],
        namespace_packages: Dict[str, XmiId] | None = None,
    ) -> "UmlGraph":
        elements_by_id = {elem.xmi: elem for elem in created.values()}
        namespaces = build_namespace_tree(created, precreated=namespace_packages or {})
        return cls(
            elements_by_id=elements_by_id,
            name_to_xmi=name_to_xmi,
            associations=associations,
            dependencies=dependencies,
            generalizations=generalizations,
            namespaces=namespaces,
        )


