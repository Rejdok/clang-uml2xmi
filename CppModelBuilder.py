

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
    def extract_namespace(qualified_name: str) -> Optional[str]:
        """Extract namespace from qualified name (e.g., 'std::vector' -> 'std')."""
        if not qualified_name or '::' not in qualified_name:
            return None
        
        # Split by :: and take everything except the last part
        parts = qualified_name.split('::')
        if len(parts) <= 1:
            return None
            
        # Return namespace part (everything except the last part)
        return '::'.join(parts[:-1])
    
    @staticmethod
    def extract_simple_name(qualified_name: str) -> str:
        """Extract simple name from qualified name (e.g., 'std::vector' -> 'vector')."""
        if not qualified_name:
            return ""
        
        if '::' in qualified_name:
            return qualified_name.split('::')[-1]
        
        return qualified_name

    @staticmethod
    def choose_name(el: RawElementData) -> ElementName:
        # Priority order for choosing element names
        # 1. display_name (user-friendly name)
        # 2. name (simple name)
        # 3. Never use internal ID as it's not meaningful
        
        # Note: qualified_name is handled separately in prepare() method
        
        name = el.get("display_name") 
        if name and name.strip():
            return ElementName(name.strip())
            
        name = el.get("name")
        if name and name.strip():
            return ElementName(name.strip())
        
        # If no meaningful name found, generate a descriptive one
        kind = el.get("type") or el.get("kind") or "element"
        return ElementName(f"unnamed_{kind}_{xid()}")

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
        # Priority order for member names
        mname: str = m.get("display_name") or m.get("name") or "unnamed_member"
        if not mname or mname.strip() == "":
            mname = "unnamed_member"
            
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
        # Priority order for operation names
        opname: str = op.get("display_name") or op.get("name") or op.get("signature") or "unnamed_operation"
        if not opname or opname.strip() == "":
            opname = "unnamed_operation"
            
        visibility_str: str = op.get("access") or op.get("visibility") or "public"
        visibility = Visibility(visibility_str) if visibility_str in [v.value for v in Visibility] else Visibility.PUBLIC
        is_static: bool = bool(op.get("is_static") or op.get("static") or False)
        is_abstract: bool = bool(op.get("is_pure_virtual") or op.get("is_abstract") or False)
        is_const: bool = bool(op.get("is_const") or False)
        is_virtual: bool = bool(op.get("is_virtual") or False)
        
        params: List[Any] = op.get("parameters") or op.get("params") or op.get("arguments") or []
        param_list: List[Tuple[str, str]] = []
        for p in params:
            # Priority order for parameter names
            pname: str = p.get("name") or "unnamed_param"
            if not pname or pname.strip() == "":
                pname = "unnamed_param"
                
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
                
            # Extract namespace and simple name
            qualified_name = el.get("qualified_name", "")
            namespace = self.extract_namespace(qualified_name) if qualified_name else None
            
            # Use qualified name if available, otherwise fall back to simple name
            if qualified_name and qualified_name.strip():
                chosen: ElementName = ElementName(qualified_name.strip())
            else:
                chosen: ElementName = self.choose_name(el)
                
            kind: ElementKind = self._get_element_kind(el)
            xmi: XmiId = XmiId(xid())
            
            # Create ClangMetadata
            clang_meta: ClangMetadata = self._create_clang_metadata(el)
            
            # Create UmlElement with namespace and empty members/used_types for now
            uml_element: UmlElement = UmlElement(
                xmi=xmi,
                name=chosen,
                kind=kind,
                members=[],
                clang=clang_meta,
                used_types=frozenset(),
                underlying=None,
                namespace=namespace,  # Add namespace
                original_data=el  # Store original raw data
            )
            
            self.created[chosen] = uml_element
            self.name_to_xmi[chosen] = xmi

    @staticmethod
    def normalize_template_name_for_matching(name: str) -> str:
        """Normalize template name for better matching."""
        if '<' in name:
            base, args = CppTypeParser.parse_template_args(name)
            # Try to find a pattern that matches the base template
            return base
        return name

    @staticmethod
    def find_best_template_match(template_name: str, candidates: List[Tuple[ElementName, UmlElement]]) -> Optional[XmiId]:
        """Find the best matching template class from candidates."""
        if not template_name or not candidates:
            return None
            
        # Extract base template name
        base_template = CppModelBuilder.normalize_template_name_for_matching(template_name)
        
        # First try exact base template match
        for candidate_name, candidate_info in candidates:
            if candidate_info.original_data and candidate_info.original_data.get('is_template', False):
                candidate_display = candidate_info.original_data.get('display_name', '')
                if candidate_display.startswith(base_template + '<'):
                    return candidate_info.xmi
        
        # Try namespace + simple name match
        if '::' in base_template:
            namespace = CppModelBuilder.extract_namespace(base_template)
            simple_name = CppModelBuilder.extract_simple_name(base_template)
            
            for candidate_name, candidate_info in candidates:
                if candidate_info.original_data:
                    candidate_namespace = CppModelBuilder.extract_namespace(str(candidate_info.name))
                    candidate_simple = CppModelBuilder.extract_simple_name(str(candidate_info.name))
                    
                    if candidate_namespace == namespace and candidate_simple == simple_name:
                        return candidate_info.xmi
        
        return None

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
                # Extract ID if available
                base_info["id"] = base.get("id")
            elif isinstance(base, str):
                # Base class as string
                base_info["name"] = base.strip()
                base_info["access"] = "public"  # Default to public
                base_info["is_virtual"] = False
                base_info["is_final"] = False
                base_info["id"] = None
            else:
                # Fallback
                base_info["name"] = str(base)
                base_info["access"] = "public"
                base_info["is_virtual"] = False
                base_info["is_final"] = False
                base_info["id"] = None
                
            if base_info["name"] and not any(b["name"] == base_info["name"] for b in base_classes):
                base_classes.append(base_info)
                
        return base_classes

    def _resolve_base_class_references(self) -> None:
        """Resolve base class names to XMI IDs and create generalizations."""
        from uml_types import InheritanceType
        
        # Create a mapping from ID to element for faster lookup
        id_to_element = {}
        for name, info in self.created.items():
            if info.original_data and 'id' in info.original_data:
                id_to_element[info.original_data['id']] = info
        
        for name, info in self.created.items():
            if info.original_data is None:
                continue
                
            base_classes = self._extract_base_classes(info.original_data)
            
            for base_info in base_classes:
                base_name = base_info["name"]
                base_id = base_info.get("id")  # Try to get ID directly
                
                base_xmi_id = None
                
                # First try to find by ID if available
                if base_id and base_id in id_to_element:
                    base_xmi_id = id_to_element[base_id].xmi
                    print(f"Found base class by ID: {name} -> {base_name} (ID: {base_id})")
                
                # If not found by ID, try to find by name
                if not base_xmi_id:
                    # Try exact name match first
                    base_xmi_id = self.name_to_xmi.get(ElementName(base_name))
                    
                    if base_xmi_id:
                        print(f"Found base class by exact name: {name} -> {base_name}")
                
                # If still not found, try to find by display_name
                if not base_xmi_id:
                    # Search through all created elements for matching display_name
                    for candidate_name, candidate_info in self.created.items():
                        if (candidate_info.original_data and 
                            candidate_info.original_data.get('display_name') == base_name):
                            base_xmi_id = candidate_info.xmi
                            print(f"Found base class by display_name: {name} -> {base_name}")
                            break
                
                # If still not found, try to find by template base name
                if not base_xmi_id and '<' in base_name:
                    # Extract base template name (e.g., "spdlog::details::flag_formatter<ScopedPadder>" -> "spdlog::details::flag_formatter")
                    base_template, _ = CppTypeParser.parse_template_args(base_name)
                    if base_template:
                        # Use the new template matching method
                        candidates = [(name, info) for name, info in self.created.items()]
                        base_xmi_id = self.find_best_template_match(base_name, candidates)
                        if base_xmi_id:
                            print(f"Found base class by template base: {name} -> {base_name} (matched template: {base_template})")
                
                # If still not found, try to find by namespace + simple name
                if not base_xmi_id and '::' in base_name:
                    namespace = self.extract_namespace(base_name)
                    simple_name = self.extract_simple_name(base_name)
                    
                    # Try to find by namespace + simple name combination
                    for candidate_name, candidate_info in self.created.items():
                        if candidate_info.original_data:
                            candidate_namespace = self.extract_namespace(str(candidate_info.name))
                            candidate_simple = self.extract_simple_name(str(candidate_info.name))
                            
                            if candidate_namespace == namespace and candidate_simple == simple_name:
                                base_xmi_id = candidate_info.xmi
                                print(f"Found base class by namespace+name: {name} -> {base_name} (matched: {candidate_name})")
                                break
                
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
                        # Priority order for template parameter names
                        tname: str = t.get("name") or t.get("display_name") or t.get("type") or "T"
                        if not tname or tname.strip() == "":
                            tname = "T"
                        # Store additional template info for better analysis
                        if hasattr(info, 'template_details'):
                            info.template_details.append(t)
                        else:
                            info.template_details = [t]
                    else:
                        tname = str(t)
                        if not tname or tname.strip() == "":
                            tname = "T"
                    info.templates.append(tname)
                
                # Mark as template if not already marked
                if not info.original_data.get('is_template', False):
                    info.original_data['is_template'] = True
            else:
                # Only parse template args if we don't have explicit template info
                # and the name contains template syntax
                if '<' in str(info.name):
                    base, args = CppTypeParser.parse_template_args(str(info.name))
                    if args:
                        info.templates = args
                        # Keep the original name with namespace, just remove template args
                        # The namespace is preserved in the name
                        info.name = ElementName(base)
                        # Mark as template
                        if not info.original_data.get('is_template', False):
                            info.original_data['is_template'] = True

            if kind == ElementKind.ENUM:
                enumerators: List[RawEnumeratorData] = el.get("enumerators") or el.get("values") or el.get("literals") or []
                info.literals = []
                for lit in enumerators:
                    if isinstance(lit, dict):
                        # Priority order for enum literal names
                        lname: str = lit.get("name") or lit.get("value") or "unnamed_literal"
                        if not lname or lname.strip() == "":
                            lname = "unnamed_literal"
                    else:
                        lname = str(lit)
                        if not lname or lname.strip() == "":
                            lname = "unnamed_literal"
                    info.literals.append(lname)
                continue

            if kind == ElementKind.TYPEDEF:
                underlying: RawUnderlyingTypeData = el.get("underlying_type") or el.get("type") or el.get("alias_of") or {}
                ustr: Optional[str] = None
                if isinstance(underlying, dict):
                    # Priority order for underlying type names
                    ustr = underlying.get("name") or underlying.get("display_name") or underlying.get("qualified_name")
                    if not ustr or ustr.strip() == "":
                        ustr = None
                elif isinstance(underlying, str):
                    ustr = underlying.strip() if underlying.strip() else None
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
                    # Skip non-dict member data as it's not useful
                    continue

            # operations
            operations: List[RawOperationData] = el.get("methods") or el.get("functions") or el.get("operations") or []
            info.operations = []
            used_types_set: Set[TypeName] = set()  # Temporary set for collecting types
            
            for op in operations:
                if isinstance(op, dict):
                    uml_operation: UmlOperation = self._create_uml_operation(op)
                    info.operations.append(uml_operation)
                    
                    # Collect used types from operation
                    if uml_operation.return_type:
                        used_types_set.add(TypeName(uml_operation.return_type))
                    for param_name, param_type in uml_operation.parameters:
                        if param_type:
                            used_types_set.add(TypeName(param_type))
                else:
                    # Skip non-dict operation data as it's not useful
                    continue
            
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

