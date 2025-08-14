#!/usr/bin/env python3
"""
XMI Generator for UML2Papyrus project.
Generates XMI files from UML model data.
"""

import logging
from typing import Dict, Any, List, Set, Optional, Union
from lxml import etree
from adapters.clang_uml.parser import CppTypeParser
from core.uml_model import (
    UmlModel, UmlElement, UmlAssociation, ElementKind,
    ClangMetadata, XmiId, ElementName, UmlOperation
)
from gen.xmi.writer import XmiWriter
from utils.ids import stable_id
from utils.xml import xml_text
from meta import DEFAULT_META as NEW_DEFAULT_META

from uml_types import TypedDict

logger = logging.getLogger(__name__)


class NamespaceTree(TypedDict):
    __annotations__: Dict[str, Union[UmlElement, Dict[str, Any]]]


class XmiElementVisitor:
    def visit_class(self, info: UmlElement) -> None:
        raise NotImplementedError

    def visit_enum(self, info: UmlElement) -> None:
        raise NotImplementedError

    def visit_datatype(self, info: UmlElement) -> None:
        raise NotImplementedError


class UmlXmiWritingVisitor(XmiElementVisitor):
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[ElementName, XmiId], model: UmlModel, property_enrichments: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        self.writer = writer
        self.name_to_xmi = name_to_xmi
        self.model = model
        self.elements_by_id = model.elements
        self._elements_by_id_str = {str(xid): el for xid, el in self.elements_by_id.items()}
        self.property_enrichments: Dict[str, Dict[str, str]] = property_enrichments or {}

    def _normalize_type_name(self, t: Optional[str]) -> str:
        if not t:
            return "void"
        try:
            analysis = CppTypeParser.analyze_type_expr(t)
            base = analysis.get("base") or t
            base = base.strip()
            return base
        except Exception:
            return t

    def _mangle_operation_signature(self, class_id: XmiId, op: 'UmlOperation') -> str:
        try:
            param_types = [self._normalize_type_name(pt) for _, pt in (op.parameters or [])]
            ret_type = self._normalize_type_name(op.return_type)
            const_suffix = " const" if getattr(op, 'is_const', False) else ""
            virt_suffix = " virtual" if getattr(op, 'is_virtual', False) else ""
            sig = f"{op.name}({', '.join(param_types)}) -> {ret_type}{const_suffix}{virt_suffix}"
            return sig
        except Exception:
            return f"{op.name}()"

    def _parse_template_instantiation(self, qualified_name: str) -> Optional[tuple[str, list[str]]]:
        if '<' not in qualified_name or '>' not in qualified_name:
            return None
        base = qualified_name.split('<', 1)[0]
        args_str = qualified_name[qualified_name.find('<') + 1: qualified_name.rfind('>')]
        # split by top-level commas
        args: list[str] = []
        buf: list[str] = []
        depth = 0
        for ch in args_str:
            if ch == '<':
                depth += 1
                buf.append(ch)
            elif ch == '>':
                depth -= 1
                buf.append(ch)
            elif ch == ',' and depth == 0:
                arg = ''.join(buf).strip()
                if arg:
                    args.append(arg)
                buf = []
            else:
                buf.append(ch)
        last = ''.join(buf).strip()
        if last:
            args.append(last)
        return base, args

    def visit_class(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)

        extra_attrs: Optional[Dict[str, str]] = None
        if hasattr(info, 'templates') and info.templates:
            extra_attrs = {"isTemplate": "true"}

        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)

        uml_model = NEW_DEFAULT_META.uml
        self.writer.start_packaged_element(xmi, uml_model.class_type, short_name, is_abstract=is_abstract, extra_attrs=extra_attrs)

        # DISABLED: Template signatures for EMF compatibility
        # EMF validator requires each template signature to have at least 1 parameter
        # Many C++ templates have complex/external parameters that can't be properly modeled
        # For now, disable template signatures to ensure valid EMF XMI output
        if False:  # Completely disable template signature generation
            pass

        generalizations = getattr(self.model, "generalizations", []) or []
        for gen in generalizations:
            if gen.child_id == xmi:
                parent_exists = gen.parent_id in self.model.elements
                if not parent_exists:
                    logger.warning(f"Skip generalization for '{name}': parent id {gen.parent_id} not found")
                    continue
                self.writer.write_generalization(
                    stable_id(str(gen.child_id) + ":gen"), 
                    gen.parent_id,
                    inheritance_type=gen.inheritance_type.value if gen.inheritance_type else "public",
                    is_virtual=gen.is_virtual,
                    is_final=gen.is_final
                )

        for m in info.members:
            aid: str = stable_id(xmi + ":attr:" + m.name)
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(m.type_repr)) if m.type_repr else None
            enr = self.property_enrichments.get(aid, {})
            assoc_ref = enr.get('association')
            opp_ref = enr.get('opposite')
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value,
                type_ref=tref, is_static=m.is_static,
                association_ref=XmiId(assoc_ref) if assoc_ref else None,
                opposite_ref=XmiId(opp_ref) if opp_ref else None,
            )

        # Emit operations with mangled names to make them distinguishable and ids stable
        seen_param_names: set[str] = set()
        for idx, op in enumerate(info.operations):
            mangled = self._mangle_operation_signature(xmi, op)
            # Add index to ensure unique ID even for operations with identical signatures  
            op_id: str = stable_id(xmi + ":op:" + str(idx) + ":" + mangled)
            # Ensure distinguishable names even when parameter types are missing
            display_name = f"{mangled}#{op_id[-6:]}"
            return_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(op.return_type)) if op.return_type else None
            self.writer.start_owned_operation(op_id, display_name, visibility=op.visibility.value, is_static=op.is_static)
            if return_type_ref:
                self.writer.write_operation_return_type(op_id, return_type_ref)
            seen_param_names.clear()
            for i, (param_name, param_type) in enumerate(op.parameters):
                if not isinstance(param_name, str) or not isinstance(param_type, str):
                    logging.warning(f"Skipping invalid parameter data: name={param_name}, type={param_type}")
                    continue
                if not param_name or param_name.startswith("id_"):
                    param_name = f"p{i}"
                # ensure unique within operation namespace
                base_name = param_name
                n = 1
                while param_name in seen_param_names:
                    param_name = f"{base_name}_{n}"
                    n += 1
                seen_param_names.add(param_name)
                param_id: str = stable_id(op_id + ":param:" + str(i) + ":" + param_name)
                param_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(param_type)) if param_type else None
                self.writer.write_owned_parameter(param_id, param_name, "in", param_type_ref)
            self.writer.end_owned_operation()

        # Emit template binding if this is an instantiation (by metadata or by name heuristic)
        inst_of = getattr(info, 'instantiation_of', None)
        inst_args = getattr(info, 'instantiation_args', []) or []
        if not inst_of and '<' in str(info.name) and '>' in str(info.name):
            parsed = self._parse_template_instantiation(str(info.name))
            if parsed:
                base_name, arg_names = parsed
                base_id = self.name_to_xmi.get(ElementName(base_name))
                if base_id:
                    inst_of = base_id
                    inst_args = [self.name_to_xmi.get(ElementName(a)) for a in arg_names]
        # Skip template binding generation for EMF compatibility 
        # Template bindings with invalid signature references cause EMF validation errors
        if False:  # Disabled for EMF compatibility
            pass

        self.writer.end_packaged_element()

    def visit_enum(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        uml_model = NEW_DEFAULT_META.uml
        self.writer.start_packaged_element(xmi, uml_model.enum_type, short_name, is_abstract=is_abstract)
        if hasattr(info, 'literals') and info.literals:
            for lit in info.literals:
                lit_id: str = stable_id(xmi + ":literal:" + lit)
                self.writer.write_enum_literal(lit_id, lit)
        self.writer.end_packaged_element()

    def visit_datatype(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)
        short_name = str(name).split('::')[-1] if '::' in str(name) else str(name)
        uml_model = NEW_DEFAULT_META.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, short_name, is_abstract=is_abstract)
        # DataTypes may own attributes as well
        for m in getattr(info, 'members', []) or []:
            aid: str = stable_id(xmi + ":attr:" + m.name)
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(m.type_repr)) if m.type_repr else None
            enr = self.property_enrichments.get(aid, {})
            assoc_ref = enr.get('association')
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value,
                type_ref=tref, is_static=m.is_static,
                association_ref=XmiId(assoc_ref) if assoc_ref else None,
                opposite_ref=None,
            )
        if info.underlying:
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(info.underlying))
            if tref:
                self.writer.write_generalization(stable_id(xmi + ":gen"), tref)
        # Template binding emission for datatypes disabled
        self.writer.end_packaged_element()


