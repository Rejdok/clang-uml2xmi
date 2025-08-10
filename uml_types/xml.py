#!/usr/bin/env python3
"""
XML/XMI types for UML2Papyrus project.
"""

from typing import List, Dict, NewType, TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import XmlElement

# ---------- Type aliases for XML/XMI ----------
ContextStack = List['XmlElement']
ElementAttributes = Dict[str, str]
ModelName = NewType('ModelName', str)
ModelId = NewType('ModelId', str)
IdString = NewType('IdString', str)
HashString = NewType('HashString', str)
