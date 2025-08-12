from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Union, Any
from uml_types import (
    XmiId, ElementName, TypeName, Multiplicity, 
    ElementKind, Visibility, AggregationType,
    TypedList, TypedDict, Namespace
)

# ---------- Member structure ----------
@dataclass
class UmlMember:
    name: str
    type_repr: Optional[str]
    visibility: Visibility = Visibility.PRIVATE
    is_static: bool = False
    is_abstract: bool = False
    multiplicity: Multiplicity = "1"

# ---------- Operation structure ----------
@dataclass
class UmlOperation:
    name: str
    return_type: Optional[str]
    parameters: List[Tuple[str, str]]  # (name, type)
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_abstract: bool = False
    is_const: bool = False
    is_virtual: bool = False

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
    xmi: XmiId
    name: ElementName
    kind: ElementKind
    members: List[UmlMember]
    clang: ClangMetadata
    used_types: frozenset[TypeName]
    underlying: Optional[TypeName] = None
    operations: List[UmlOperation] = None  # List of UmlOperation objects
    templates: List[str] = None  # List of template parameter names
    literals: List[str] = None  # List of enum literal names
    namespace: Optional[str] = None  # Namespace for this element
    original_data: Optional[Dict[str, Any]] = None  # Store original raw data (structure may vary)
    # Extended fields for stub/template handling
    is_stub: bool = False
    instantiation_of: Optional[XmiId] = None
    instantiation_args: List[XmiId] = field(default_factory=list)
    
    def __post_init__(self):
        if self.operations is None:
            self.operations = []
        if self.templates is None:
            self.templates = []
        if self.literals is None:
            self.literals = []
        
        # Validate that the kind matches the content
        self._validate_kind_content()
    
    def _validate_kind_content(self) -> None:
        """Validate that the element kind matches its content."""
        # Note: During construction, enums may have empty literals list
        # The final validation should be done after the model is fully built
        
        if self.kind == ElementKind.DATATYPE and self.members:
            raise ValueError(f"Datatype element '{self.name}' should not have members")
    
    @property
    def is_template(self) -> bool:
        """Check if this element is a template."""
        return bool(self.templates)
    
    @property
    def has_operations(self) -> bool:
        """Check if this element has operations."""
        return bool(self.operations)
    
    @property
    def public_members(self) -> List[UmlMember]:
        """Get all public members."""
        return [member for member in self.members if member.visibility == Visibility.PUBLIC]

# ---------- Association structure ----------
@dataclass
class UmlAssociation:
    src: XmiId  # source element XMI ID
    tgt: XmiId  # target element XMI ID
    aggregation: AggregationType = AggregationType.NONE
    multiplicity: str = "1"
    name: str = ""
    _assoc_id: Optional[XmiId] = None
    _end1_id: Optional[XmiId] = None
    _end2_id: Optional[XmiId] = None

# ---------- New: Generalization structure ----------
@dataclass
class UmlGeneralization:
    """Represents inheritance relationship between UML elements."""
    child_id: XmiId  # Child element XMI ID
    parent_id: XmiId  # Parent element XMI ID
    inheritance_type: 'InheritanceType' = None  # Type of inheritance (public/private/protected)
    is_virtual: bool = False  # Virtual inheritance
    is_final: bool = False  # Final class (cannot be inherited)
    _gen_id: Optional[XmiId] = None  # Generalization element XMI ID
    
    def __post_init__(self):
        # Import here to avoid circular imports
        from uml_types import InheritanceType
        if self.inheritance_type is None:
            self.inheritance_type = InheritanceType.PUBLIC  # Default to public inheritance

