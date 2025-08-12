from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from uml_types import XmiId, ElementName
from core.uml_model import UmlElement


@dataclass
class NamespaceNode:
    name: str
    xmi_id: Optional[XmiId] = None
    children: Dict[str, "NamespaceNode"] = field(default_factory=dict)
    elements: List[XmiId] = field(default_factory=list)


def build_namespace_tree(elements: Dict[ElementName, UmlElement], precreated: Optional[Dict[str, XmiId]] = None) -> NamespaceNode:
    """Build a NamespaceNode tree from elements keyed by qualified names.

    - elements: mapping of ElementName (qualified) -> UmlElement
    - precreated: optional mapping namespace string -> XmiId for existing package IDs
    """
    root = NamespaceNode(name="__root__", xmi_id=None)
    precreated = precreated or {}

    # Precreate top-level namespaces
    for ns_name, ns_xmi in precreated.items():
        parts = ns_name.split("::")
        current = root
        for part in parts:
            if part not in current.children:
                current.children[part] = NamespaceNode(name=part)
            current = current.children[part]
        current.xmi_id = ns_xmi

    for qname, info in elements.items():
        name_str = str(qname)
        parts = name_str.split("::")
        if len(parts) == 1:
            # root-level element
            root.elements.append(info.xmi)
            continue
        current = root
        for part in parts[:-1]:
            if part not in current.children:
                current.children[part] = NamespaceNode(name=part)
            current = current.children[part]
        current.elements.append(info.xmi)

    return root


