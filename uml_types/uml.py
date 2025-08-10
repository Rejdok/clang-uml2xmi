#!/usr/bin/env python3
"""
UML-specific types and enums for UML2Papyrus project.
"""

from typing import NewType, Literal
from enum import Enum

# ---------- Type aliases for UML elements ----------
XmiId = NewType('XmiId', str)
ElementName = NewType('ElementName', str)
TypeName = NewType('TypeName', str)
Multiplicity = Literal["0..1", "1", "0..*", "1..*", "*"]
Namespace = NewType('Namespace', str)
AttributeName = NewType('AttributeName', str)
ElementType = NewType('ElementType', str)
MultiplicityValue = NewType('MultiplicityValue', str)

# ---------- Enums for UML elements ----------
class ElementKind(Enum):
    CLASS = "class"
    ENUM = "enum"
    TYPEDEF = "typedef"
    INTERFACE = "interface"
    DATATYPE = "datatype"

class Visibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    PACKAGE = "package"

class AggregationType(Enum):
    NONE = "none"
    SHARED = "shared"
    COMPOSITE = "composite"

class Direction(Enum):
    """Parameter direction modifiers."""
    IN = "in"
    OUT = "out"
    INOUT = "inout"
    RETURN = "return"

# ---------- New enums for inheritance ----------
class InheritanceType(Enum):
    """Type of inheritance relationship."""
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    VIRTUAL = "virtual"
    FINAL = "final"

class InheritanceModifier(Enum):
    """Modifiers for inheritance."""
    NONE = "none"
    VIRTUAL = "virtual"
    FINAL = "final"
    ABSTRACT = "abstract"
