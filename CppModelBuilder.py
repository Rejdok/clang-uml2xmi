

# ---------- Model builder (parser + initial analysis) ----------
from typing import Dict, Any, List, Tuple, Set, Optional, Union, cast, TypedDict
from CppParser import CppTypeParser
from Utils import xid
from UmlModel import (
    UmlElement, UmlMember, UmlAssociation, ClangMetadata, 
    UmlOperation, UmlModel, UmlGeneralization
)
from uml_types import (
    ElementKind, Visibility, AggregationType,
    XmiId, ElementName, TypeName, BuildResult
)

from uml_types import (
    RawElementData, RawMemberData, RawOperationData,
    RawTemplateData, RawEnumeratorData, RawUnderlyingTypeData,
    RawBaseClassData, RawInheritanceData
)

class CppModelBuilder:
    def __init__(self, j: Dict[str, Any]) -> None:
        self.j: Dict[str, Any] = j
        # mapping from chosen name (fallback) to xmi id
        self.name_to_xmi: Dict[ElementName, XmiId] = {}
        # internal store of created element metadata
        self.created: Dict[ElementName, UmlElement] = {}
        self.associations: List[UmlAssociation] = []
        self.dependencies: List[Tuple[ElementName, TypeName]] = []
        # New: store inheritance relationships
        self.generalizations: List[UmlGeneralization] = []

    @staticmethod
    def choose_name(el: RawElementData) -> ElementName:
        return ElementName(el.get("qualified_name") or el.get("display_name") or el.get("name") or el.get("id") or xid())

    def _create_clang_metadata(self, el: RawElementData) -> ClangMetadata:
        """Create ClangMetadata from raw clang data."""
        return ClangMetadata(
            is_abstract=bool(el.get("is_abstract", False)),
            is_enum=bool(el.get("is_enum", False)),
            is_typedef=bool(el.get("is_typedef", False) or el.get("is_alias", False)),
            is_interface=bool(el.get("is_interface", False)),
            is_struct=bool(el.get("is_struct", False) or el.get("is_datatype", False)),
            is_datatype=bool(el.get("is_datatype", False)),
            qualified_name=el.get("qualified_name"),
            display_name=el.get("display_name"),
            name=el.get("name"),
            type=el.get("type"),
            kind=el.get("kind")
        )

    def _create_uml_member(self, m: RawMemberData) -> UmlMember:
        """Create UmlMember from raw member data."""
        mname: str = m.get("display_name") or m.get("name") or m.get("id") or ""
        visibility_str: str = m.get("access") or m.get("visibility") or "private"
        visibility = Visibility(visibility_str) if visibility_str in [v.value for v in Visibility] else Visibility.PRIVATE
        is_static: bool = bool(m.get("is_static") or m.get("static") or False)
        mtypeobj: Any = m.get("type") or m.get("type_info") or {}
        tname: Optional[str] = CppTypeParser.safe_type_name(mtypeobj) or m.get("type_name") or m.get("type")
        return UmlMember(
            name=mname,
            type_repr=tname,
            visibility=visibility,
            is_static=is_static
        )

    def _create_uml_operation(self, op: RawOperationData) -> UmlOperation:
        """Create UmlOperation from raw operation data."""
        opname: str = op.get("display_name") or op.get("name") or op.get("signature") or "op"
        visibility_str: str = op.get("access") or op.get("visibility") or "public"
        visibility = Visibility(visibility_str) if visibility_str in [v.value for v in Visibility] else Visibility.PUBLIC
        is_static: bool = bool(op.get("is_static") or op.get("static") or False)
        is_abstract: bool = bool(op.get("is_pure_virtual") or op.get("is_abstract") or False)
        is_const: bool = bool(op.get("is_const") or False)
        is_virtual: bool = bool(op.get("is_virtual") or False)
        
        params: List[Any] = op.get("parameters") or op.get("params") or op.get("arguments") or []
        param_list: List[Tuple[str, str]] = []
        for p in params:
            pname: str = p.get("name") or p.get("id") or "p"
            ptype: str = CppTypeParser.safe_type_name(p.get("type")) or p.get("type_name") or "void"
            param_list.append((pname, ptype))
        
        rt: Optional[str] = CppTypeParser.safe_type_name(op.get("return_type")) or CppTypeParser.safe_type_name(op.get("type")) or CppTypeParser.safe_type_name(op.get("returnType"))
        
        return UmlOperation(
            name=opname,
            return_type=rt,
            parameters=param_list,
            visibility=visibility,
            is_static=is_static,
            is_abstract=is_abstract,
            is_const=is_const,
            is_virtual=is_virtual
        )

    def _get_element_kind(self, el: RawElementData) -> ElementKind:
        """Determine ElementKind from clang data."""
        kind_raw: str = (el.get("type") or el.get("kind") or "").lower()
        if "enum" in kind_raw or el.get("is_enum"):
            return ElementKind.ENUM
        elif "typedef" in kind_raw or el.get("is_typedef") or el.get("is_alias"):
            return ElementKind.TYPEDEF
        elif "interface" in kind_raw or el.get("is_interface"):
            return ElementKind.INTERFACE
        elif "struct" in kind_raw or el.get("is_struct") or el.get("is_datatype"):
            return ElementKind.DATATYPE
        else:
            return ElementKind.CLASS

    def prepare(self) -> None:
        elements: List[RawElementData] = self.j.get("elements") or self.j.get("entities") or self.j.get("types") or []
        for el in elements:
            if not isinstance(el, dict):
                continue
            chosen: ElementName = self.choose_name(el)
            kind: ElementKind = self._get_element_kind(el)
            xmi: XmiId = XmiId(xid())
            
            # Create ClangMetadata
            clang_meta: ClangMetadata = self._create_clang_metadata(el)
            
            # Create UmlElement with empty members and used_types for now
            uml_element: UmlElement = UmlElement(
                xmi=xmi,
                name=chosen,
                kind=kind,
                members=[],
                clang=clang_meta,
                used_types=frozenset(),
                underlying=None,
                original_data=el  # Store original raw data
            )
            
            self.created[chosen] = uml_element
            self.name_to_xmi[chosen] = xmi

    def _extract_base_classes(self, el: RawElementData) -> List[Dict[str, Any]]:
        """Extract base class information from element data."""
        base_classes: List[Dict[str, Any]] = []
        
        # Try different possible field names for base classes
        bases_data = (
            el.get("bases") or 
            el.get("base_classes") or 
            el.get("inherits_from") or 
            el.get("parent_classes") or 
            el.get("superclasses") or
            []
        )
        
        if not bases_data:
            return base_classes
            
        for base in bases_data:
            base_info = {}
            
            if isinstance(base, dict):
                # Base class as object with metadata
                base_info["name"] = (
                    base.get("name") or 
                    base.get("qualified_name") or 
                    base.get("display_name") or 
                    base.get("type") or
                    str(base)
                )
                # Extract inheritance modifiers
                base_info["access"] = base.get("access", "public")  # public/private/protected
                base_info["is_virtual"] = bool(base.get("is_virtual", False))
                base_info["is_final"] = bool(base.get("is_final", False))
            elif isinstance(base, str):
                # Base class as string
                base_info["name"] = base.strip()
                base_info["access"] = "public"  # Default to public
                base_info["is_virtual"] = False
                base_info["is_final"] = False
            else:
                # Fallback
                base_info["name"] = str(base)
                base_info["access"] = "public"
                base_info["is_virtual"] = False
                base_info["is_final"] = False
                
            if base_info["name"] and not any(b["name"] == base_info["name"] for b in base_classes):
                base_classes.append(base_info)
                
        return base_classes

    def _resolve_base_class_references(self) -> None:
        """Resolve base class names to XMI IDs and create generalizations."""
        from uml_types import InheritanceType
        
        for name, info in self.created.items():
            if info.original_data is None:
                continue
                
            base_classes = self._extract_base_classes(info.original_data)
            
            for base_info in base_classes:
                base_name = base_info["name"]
                
                # Try to find the base class in our created elements
                base_xmi_id = self.name_to_xmi.get(ElementName(base_name))
                
                if base_xmi_id:
                    # Determine inheritance type
                    access = base_info.get("access", "public").lower()
                    if access == "private":
                        inheritance_type = InheritanceType.PRIVATE
                    elif access == "protected":
                        inheritance_type = InheritanceType.PROTECTED
                    else:
                        inheritance_type = InheritanceType.PUBLIC
                    
                    # Create generalization relationship
                    generalization = UmlGeneralization(
                        child_id=info.xmi,
                        parent_id=base_xmi_id,
                        inheritance_type=inheritance_type,
                        is_virtual=base_info.get("is_virtual", False),
                        is_final=base_info.get("is_final", False)
                    )
                    
                    # Check if this generalization already exists
                    existing = [g for g in self.generalizations 
                              if g.child_id == info.xmi and g.parent_id == base_xmi_id]
                    
                    if not existing:
                        self.generalizations.append(generalization)
                        print(f"Added inheritance: {name} -> {base_name} ({access})")
                else:
                    # Base class not found - add as dependency
                    if (info.name, TypeName(base_name)) not in self.dependencies:
                        self.dependencies.append((info.name, TypeName(base_name)))
                        print(f"Added dependency for unknown base class: {name} -> {base_name}")

    def build(self) -> BuildResult:
        # prepare if not done
        if not self.created:
            self.prepare()

        # second pass: collect members, operations, templates, typedef underlying, associations
        for name, info in list(self.created.items()):
            # Use original data instead of clang metadata for dictionary access
            el: RawElementData = info.original_data
            kind: ElementKind = info.kind

            # templates
            templates: List[RawTemplateData] = el.get("templates") or el.get("template_parameters") or el.get("template_args") or []
            if templates:
                info.templates = []
                for t in templates:
                    if isinstance(t, dict):
                        tname: str = t.get("name") or t.get("display_name") or t.get("type") or "T"
                    else:
                        tname = str(t)
                    info.templates.append(tname)
            else:
                base, args = CppTypeParser.parse_template_args(info.name)
                if args:
                    info.templates = args
                    info.name = base

            if kind == ElementKind.ENUM:
                enumerators: List[RawEnumeratorData] = el.get("enumerators") or el.get("values") or el.get("literals") or []
                info.literals = []
                for lit in enumerators:
                    if isinstance(lit, dict):
                        lname: str = lit.get("name") or lit.get("value") or str(lit)
                    else:
                        lname = str(lit)
                    info.literals.append(lname)
                continue

            if kind == ElementKind.TYPEDEF:
                underlying: RawUnderlyingTypeData = el.get("underlying_type") or el.get("type") or el.get("alias_of") or {}
                ustr: Optional[str] = None
                if isinstance(underlying, dict):
                    ustr = underlying.get("name") or underlying.get("display_name")
                elif isinstance(underlying, str):
                    ustr = underlying
                info.underlying = ustr
                continue

            # members
            members: List[RawMemberData] = el.get("members") or el.get("fields") or el.get("variables") or []
            info.members = []
            for m in members:
                if isinstance(m, dict):
                    uml_member: UmlMember = self._create_uml_member(m)
                    info.members.append(uml_member)
                else:
                    # Create simple member for non-dict data
                    simple_member: UmlMember = UmlMember(
                        name=str(m),
                        type_repr=None,
                        visibility=Visibility.PRIVATE,
                        is_static=False
                    )
                    info.members.append(simple_member)

            # operations
            operations: List[RawOperationData] = el.get("methods") or el.get("functions") or el.get("operations") or []
            info.operations = []
            used_types_set: Set[TypeName] = set()  # Temporary set for collecting types
            
            for op in operations:
                uml_operation: UmlOperation = self._create_uml_operation(op)
                info.operations.append(uml_operation)
                
                # Collect used types from operation
                if uml_operation.return_type:
                    used_types_set.add(TypeName(uml_operation.return_type))
                for param_name, param_type in uml_operation.parameters:
                    if param_type:
                        used_types_set.add(TypeName(param_type))
            
            # Convert to frozenset and update the element
            if used_types_set:
                info.used_types = frozenset(used_types_set)

        # associations: for each member try to match known types
        for name, info in self.created.items():
            owner_xmi: XmiId = info.xmi
            raws: List[UmlMember] = info.members
            for m in raws:
                type_repr: Optional[str] = m.type_repr
                if not type_repr:
                    continue
                parsed: List[str] = CppTypeParser.extract_all_type_identifiers(type_repr)
                matched: List[str] = CppTypeParser.match_known_types_from_parsed(parsed, [str(k) for k in self.name_to_xmi.keys()])
                an: Dict[str, Any] = CppTypeParser.analyze_type_expr(type_repr)
                outer_base: str = an.get("template_base") or ""
                is_container: bool = any(k in outer_base for k in CppTypeParser._CONTAINER_KEYWORDS) or outer_base in CppTypeParser._CONTAINER_KEYWORDS
                is_smart: bool = any(k in outer_base for k in CppTypeParser._SMART_PTRS) or outer_base in CppTypeParser._SMART_PTRS
                for mt in matched:
                    tgt_xmi: Optional[XmiId] = self.name_to_xmi.get(ElementName(mt))
                    if not tgt_xmi:
                        continue
                    # heuristic aggregation
                    if is_smart:
                        aggregation_str: str = "composite" if "unique" in outer_base or "unique_ptr" in outer_base else "shared"
                        # UML uses 'shared' not standard; keep 'none' or 'composite'
                        if aggregation_str not in ("composite", "shared"):
                            aggregation_str = "none"
                    else:
                        if an["is_pointer"] or an["is_reference"] or an["is_rref"]:
                            aggregation_str = "shared"
                        else:
                            aggregation_str = "none"
                    
                    # Convert string to AggregationType enum
                    try:
                        aggregation: AggregationType = AggregationType(aggregation_str)
                    except ValueError:
                        aggregation = AggregationType.NONE
                    
                    mult: str = "*" if is_container or an["is_array"] else "1"
                    
                    association: UmlAssociation = UmlAssociation(
                        src=owner_xmi,
                        tgt=tgt_xmi,
                        aggregation=aggregation,
                        multiplicity=mult,
                        name=m.name
                    )
                    self.associations.append(association)

        # dependencies: types used but unknown
        for name, info in self.created.items():
            used: frozenset[TypeName] = info.used_types or frozenset()
            for typename in used:
                if not typename:
                    continue
                # skip if known as element
                # match via parsed tokens
                if ElementName(str(typename)) in self.name_to_xmi:
                    continue
                parsed: List[str] = CppTypeParser.extract_all_type_identifiers(str(typename))
                cand: List[str] = CppTypeParser.match_known_types_from_parsed(parsed, [str(k) for k in self.name_to_xmi.keys()])
                if cand:
                    # already accounted as association maybe; otherwise add dependency to first match
                    continue
                self.dependencies.append((info.name, TypeName(str(typename))))

        # NEW: Process inheritance relationships
        self._resolve_base_class_references()

        # expose project_name + created + lists
        project_name: str = self.j.get("project_name") or self.j.get("project") or "clang_uml_model"
        return {
            "project_name": project_name,
            "created": self.created,
            "associations": self.associations,
            "dependencies": self.dependencies,
            "generalizations": self.generalizations,  # NEW: Include generalizations
            "name_to_xmi": self.name_to_xmi
        }