class XmiGenerator:
    def __init__(self, model: UmlModel, graph: Optional[Any] = None) -> None:
        self.model = model
        self.name_to_xmi: Dict[ElementName, XmiId] = model.name_to_xmi
        self.graph = graph
        self.elements_by_id: Dict[XmiId, UmlElement] = model.elements
        self._elements_by_id_str = {str(xid): el for xid, el in self.elements_by_id.items()}

        self.created: Dict[ElementName, UmlElement] = {
            name: model.elements[xmi]
            for name, xmi in self.name_to_xmi.items()
            if xmi in model.elements
        }
        self.xmi_to_name: Dict[XmiId, ElementName] = {xmi: name for name, xmi in self.name_to_xmi.items()}

        if self.graph and hasattr(self.graph, "namespaces") and hasattr(self.graph, "elements_by_id"):
            self.namespace_tree = self._build_tree_from_namespace_node(self.graph.namespaces, self.graph.elements_by_id)
        else:
            self.namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)

        self.all_referenced_type_names: Set[str] = self._collect_referenced_types()
        self._create_stub_elements()
        self._resolve_association_targets()
        self._cleanup_invalid_associations()
        self._ensure_association_types_materialized()
        if self.graph and hasattr(self.graph, "namespaces") and hasattr(self.graph, "elements_by_id"):
            for name, elem in self.created.items():
                if elem.xmi not in self.graph.elements_by_id:
                    self.graph.elements_by_id[elem.xmi] = elem
            self.namespace_tree = self._build_tree_from_namespace_node(self.graph.namespaces, self.graph.elements_by_id)
        else:
            self.namespace_tree = self._build_namespace_tree(self.created)
        self._validate_model()

    def _ensure_association_types_materialized(self) -> None:
        # Ensure every association endpoint id exists as a created element
        present_ids = {elem.xmi for elem in self.created.values()}
        for assoc in list(self.model.associations):
            for end_id in (assoc.src, assoc.tgt):
                if end_id not in present_ids:
                    # Try to find a name for this id
                    end_name = self.xmi_to_name.get(end_id) if hasattr(self, 'xmi_to_name') else None
                    if not end_name:
                        end_name = ElementName(f"Type_{str(end_id)[-8:]}")
                    # Create a minimal DataType stub and add it to created and model.elements
                    stub_element: UmlElement = UmlElement(
                        xmi=end_id,
                        name=end_name,
                        kind=ElementKind.DATATYPE,
                        members=[],
                        clang=ClangMetadata(),
                        used_types=frozenset(),
                        underlying=None,
                        is_stub=True,
                        original_data={"materialized_stub": True},
                    )
                    self.created[end_name] = stub_element
                    self.model.elements[end_id] = stub_element
                    if end_name not in self.name_to_xmi:
                        self.name_to_xmi[end_name] = end_id
                    present_ids.add(end_id)
                    logger.warning(f"Materialized association endpoint as DataType: id='{end_id}', name='{end_name}'")

    def _build_tree_from_namespace_node(self, node: Any, elements_by_id: Dict[XmiId, UmlElement]) -> NamespaceTree:
        def rec(ns_node: Any) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            children = getattr(ns_node, 'children', {}) or {}
            for name, child in children.items():
                out[name] = {'__namespace__': True, '__children__': rec(child)}
                xmi_id = getattr(child, 'xmi_id', None)
                if xmi_id:
                    out[name]['__xmi_id__'] = xmi_id
            elem_ids = getattr(ns_node, 'elements', []) or []
            for eid in elem_ids:
                elem = elements_by_id.get(eid)
                if elem is not None:
                    key = str(getattr(elem, 'name', eid))
                    out[key] = elem
            return out

        return rec(node)

    def _build_namespace_tree(self, elements: Dict[ElementName, UmlElement]) -> NamespaceTree:
        tree: NamespaceTree = {}
        logger.info(f"Building namespace tree for {len(elements)} elements")
        if hasattr(self.model, 'namespace_packages') and self.model.namespace_packages:
            for namespace_name, namespace_xmi in self.model.namespace_packages.items():
                tree[namespace_name] = {'__namespace__': True, '__children__': {}, '__xmi_id__': namespace_xmi}
        for q_name, info in elements.items():
            name_str = str(q_name)
            if '::' not in name_str:
                tree[name_str] = info
            else:
                parts = name_str.split('::')
                if len(parts) == 1:
                    tree[name_str] = info
                else:
                    current: Dict[str, Any] = tree
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {'__namespace__': True, '__children__': {}}
                        elif not isinstance(current[part], dict) or '__namespace__' not in current[part]:
                            existing_element: UmlElement = current[part]  # type: ignore
                            current[part] = {'__namespace__': True, '__children__': {}}
                            current[part]['__children__']['__root__'] = existing_element  # type: ignore
                        current = current[part]['__children__']  # type: ignore
                    current[parts[-1]] = info
        return tree

    def _collect_referenced_types(self) -> Set[str]:
        def normalize(t: Optional[str]) -> Optional[str]:
            if not t:
                return None
            analysis = CppTypeParser.analyze_type_expr(t)
            base: str = analysis.get("base") or t
            base = base.strip()
            return base or None

        all_referenced_type_names: Set[str] = set()
        for _, info in self.created.items():
            for m in info.members:
                n = normalize(m.type_repr)
                if n:
                    all_referenced_type_names.add(n)
            if hasattr(info, 'operations'):
                for op in info.operations:
                    if op.return_type:
                        n = normalize(op.return_type)
                        if n:
                            all_referenced_type_names.add(n)
                    for _, param_type in op.parameters:
                        n = normalize(param_type)
                        if n:
                            all_referenced_type_names.add(n)
            if hasattr(info, 'templates'):
                for t in info.templates:
                    n = normalize(t)
                    if n:
                        all_referenced_type_names.add(n)
        return all_referenced_type_names

    def _final_materialize_any_missing_idrefs(self, out_path: str, writer: XmiWriter) -> None:
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(out_path, parser)
            root = tree.getroot()
            xmi_ns = NEW_DEFAULT_META.xml.xmi_ns
            ns = {"xmi": xmi_ns, "uml": NEW_DEFAULT_META.xml.uml_ns}
            ids_present: set[str] = set(el.get(NEW_DEFAULT_META.xml.xmi_id) for el in root.xpath('//*[@xmi:id]', namespaces=ns))
            referenced: set[str] = set()
            # Collect common reference attributes
            ref_attrs = ["type", "general", "client", "supplier", "association", "opposite"]
            for attr in ref_attrs:
                for el in root.xpath(f'//*[@{attr}]', namespaces=ns):
                    val = el.get(attr)
                    if val:
                        referenced.add(val)
            # xmi:idref occurrences (memberEnd, signature, etc.)
            for el in root.xpath('//*[@xmi:idref]', namespaces=ns):
                val = el.get(f'{{{xmi_ns}}}idref')
                if val:
                    referenced.add(val)
            missing = [mid for mid in referenced if mid and mid not in ids_present]
        except Exception:
            missing = []
        if not missing:
            return
        # Emit missing as DataType stubs under a dedicated package
        ext_pkg_id = stable_id("package:ExternalTypes")
        writer.start_package(ext_pkg_id, "ExternalTypes")
        for mid in sorted(set(missing)):
            try:
                name = self.xmi_to_name.get(XmiId(mid)) if hasattr(self, 'xmi_to_name') else None
            except Exception:
                name = None
            nm_s = str(name) if name else f"Type_{mid[-8:]}"
            writer.start_packaged_element(XmiId(mid), NEW_DEFAULT_META.uml.datatype_type, nm_s)
            writer.end_packaged_element()
        writer.end_package()

    def _create_stub_elements(self) -> None:
        from app.config import DEFAULT_CONFIG
        emit_stubs = True
        try:
            emit_stubs = DEFAULT_CONFIG.emit_referenced_type_stubs
        except Exception:
            emit_stubs = True
        logger.info(f"Creating stub elements for {len(self.all_referenced_type_names)} referenced types")
        for type_name in self.all_referenced_type_names:
            if type_name in self.created or ElementName(type_name) in self.name_to_xmi:
                continue
            if type_name in ['int', 'char', 'bool', 'float', 'double', 'void', 'string', 'std::string']:
                continue
            # Generate a stable stub id strictly from the type name
            if emit_stubs:
                stub_id: XmiId = XmiId(stable_id(f"type:{type_name}"))
                self.name_to_xmi[ElementName(type_name)] = stub_id
                stub_element: UmlElement = UmlElement(
                    xmi=stub_id,
                    name=ElementName(type_name),
                    kind=ElementKind.DATATYPE,
                    members=[],
                    clang=ClangMetadata(),
                    used_types=frozenset(),
                    underlying=None
                )
                self.created[ElementName(type_name)] = stub_element
                # Ensure the stub is also visible via elements_by_id/model.elements
                try:
                    self.elements_by_id[stub_id] = stub_element
                    self.model.elements[stub_id] = stub_element
                    self._elements_by_id_str[str(stub_id)] = stub_element
                except Exception:
                    pass

        # Also materialize template instantiations referenced in member types
        def ensure_instantiation_from_expr(expr: Dict[str, Any]) -> Optional[XmiId]:
            kind = expr.get("kind")
            if kind == "name":
                nm = expr.get("name")
                return self.name_to_xmi.get(ElementName(nm)) if nm else None
            if kind == "template":
                base = expr.get("base") or ""
                args = expr.get("args") or []
                arg_ids: List[XmiId] = []
                arg_names: List[str] = []
                for a in args:
                    # resolve recursively
                    aid = ensure_instantiation_from_expr(a)
                    if aid:
                        arg_ids.append(aid)
                        base_el = self._elements_by_id_str.get(str(aid))
                        if base_el is not None:
                            arg_names.append(str(base_el.name).split("::")[-1])
                canonical = base + ("<" + ", ".join(arg_names) + ">" if arg_names else "")
                inst_name = ElementName(canonical)
                inst_xmi: Optional[XmiId] = self.name_to_xmi.get(inst_name)
                if not inst_xmi:
                    inst_id: XmiId = XmiId(stable_id(f"inst:{canonical}"))
                    of_id: Optional[XmiId] = self.name_to_xmi.get(ElementName(base))
                    if not of_id:
                        return None
                    inst_elem: UmlElement = UmlElement(
                        xmi=inst_id,
                        name=inst_name,
                        kind=ElementKind.CLASS,
                        members=[],
                        clang=ClangMetadata(),
                        used_types=frozenset(),
                        underlying=None,
                    )
                    inst_elem.instantiation_of = of_id
                    inst_elem.instantiation_args = list(arg_ids)
                    self.created[inst_name] = inst_elem
                    self.name_to_xmi[inst_name] = inst_id
                    self.elements_by_id[inst_id] = inst_elem
                    self._elements_by_id_str[str(inst_id)] = inst_elem
                    inst_xmi = inst_id
                return inst_xmi
            return None

        for _, info in list(self.created.items()):
            for m in getattr(info, 'members', []) or []:
                if not m.type_repr:
                    continue
                try:
                    expr = CppTypeParser.parse_type_expr(m.type_repr)
                    ensure_instantiation_from_expr(expr)
                except Exception:
                    continue

    def _resolve_association_targets(self) -> None:
        for assoc in self.model.associations:
            if assoc.tgt not in [info.xmi for info in self.created.values()]:
                target_found = False
                for _, info in self.created.items():
                    if info.xmi == assoc.tgt:
                        target_found = True
                        break
                if not target_found:
                    for name, xmi_id in self.name_to_xmi.items():
                        if xmi_id == assoc.tgt and name in self.created:
                            target_found = True
                            break
                if not target_found:
                    logger.warning(f"Association '{assoc.name}' has unresolved target: {assoc.tgt}")

    def _cleanup_invalid_associations(self) -> None:
        valid_associations: List[UmlAssociation] = []
        valid_xmi_ids = {element.xmi for element in self.created.values()}
        seen_associations: set[tuple[str, str]] = set()  # Track end pairs to prevent duplicates
        
        for assoc in self.model.associations:
            # Skip invalid associations
            if assoc.src not in valid_xmi_ids or assoc.tgt not in valid_xmi_ids:
                continue
                
            # Skip problematic associations
            # 1. Self-referential associations where both ends are the same property
            if (assoc.src == assoc.tgt and 
                assoc._end1_id and assoc._end2_id and 
                assoc._end1_id == assoc._end2_id):
                logger.debug(f"Skipping self-referential association: {assoc.name}")
                continue
            # 2. Skip associations where either end ID is None/empty (would create invalid memberEnd)
            if not assoc._end1_id or not assoc._end2_id:
                logger.debug(f"Skipping association with missing end IDs: {assoc.name} (end1={assoc._end1_id}, end2={assoc._end2_id})")
                continue
                
            # Skip duplicate associations between same endpoints
            end1 = str(assoc._end1_id) if assoc._end1_id else str(assoc.src)
            end2 = str(assoc._end2_id) if assoc._end2_id else str(assoc.tgt)
            end_pair = tuple(sorted([end1, end2]))  # Sort to catch both directions
            
            if end_pair in seen_associations:
                logger.debug(f"Skipping duplicate association: {assoc.name}")
                continue  # Skip duplicate
                
            seen_associations.add(end_pair)
            valid_associations.append(assoc)
            
        self.model.associations = valid_associations

    def _validate_model(self) -> None:
        validation_errors: List[str] = []
        for name, element in self.created.items():
            if not element.name:
                validation_errors.append(f"Element {name} has no name")
            if not element.xmi:
                validation_errors.append(f"Element {name} has no XMI ID")
            for member in element.members:
                if member.type_repr:
                    if member.type_repr in ['int', 'char', 'bool', 'float', 'double', 'void', 'string', 'std::string', 'long', 'short', 'unsigned', 'signed']:
                        continue
                    if ElementName(member.type_repr) not in self.name_to_xmi:
                        validation_errors.append(f"Member {member.name} in {name} references undefined type: {member.type_repr}")
        valid_xmi_ids = {element.xmi for element in self.created.values()}
        for assoc in self.model.associations:
            if assoc.src not in valid_xmi_ids or assoc.tgt not in valid_xmi_ids:
                validation_errors.append(f"Association '{assoc.name}' references undefined elements")
        if validation_errors:
            for error in validation_errors:
                logger.warning(error)

    def get_model_statistics(self) -> Dict[str, Any]:
        return {
            'total_elements': len(self.created),
            'classes': len([e for e in self.created.values() if e.kind == ElementKind.CLASS]),
            'enums': len([e for e in self.created.values() if e.kind == ElementKind.ENUM]),
            'datatypes': len([e for e in self.created.values() if e.kind == ElementKind.DATATYPE]),
            'templates': len([e for e in self.created.values() if hasattr(e, 'templates') and e.templates]),
            'associations': len(self.model.associations),
            'dependencies': len(self.model.dependencies),
            'generalizations': len(getattr(self.model, 'generalizations', []) or []),
            'stub_elements': sum(1 for e in self.created.values() if getattr(e, 'is_stub', False))
        }

    def _write_package_contents(self, visitor: UmlXmiWritingVisitor, tree: NamespaceTree, parent_name: str = "") -> None:
        for name, item in tree.items():
            if isinstance(item, dict) and item.get('__namespace__'):
                package_name: str = f"{parent_name}::{name}" if parent_name else name
                if '__xmi_id__' in item:
                    package_id: str = str(item['__xmi_id__'])
                else:
                    package_id: str = stable_id(f"package:{package_name}")
                visitor.writer.start_package(package_id, name)
                children: Dict[str, Any] = item.get('__children__', {})  # type: ignore
                self._write_package_contents(visitor, children, package_name)
                visitor.writer.end_package()
            else:
                if hasattr(item, 'kind'):
                    if item.kind == ElementKind.CLASS:
                        visitor.visit_class(item)
                    elif item.kind == ElementKind.ENUM:
                        visitor.visit_enum(item)
                    elif item.kind == ElementKind.DATATYPE:
                        visitor.visit_datatype(item)
                    else:
                        visitor.visit_class(item)

    def write(self, out_path: str, project_name: str, pretty: bool = False) -> None:
        namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer: XmiWriter = XmiWriter(xf, xml_model=NEW_DEFAULT_META.xml)
            writer.start_doc(project_name, model_id="model_1")
            # Map только по имени свойства (строго)
            member_prop_by_owner_and_name: Dict[tuple[XmiId, str], str] = {}
            # Обратное отображение: (owner_id, prop_id) -> member_name
            owner_prop_to_member_name: Dict[tuple[XmiId, str], str] = {}
            # Обогащение свойств: property_id -> { 'association': assoc_id, 'opposite': other_prop_id }
            property_enrichments: Dict[str, Dict[str, str]] = {}
            # Набор всех реально существующих property id, вычисленных по членам классов
            existing_property_ids: set[str] = set()
            for elem in self.model.elements.values():
                if hasattr(elem, 'members') and elem.members:
                    for m in elem.members:
                        pid: str = stable_id(elem.xmi + ":attr:" + m.name)
                        member_prop_by_owner_and_name[(elem.xmi, m.name)] = pid
                        owner_prop_to_member_name[(elem.xmi, pid)] = m.name
                        existing_property_ids.add(pid)

            # Pre-set association ids and resolve end property ids from existing class members
            for assoc in self.model.associations:
                if not assoc._assoc_id:
                    assoc._assoc_id = stable_id(f"assoc:{assoc.src}:{assoc.tgt}:{assoc.name}")
                # Только по имени свойства
                if not assoc._end1_id:
                    pid_by_name = member_prop_by_owner_and_name.get((assoc.src, assoc.name))
                    assoc._end1_id = pid_by_name
                if not assoc._end2_id:
                    pid_by_name = member_prop_by_owner_and_name.get((assoc.tgt, assoc.name))
                    assoc._end2_id = pid_by_name
                # Если вычисленный id свойства отсутствует среди реально существующих, не используем его
                if assoc._end1_id and str(assoc._end1_id) not in existing_property_ids:
                    assoc._end1_id = None
                if assoc._end2_id and str(assoc._end2_id) not in existing_property_ids:
                    assoc._end2_id = None
                # Имя ассоциации: <SrcFQN>::<src_prop>-><TgtFQN>::<tgt_prop>
                try:
                    src_fqn = str(self.xmi_to_name.get(assoc.src) or assoc.src)
                    tgt_fqn = str(self.xmi_to_name.get(assoc.tgt) or assoc.tgt)
                    src_prop = owner_prop_to_member_name.get((assoc.src, assoc._end1_id or "")) or ""
                    tgt_prop = owner_prop_to_member_name.get((assoc.tgt, assoc._end2_id or "")) or ""
                    left = f"{src_fqn}::{src_prop}" if src_prop else src_fqn
                    right = f"{tgt_fqn}::{tgt_prop}" if tgt_prop else tgt_fqn
                    assoc.name = f"{left}->{right}"
                except Exception:
                    pass
                # Обогащения свойств: association only (skip opposite for EMF compatibility)
                try:
                    if assoc._end1_id:
                        d = property_enrichments.setdefault(str(assoc._end1_id), {})
                        d.setdefault('association', str(assoc._assoc_id))
                        # Skip opposite references for EMF compatibility
                    if assoc._end2_id:
                        d2 = property_enrichments.setdefault(str(assoc._end2_id), {})
                        d2.setdefault('association', str(assoc._assoc_id))
                        # Skip opposite references for EMF compatibility  
                except Exception:
                    pass
                # Не мутируем имя ассоциации; оставляем как есть из модели

            # No synthetic association-end properties; rely on existing properties only
            # Передаём обогащения свойств для записи association/opposite у ownedAttribute
            visitor: UmlXmiWritingVisitor = UmlXmiWritingVisitor(writer, self.name_to_xmi, self.model, property_enrichments=property_enrichments)
            # Write all elements once according to namespace tree
            self._write_package_contents(visitor, namespace_tree)
            # Ask writer which property ids were emitted to validate class-owned association ends
            try:
                emitted_props = visitor.writer.get_emitted_property_ids()  # type: ignore[attr-defined]
            except Exception:
                emitted_props = set()
            # Optional: materialize referenced type ids (disabled if policy forbids)
            from app.config import DEFAULT_CONFIG
            do_emit_types = True
            try:
                do_emit_types = DEFAULT_CONFIG.emit_referenced_type_stubs
            except Exception:
                do_emit_types = True
            if do_emit_types:
                try:
                    parser_pk = etree.XMLParser(remove_blank_text=True)
                    tree_pk = etree.parse(out_path, parser_pk)
                    root_pk = tree_pk.getroot()
                    ns_pk = {"xmi": NEW_DEFAULT_META.xml.xmi_ns, "uml": NEW_DEFAULT_META.xml.uml_ns}
                    present_ids = set(el.get(NEW_DEFAULT_META.xml.xmi_id) for el in root_pk.xpath('//*[@xmi:id]', namespaces=ns_pk))
                except Exception:
                    present_ids = set()
                try:
                    referenced_type_ids = visitor.writer.get_referenced_type_ids()  # type: ignore[attr-defined]
                except Exception:
                    referenced_type_ids = set()
                missing_type_ids = [tid for tid in referenced_type_ids if tid and tid not in present_ids]
                if missing_type_ids:
                    ext_pkg_id = stable_id("package:ExternalTypes")
                    writer.start_package(ext_pkg_id, "ExternalTypes")
                    for mid in missing_type_ids:
                        nm = self.xmi_to_name.get(XmiId(mid)) if hasattr(self, 'xmi_to_name') else None
                        nm_s = str(nm) if nm else f"Type_{mid[-8:]}"
                        writer.start_packaged_element(XmiId(mid), NEW_DEFAULT_META.uml.datatype_type, nm_s)
                        writer.end_packaged_element()
                    writer.end_package()
            for assoc in self.model.associations:
                # Association id and end property ids already precomputed; just write association
                logger.debug(f"Writing association: name='{assoc.name}', src='{assoc.src}', tgt='{assoc.tgt}'")
                # If a claimed class-owned property id was not actually emitted, drop it to force ownedEnd
                if assoc._end1_id and str(assoc._end1_id) not in emitted_props:
                    assoc._end1_id = None
                if assoc._end2_id and str(assoc._end2_id) not in emitted_props:
                    assoc._end2_id = None
                writer.write_association(assoc, uml_model=NEW_DEFAULT_META.uml)
                # Try to set opposites between class properties if both memberEnd properties exist and belong to different owners
                try:
                    if assoc._end1_id and assoc._end2_id:
                        src_owner = self.model.elements.get(assoc.src)
                        tgt_owner = self.model.elements.get(assoc.tgt)
                        if src_owner and tgt_owner:
                            # Emit opposite via ownedAttribute update (best-effort)
                            # Note: writer API writes attributes immediately; we cannot mutate already written ones here.
                            # Future: move association write earlier or collect attributes to set opposite before flushing.
                            pass
                except Exception:
                    pass
            for owner_q_name, typ in self.model.dependencies:
                client_info: Optional[UmlElement] = self.created.get(ElementName(owner_q_name))
                if not client_info:
                    continue
                client_id: XmiId = client_info.xmi
                supplier_id: Optional[XmiId] = self.name_to_xmi.get(ElementName(typ))
                if client_id and supplier_id:
                    dep_id: str = stable_id(f"dep:{owner_q_name}:{typ}")
                    xml_model = NEW_DEFAULT_META.xml
                    attribs: Dict[str, str] = {
                        xml_model.xmi_type: "uml:Dependency", 
                        xml_model.xmi_id: dep_id,
                        "name": f"dep_{xml_text(owner_q_name)}_to_{xml_text(typ)}",
                        "client": client_id, 
                        "supplier": supplier_id
                    }
                    dep_el: etree._Element = etree.Element("packagedElement", attrib=attribs, nsmap=xml_model.uml_nsmap)
                    xf.write(dep_el)
            # Final post-pass (optional): ensure any id in @type exists
            do_emit_types_final = True
            try:
                do_emit_types_final = DEFAULT_CONFIG.emit_referenced_type_stubs
            except Exception:
                do_emit_types_final = True
            if do_emit_types_final:
                try:
                    parser3 = etree.XMLParser(remove_blank_text=True)
                    tree3 = etree.parse(out_path, parser3)
                    root3 = tree3.getroot()
                    ns3 = {"xmi": NEW_DEFAULT_META.xml.xmi_ns, "uml": NEW_DEFAULT_META.xml.uml_ns}
                    ids_in_doc3 = set(el.get(NEW_DEFAULT_META.xml.xmi_id) for el in root3.xpath('//*[@xmi:id]', namespaces=ns3))
                    type_targets3 = set(el.get('type') for el in root3.xpath('//*[@type]', namespaces=ns3))
                    missing_final = [t for t in type_targets3 if t and t not in ids_in_doc3]
                except Exception:
                    missing_final = []
                if missing_final:
                    ext_pkg_id4 = stable_id("package:ExternalTypes")
                    writer.start_package(ext_pkg_id4, "ExternalTypes")
                    for mid in missing_final:
                        nm = self.xmi_to_name.get(XmiId(mid)) if hasattr(self, 'xmi_to_name') else None
                        nm_s = str(nm) if nm else f"Type_{mid[-8:]}"
                        writer.start_packaged_element(XmiId(mid), NEW_DEFAULT_META.uml.datatype_type, nm_s)
                        writer.end_packaged_element()
                    writer.end_package()
            # Final catch-all: any id referenced anywhere but not declared gets materialized as DataType
            from app.config import DEFAULT_CONFIG
            do_final_emit = True
            try:
                do_final_emit = DEFAULT_CONFIG.emit_referenced_type_stubs
            except Exception:
                do_final_emit = True
            if do_final_emit:
                try:
                    # Prefer writer-collected idrefs for accuracy
                    emitted_ids = visitor.writer.get_emitted_ids()  # type: ignore[attr-defined]
                    idrefs = visitor.writer.get_referenced_idrefs()  # type: ignore[attr-defined]
                    missing_ids = [rid for rid in idrefs if rid not in emitted_ids]
                    if missing_ids:
                        ext_pkg_id = stable_id("package:ExternalTypes")
                        writer.start_package(ext_pkg_id, "ExternalTypes")
                        for mid in sorted(set(missing_ids)):
                            nm = self.xmi_to_name.get(XmiId(mid)) if hasattr(self, 'xmi_to_name') else None
                            nm_s = str(nm) if nm else f"Type_{mid[-8:]}"
                            writer.start_packaged_element(XmiId(mid), NEW_DEFAULT_META.uml.datatype_type, nm_s)
                            writer.end_packaged_element()
                        writer.end_package()
                except Exception:
                    # Fallback to XML parse method (only if stubs enabled)
                    if DEFAULT_CONFIG.emit_referenced_type_stubs:
                        self._final_materialize_any_missing_idrefs(out_path, writer)
            writer.end_doc()
        if pretty:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(out_path, parser)
            tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)

__all__ = ["XmiGenerator"]