# ---------- Model returned by analyzer ----------
@dataclass
class UmlModel:
    elements: TypedDict[XmiId, UmlElement]
    associations: TypedList[UmlAssociation]
    dependencies: TypedList[Tuple[ElementName, TypeName]]  # (owner_name, type_name)
    generalizations: TypedList[UmlGeneralization]  # Updated: Use UmlGeneralization objects
    name_to_xmi: TypedDict[ElementName, XmiId]  # name -> XMI ID mapping
    namespace_packages: Optional[TypedDict[str, XmiId]] = None  # NEW: namespace -> XMI ID mapping
    
    def __post_init__(self):
        """Initialize model after creation."""
        # Note: Validation is deferred until explicitly requested
        # to allow for incremental model building
        if self.namespace_packages is None:
            self.namespace_packages = {}
    
    def _validate_model_consistency(self) -> None:
        """Validate that the model is internally consistent."""
        # Check that all referenced elements exist
        for assoc in self.associations:
            if assoc.src not in self.elements:
                raise ValueError(f"Association references non-existent source element: {assoc.src}")
            if assoc.tgt not in self.elements:
                raise ValueError(f"Association references non-existent target element: {assoc.tgt}")
        
        # Check that all generalizations reference existing elements
        for gen in self.generalizations:
            if gen.child_id not in self.elements:
                raise ValueError(f"Generalization references non-existent child element: {gen.child_id}")
            if gen.parent_id not in self.elements:
                raise ValueError(f"Generalization references non-existent parent element: {gen.parent_id}")
        
        # Validate that enum elements have literals
        for element in self.elements.values():
            if element.kind == ElementKind.ENUM and not element.literals:
                raise ValueError(f"Enum element '{element.name}' must have literals")
    
    def get_element_by_name(self, name: ElementName) -> Optional[UmlElement]:
        """Get element by its name."""
        xmi_id = self.name_to_xmi.get(name)
        return self.elements.get(xmi_id) if xmi_id else None
    
    def get_elements_by_kind(self, kind: ElementKind) -> List[UmlElement]:
        """Get all elements of a specific kind."""
        return [elem for elem in self.elements.values() if elem.kind == kind]
    
    def get_associated_elements(self, element_id: XmiId) -> List[UmlElement]:
        """Get all elements associated with the given element."""
        associated_ids = set()
        for assoc in self.associations:
            if assoc.src == element_id:
                associated_ids.add(assoc.tgt)
            elif assoc.tgt == element_id:
                associated_ids.add(assoc.src)
        
        return [self.elements[elem_id] for elem_id in associated_ids if elem_id in self.elements]
    
    def get_parent_elements(self, element_id: XmiId) -> List[UmlElement]:
        """Get all parent elements for the given element."""
        parent_ids = [gen.parent_id for gen in self.generalizations if gen.child_id == element_id]
        return [self.elements[parent_id] for parent_id in parent_ids if parent_id in self.elements]
    
    def get_child_elements(self, element_id: XmiId) -> List[UmlElement]:
        """Get all child elements for the given element."""
        child_ids = [gen.child_id for gen in self.generalizations if gen.parent_id == element_id]
        return [self.elements[child_id] for child_id in child_ids if child_id in self.elements]
    
    def get_inheritance_hierarchy(self, element_id: XmiId) -> List[UmlElement]:
        """Get complete inheritance hierarchy for the given element (including ancestors)."""
        hierarchy = []
        current_id = element_id
        
        while current_id in self.elements:
            current_element = self.elements[current_id]
            hierarchy.append(current_element)
            
            # Find parent
            parent_gens = [gen for gen in self.generalizations if gen.child_id == current_id]
            if not parent_gens:
                break
                
            current_id = parent_gens[0].parent_id
            
            # Prevent infinite loops
            if current_id in [elem.xmi for elem in hierarchy]:
                break
        
        return hierarchy
    
    def validate(self) -> bool:
        """Validate the entire model and return True if valid."""
        try:
            self._validate_model_consistency()
            return True
        except ValueError:
            return False
    
    def validate_and_raise(self) -> None:
        """Validate the entire model and raise ValueError if invalid."""
        self._validate_model_consistency()

