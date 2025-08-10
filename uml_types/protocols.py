#!/usr/bin/env python3
"""
Protocols and typed structures for UML2Papyrus project.
"""

from typing import Dict, List, Tuple, Optional, Any, Protocol
from .uml import ElementName, TypeName, XmiId

# ---------- Protocol definitions ----------
class XmlElement(Protocol):
    """Protocol for XML element context."""
    def __enter__(self) -> 'XmlElement': ...
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None: ...

# ---------- Typed structures ----------
class BuildResult(Dict[str, Any]):
    """Typed return structure for build method."""
    elements: Dict[ElementName, 'UmlElement']
    associations: List['UmlAssociation']
    dependencies: List[Tuple[ElementName, TypeName]]
    generalizations: List[Tuple[XmiId, XmiId]]  # (child_id, parent_id)
    name_to_xmi: Dict[ElementName, XmiId]

class TypeAnalysisResult(Dict[str, Any]):
    """Structured type analysis result."""
    raw: Optional[str]
    base: str
    is_pointer: bool
    is_reference: bool
    is_rref: bool
    is_array: bool
    template_base: Optional[str]
    template_args: List[str]

# Forward references for circular imports
UmlElement = 'UmlElement'
UmlAssociation = 'UmlAssociation'
