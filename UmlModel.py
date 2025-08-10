from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Any
from enum import Enum

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

# ---------- Member structure ----------
@dataclass
class UmlMember:
    name: str
    type_repr: Optional[str]
    visibility: Visibility = Visibility.PRIVATE
    is_static: bool = False
    is_abstract: bool = False
    multiplicity: str = "1"

# ---------- Clang metadata ----------
@dataclass
class ClangMetadata:
    is_abstract: bool = False
    is_enum: bool = False
    is_typedef: bool = False
    is_interface: bool = False
    is_struct: bool = False
    is_datatype: bool = False
    qualified_name: Optional[str] = None
    display_name: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    kind: Optional[str] = None

# ---------- UML Element structure ----------
@dataclass
class UmlElement:
    xmi: str
    name: str
    kind: ElementKind
    members: List[UmlMember]
    clang: ClangMetadata
    used_types: Set[str]
    underlying: Optional[str] = None
    operations: List[Dict[str, Any]] = None  # List of operation dictionaries
    templates: List[str] = None  # List of template parameter names
    literals: List[str] = None  # List of enum literal names
    original_data: Optional[Dict[str, Any]] = None  # Store original raw data
    
    def __post_init__(self):
        if self.operations is None:
            self.operations = []
        if self.templates is None:
            self.templates = []
        if self.literals is None:
            self.literals = []

# ---------- Association structure ----------
@dataclass
class UmlAssociation:
    src: str  # source element XMI ID
    tgt: str  # target element XMI ID
    aggregation: AggregationType = AggregationType.NONE
    multiplicity: str = "1"
    name: str = ""
    _assoc_id: Optional[str] = None
    _end1_id: Optional[str] = None
    _end2_id: Optional[str] = None

# ---------- Model returned by analyzer ----------
@dataclass
class UmlModel:
    elements: Dict[str, UmlElement]
    associations: List[UmlAssociation]
    dependencies: List[Tuple[str, str]]  # (owner_name, type_name)
    generalizations: List[Tuple[str, str]]  # (child_id, parent_id)
    name_to_xmi: Dict[str, str]  # name -> XMI ID mapping

