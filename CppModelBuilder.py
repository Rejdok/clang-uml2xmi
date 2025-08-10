

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
            # Validate parameter data structure
            if not isinstance(p, dict):
                import logging
                logging.warning(f"Skipping non-dict parameter data: {p}")
                continue
            
            # Check for unexpected data structure that might cause direction issues
            if "direction" in p:
                import logging
                logging.warning(f"Parameter has unexpected 'direction' field: {p}")
                
            # Priority order for parameter names
            pname: str = p.get("name") or "unnamed_param"
            if not pname or pname.strip() == "":
                pname = "unnamed_param"
            
            # Ensure parameter name is not an ID
            if pname.startswith("id_"):
                import logging
                logging.warning(f"Parameter name appears to be an ID, using 'unnamed_param': {pname}")
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

    def _create_missing_template_elements(self) -> None:
        """Create missing template elements for unresolved template dependencies."""
        missing_templates: Set[str] = set()
        
        # Collect all template types mentioned in dependencies
        for name, info in self.created.items():
            if info.original_data and info.original_data.get('is_template', False):
                # Check if this template has unresolved dependencies
                if hasattr(info, 'template_details') and info.template_details:
                    for template_detail in info.template_details:
                        if isinstance(template_detail, dict):
                            template_type = template_detail.get('type') or template_detail.get('name')
                            if template_type and ElementName(template_type) not in self.name_to_xmi:
                                missing_templates.add(template_type)
        
        # Create missing template elements
        for template_type in missing_templates:
            if template_type not in [str(name) for name in self.created.keys()]:
                # Create a placeholder template element
                template_id = f"template_{len(self.created)}"
                template_element = UmlElement(
                    xmi=template_id,
                    name=ElementName(template_type),
                    kind=ElementKind.CLASS,  # Assume class for now
                    members=[],
                    clang=ClangMetadata(is_abstract=False, is_template=True),
                    used_types=frozenset(),
                    templates=[],  # Will be populated later
                    original_data={
                        'name': template_type,
                        'display_name': template_type,
                        'is_template': True,
                        'kind': 'class'
                    }
                )
                
                self.created[ElementName(template_type)] = template_element
                self.name_to_xmi[ElementName(template_type)] = template_id
                print(f"Created missing template element: {template_type}")

    def prepare(self) -> None:
        """Prepare the model by creating UML elements from raw data."""
        if self.created:
            return  # Already prepared
        
        # First pass: create UML elements
        for el in self.j.get("elements", []):
            if not isinstance(el, dict):
                continue
                
            # Choose the best name for this element
            name: ElementName = self.choose_name(el)
            if not name:
                continue
            
            # Create XMI ID
            xmi: XmiId = xid()
            
            # Create UML element
            info: UmlElement = UmlElement(
                xmi=xmi,
                name=name,
                kind=self._get_element_kind(el),
                members=[],
                clang=self._create_clang_metadata(el),
                used_types=frozenset(),
                original_data=el
            )
            
            # Store element
            self.created[name] = info
            self.name_to_xmi[name] = xmi
            
            # Extract members
            members_data: List[RawMemberData] = el.get("members") or el.get("fields") or el.get("attributes") or []
            for m in members_data:
                if isinstance(m, dict):
                    uml_member: UmlMember = self._create_uml_member(m)
                    info.members.append(uml_member)
        
        # NEW: Create missing template elements
        self._create_missing_template_elements()

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
        """Find the best matching template class from candidates with improved template handling."""
        if not template_name or not candidates:
            return None
            
        # Extract base template name and arguments
        base_template, template_args = CppTypeParser.parse_template_args(template_name)
        
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
        
        # NEW: Try partial template specialization matching
        if template_args:
            # Look for candidates that have the same number of template parameters
            for candidate_name, candidate_info in candidates:
                if (candidate_info.original_data and 
                    candidate_info.original_data.get('is_template', False) and
                    hasattr(candidate_info, 'templates') and 
                    candidate_info.templates):
                    
                    # Check if template parameter count matches
                    if len(candidate_info.templates) == len(template_args):
                        # Try to match by base name
                        candidate_display = candidate_info.original_data.get('display_name', '')
                        if candidate_display.startswith(base_template + '<'):
                            return candidate_info.xmi
        
        # NEW: Try fuzzy matching for template base names
        for candidate_name, candidate_info in candidates:
            if candidate_info.original_data and candidate_info.original_data.get('is_template', False):
                candidate_display = candidate_info.original_data.get('display_name', '')
                candidate_name_str = str(candidate_info.name)
                
                # Check if base template names are similar (ignoring namespaces)
                candidate_base = CppModelBuilder.extract_simple_name(candidate_display)
                target_base = CppModelBuilder.extract_simple_name(base_template)
                
                if candidate_base == target_base:
                    return candidate_info.xmi
        
        return None

    @staticmethod
    def resolve_template_dependencies(template_name: str, candidates: List[Tuple[ElementName, UmlElement]]) -> List[XmiId]:
        """Resolve all template dependencies for a given template type."""
        resolved_ids = []
        
        if not template_name or not candidates:
            return resolved_ids
            
        base_template, template_args = CppTypeParser.parse_template_args(template_name)
        
        # Resolve base template
        base_id = CppModelBuilder.find_best_template_match(template_name, candidates)
        if base_id:
            resolved_ids.append(base_id)
        
        # Resolve template arguments
        for arg in template_args:
            # Try to find the argument type in candidates
            for candidate_name, candidate_info in candidates:
                if str(candidate_info.name) == arg or candidate_info.original_data.get('display_name') == arg:
                    resolved_ids.append(candidate_info.xmi)
                    break
                # Also try with template argument parsing
                elif '<' in arg:
                    arg_base, _ = CppTypeParser.parse_template_args(arg)
                    if str(candidate_info.name).endswith(arg_base) or candidate_info.original_data.get('display_name', '').endswith(arg_base):
                        resolved_ids.append(candidate_info.xmi)
                        break
        
        return resolved_ids

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
                    None  # Don't use str(base) for dict
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
                # Fallback - only use str() for non-dict types
                if not isinstance(base, dict):
                    base_info["name"] = str(base)
                else:
                    base_info["name"] = None
                base_info["access"] = "public"
                base_info["is_virtual"] = False
                base_info["is_final"] = False
                base_info["id"] = None
            
            # Debug: log the structure of base_info
            print(f"DEBUG: base_info structure: {base_info}")
            print(f"DEBUG: base_info['name'] type: {type(base_info['name'])}")
            print(f"DEBUG: base_info['name'] value: {base_info['name']}")
                
            if base_info["name"] and not any(b["name"] == base_info["name"] for b in base_classes):
                base_classes.append(base_info)
                
        return base_classes

    def _resolve_base_class_references(self) -> None:
        """Resolve base class names to XMI IDs and create generalizations with improved template handling."""
        from uml_types import InheritanceType
        
        # Create a mapping from ID to element for faster lookup
        id_to_element = {}
        for name, info in self.created.items():
            if info.original_data and info.original_data.get('id'):
                id_to_element[info.original_data['id']] = info
        
        # Process each element's base classes
        for name, info in self.created.items():
            if not info.original_data:
                continue
                
            base_classes = self._extract_base_classes(info.original_data)
            if not base_classes:
                continue
            
            for base_info in base_classes:
                base_name = base_info.get("name")
                if not base_name:
                    continue
                
                print(f"Processing base class: {name} -> {base_name}")
                
                # Try to find base class by various methods
                base_xmi_id: Optional[XmiId] = None
                
                # Method 1: Try to find by ID if available
                if base_info.get("id") and base_info["id"] in id_to_element:
                    base_xmi_id = id_to_element[base_info["id"]].xmi
                    print(f"Found base class by ID: {name} -> {base_name}")
                
                # Method 2: Try to find by exact name match
                if not base_xmi_id and ElementName(base_name) in self.name_to_xmi:
                    base_xmi_id = self.name_to_xmi[ElementName(base_name)]
                    print(f"Found base class by exact name: {name} -> {base_name}")
                
                # Method 3: Try to find by display_name
                if not base_xmi_id:
                    # Search through all created elements for matching display_name
                    for candidate_name, candidate_info in self.created.items():
                        if (candidate_info.original_data and 
                            candidate_info.original_data.get('display_name') == base_name):
                            base_xmi_id = candidate_info.xmi
                            print(f"Found base class by display_name: {name} -> {base_name}")
                            break
                
                # Method 4: Enhanced template base name resolution
                if not base_xmi_id and '<' in base_name:
                    # Extract base template name (e.g., "spdlog::details::flag_formatter<ScopedPadder>" -> "spdlog::details::flag_formatter")
                    base_template, template_args = CppTypeParser.parse_template_args(base_name)
                    if base_template:
                        # Use the improved template matching method
                        candidates = [(name, info) for name, info in self.created.items()]
                        base_xmi_id = self.find_best_template_match(base_name, candidates)
                        if base_xmi_id:
                            print(f"Found base class by template base: {name} -> {base_name} (matched template: {base_template})")
                        else:
                            # Try to resolve template dependencies
                            resolved_ids = self.resolve_template_dependencies(base_name, candidates)
                            if resolved_ids:
                                # Use the first resolved ID as the base class
                                base_xmi_id = resolved_ids[0]
                                print(f"Found base class by template dependency resolution: {name} -> {base_name}")
                
                # Method 5: Try to find by namespace + simple name
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
                
                # Method 6: Try fuzzy matching for template types
                if not base_xmi_id and '<' in base_name:
                    base_template, _ = CppTypeParser.parse_template_args(base_name)
                    simple_base = self.extract_simple_name(base_template)
                    
                    for candidate_name, candidate_info in self.created.items():
                        if candidate_info.original_data:
                            candidate_simple = self.extract_simple_name(str(candidate_info.name))
                            if candidate_simple == simple_base:
                                base_xmi_id = candidate_info.xmi
                                print(f"Found base class by fuzzy template matching: {name} -> {base_name} (matched: {candidate_name})")
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

        # associations: for each member try to match known types with improved template handling
        for name, info in self.created.items():
            owner_xmi: XmiId = info.xmi
            raws: List[UmlMember] = info.members
            for m in raws:
                type_repr: Optional[str] = m.type_repr
                if not type_repr:
                    continue
                
                # Enhanced type parsing for templates
                parsed: List[str] = CppTypeParser.extract_all_type_identifiers(type_repr)
                matched: List[str] = CppTypeParser.match_known_types_from_parsed(parsed, [str(k) for k in self.name_to_xmi.keys()])
                
                # If no direct matches found, try template resolution
                if not matched and '<' in type_repr:
                    candidates = [(name, info) for name, info in self.created.items()]
                    resolved_ids = self.resolve_template_dependencies(type_repr, candidates)
                    if resolved_ids:
                        # Create associations for resolved template dependencies
                        for resolved_id in resolved_ids:
                            # Validate that resolved_id is a valid XMI ID
                            if resolved_id and resolved_id in [info.xmi for info in self.created.values()]:
                                association: UmlAssociation = UmlAssociation(
                                    src=owner_xmi,
                                    tgt=resolved_id,
                                    aggregation=AggregationType.NONE,
                                    multiplicity="1",
                                    name=f"{m.name}_template_dep"
                                )
                                self.associations.append(association)
                                print(f"Added template dependency association: {name}.{m.name} -> {resolved_id}")
                            else:
                                print(f"Warning: Skipping invalid template dependency ID: {resolved_id}")
                
                an: Dict[str, Any] = CppTypeParser.analyze_type_expr(type_repr)
                outer_base: str = an.get("template_base") or ""
                is_container: bool = any(k in outer_base for k in CppTypeParser._CONTAINER_KEYWORDS) or outer_base in CppTypeParser._CONTAINER_KEYWORDS
                is_smart: bool = any(k in outer_base for k in CppTypeParser._SMART_PTRS) or outer_base in CppTypeParser._SMART_PTRS
                
                for mt in matched:
                    tgt_xmi: Optional[XmiId] = self.name_to_xmi.get(ElementName(mt))
                    if not tgt_xmi:
                        continue
                    
                    # Validate that both source and target XMI IDs exist in created elements
                    if owner_xmi not in [info.xmi for info in self.created.values()]:
                        print(f"Warning: Skipping association with invalid source ID: {owner_xmi}")
                        continue
                    if tgt_xmi not in [info.xmi for info in self.created.values()]:
                        print(f"Warning: Skipping association with invalid target ID: {tgt_xmi}")
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

        # dependencies: types used but unknown with improved template handling
        for name, info in self.created.items():
            used: frozenset[TypeName] = info.used_types or frozenset()
            for typename in used:
                if not typename:
                    continue
                # skip if known as element
                # match via parsed tokens
                if ElementName(str(typename)) in self.name_to_xmi:
                    continue
                
                # Enhanced template type resolution
                if '<' in str(typename):
                    candidates = [(name, info) for name, info in self.created.items()]
                    resolved_ids = self.resolve_template_dependencies(str(typename), candidates)
                    if resolved_ids:
                        # If we can resolve template dependencies, we don't need to add this as a dependency
                        print(f"Resolved template dependencies for {typename}: {resolved_ids}")
                        continue
                
                parsed: List[str] = CppTypeParser.extract_all_type_identifiers(str(typename))
                cand: List[str] = CppTypeParser.match_known_types_from_parsed(parsed, [str(k) for k in self.name_to_xmi.keys()])
                if cand:
                    # already accounted as association maybe; otherwise add dependency to first match
                    continue
                
                # Try to extract base template name for better dependency tracking
                if '<' in str(typename):
                    base_template, _ = CppTypeParser.parse_template_args(str(typename))
                    # Add dependency on base template if it's not already known
                    if base_template and ElementName(base_template) not in self.name_to_xmi:
                        self.dependencies.append((info.name, TypeName(base_template)))
                        print(f"Added dependency for template base: {name} -> {base_template}")
                
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

