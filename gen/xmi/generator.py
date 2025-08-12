#!/usr/bin/env python3
"""
XMI Generator for UML2Papyrus project.
Generates XMI files from UML model data.
"""

import logging
from typing import Dict, Any, List, Set, Optional, Union
from lxml import etree
from core.uml_model import (
    UmlModel, UmlElement, UmlAssociation, ElementKind, 
    ClangMetadata, XmiId, ElementName
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
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[ElementName, XmiId], model: UmlModel) -> None:
        self.writer = writer
        self.name_to_xmi = name_to_xmi
        self.model = model
        try:
            self.elements_by_id = model.elements
        except Exception:
            self.elements_by_id = {}
        self._elements_by_id_str = {str(xid): el for xid, el in self.elements_by_id.items()}

    def visit_class(self, info: UmlElement) -> None:
        name: ElementName = info.name
        xmi: XmiId = info.xmi
        is_abstract: bool = bool(info.clang.is_abstract)

        extra_attrs: Optional[Dict[str, str]] = None
        if hasattr(info, 'templates') and info.templates:
            extra_attrs = {"isTemplate": "true"}

        short_name_full = str(name).split('::')[-1] if '::' in str(name) else str(name)
        if hasattr(info, 'templates') and info.templates and not getattr(info, 'instantiation_of', None):
            short_name = short_name_full.split('<')[0]
        else:
            short_name = short_name_full

        uml_model = NEW_DEFAULT_META.uml
        self.writer.start_packaged_element(xmi, uml_model.class_type, short_name, is_abstract=is_abstract, extra_attrs=extra_attrs)

        if hasattr(info, 'templates') and info.templates:
            signature_id: str = stable_id(xmi + ":templateSignature")
            self.writer.start_template_signature(signature_id)
            for i, template_param in enumerate(info.templates):
                template_id: str = stable_id(xmi + ":template:" + str(i))
                self.writer.write_template_parameter(template_id, template_param)
            self.writer.end_template_signature()

        inst_of = getattr(info, 'instantiation_of', None)
        inst_args = getattr(info, 'instantiation_args', []) or []
        if inst_of and isinstance(inst_args, list) and inst_args and all(arg is not None for arg in inst_args):
            # Write binding unconditionally when instantiation data is present.
            signature_ref: XmiId = XmiId(stable_id(str(inst_of) + ":templateSignature"))
            try:
                self.writer.write_template_binding(stable_id(xmi + ":binding"), signature_ref, inst_args)  # type: ignore[arg-type]
            except Exception as e:
                logger.warning(f"Skip templateBinding for '{name}': {e}")
        else:
            # Fallback: if element name looks like an instantiation (contains '<>'), try to bind by parsing name
            nstr = str(name)
            if '<' in nstr and '>' in nstr:
                try:
                    base_template, arg_names = CppTypeParser.parse_template_args(nstr)
                    base_id = self.name_to_xmi.get(ElementName(base_template))
                    if base_id:
                        sig_ref: XmiId = XmiId(stable_id(str(base_id) + ":templateSignature"))
                        arg_ids: List[XmiId] = []
                        for an in arg_names:
                            aid = self.name_to_xmi.get(ElementName(an))
                            if aid:
                                arg_ids.append(aid)
                        if arg_ids:
                            self.writer.write_template_binding(stable_id(xmi + ":binding"), sig_ref, arg_ids)
                except Exception:
                    pass

        generalizations = getattr(self.model, "generalizations", []) or []
        for gen in generalizations:
            if gen.child_id == xmi:
                try:
                    parent_exists = gen.parent_id in self.model.elements
                except Exception:
                    parent_exists = False
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
            self.writer.write_owned_attribute(
                aid, m.name, visibility=m.visibility.value, 
                type_ref=tref, is_static=m.is_static
            )

        for op in info.operations:
            op_id: str = stable_id(xmi + ":op:" + op.name)
            return_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(op.return_type)) if op.return_type else None
            self.writer.start_owned_operation(op_id, op.name, visibility=op.visibility.value, is_static=op.is_static)
            if return_type_ref:
                self.writer.write_operation_return_type(op_id, return_type_ref)
            for param_name, param_type in op.parameters:
                if not isinstance(param_name, str) or not isinstance(param_type, str):
                    logging.warning(f"Skipping invalid parameter data: name={param_name}, type={param_type}")
                    continue
                if param_name.startswith("id_"):
                    logging.warning(f"Parameter name appears to be an ID, using 'unnamed_param': {param_name}")
                    param_name = "unnamed_param"
                param_id: str = stable_id(op_id + ":param:" + param_name)
                param_type_ref: Optional[XmiId] = self.name_to_xmi.get(ElementName(param_type)) if param_type else None
                self.writer.write_owned_parameter(param_id, param_name, "in", param_type_ref)
            self.writer.end_owned_operation()

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
        if info.underlying:
            tref: Optional[XmiId] = self.name_to_xmi.get(ElementName(info.underlying))
            if tref:
                self.writer.write_generalization(stable_id(xmi + ":gen"), tref)
        self.writer.end_packaged_element()


class XmiGenerator:
    def __init__(self, model: UmlModel, graph: Optional[Any] = None) -> None:
        self.model = model
        self.name_to_xmi: Dict[ElementName, XmiId] = model.name_to_xmi
        self.graph = graph
        try:
            self.elements_by_id: Dict[XmiId, UmlElement] = model.elements
        except Exception:
            self.elements_by_id = {}
        self._elements_by_id_str = {str(xid): el for xid, el in self.elements_by_id.items()}

        self.created: Dict[ElementName, UmlElement] = {
            name: model.elements[xmi]
            for name, xmi in self.name_to_xmi.items()
            if xmi in model.elements
        }
        self.xmi_to_name: Dict[XmiId, ElementName] = {xmi: name for name, xmi in self.name_to_xmi.items()}

        if self.graph and hasattr(self.graph, "namespaces") and hasattr(self.graph, "elements_by_id"):
            try:
                self.namespace_tree = self._build_tree_from_namespace_node(self.graph.namespaces, self.graph.elements_by_id)
            except Exception:
                self.namespace_tree = self._build_namespace_tree(self.created)
        else:
            self.namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)

        self.all_referenced_type_names: Set[str] = self._collect_referenced_types()
        self._create_stub_elements()
        self._resolve_association_targets()
        self._cleanup_invalid_associations()
        self._ensure_association_types_materialized()
        if self.graph and hasattr(self.graph, "namespaces") and hasattr(self.graph, "elements_by_id"):
            try:
                for name, elem in self.created.items():
                    if elem.xmi not in self.graph.elements_by_id:
                        self.graph.elements_by_id[elem.xmi] = elem
                self.namespace_tree = self._build_tree_from_namespace_node(self.graph.namespaces, self.graph.elements_by_id)
            except Exception:
                self.namespace_tree = self._build_namespace_tree(self.created)
        else:
            self.namespace_tree = self._build_namespace_tree(self.created)
        self._validate_model()

    def _ensure_association_types_materialized(self) -> None:
        try:
            present_ids = {elem.xmi for elem in self.created.values()}
        except Exception:
            present_ids = set()
        xmi_to_name: Dict[XmiId, ElementName] = {xmi: name for name, xmi in self.name_to_xmi.items()}
        for assoc in list(self.model.associations):
            for end_id in (assoc.src, assoc.tgt):
                if end_id not in present_ids:
                    name = xmi_to_name.get(end_id) or ElementName(f"Type_{str(end_id)[-8:]}")
                    try:
                        stub_element: UmlElement = UmlElement(
                            xmi=end_id,
                            name=name,
                            kind=ElementKind.DATATYPE,
                            members=[],
                            clang=ClangMetadata(),
                            used_types=frozenset(),
                            underlying=None,
                            is_stub=True,
                            original_data={"materialized_stub": True},
                        )
                        self.created[name] = stub_element
                        present_ids.add(end_id)
                    except Exception:
                        pass

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
            try:
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
            except Exception:
                tree[str(q_name)] = info
        return tree

    def _collect_referenced_types(self) -> Set[str]:
        all_referenced_type_names: Set[str] = set()
        for _, info in self.created.items():
            for m in info.members:
                if m.type_repr:
                    all_referenced_type_names.add(m.type_repr)
            if hasattr(info, 'operations'):
                for op in info.operations:
                    if op.return_type:
                        all_referenced_type_names.add(op.return_type)
                    for _, param_type in op.parameters:
                        if param_type:
                            all_referenced_type_names.add(param_type)
            if hasattr(info, 'templates'):
                for t in info.templates:
                    all_referenced_type_names.add(t)
        for assoc in self.model.associations:
            pass
        return all_referenced_type_names

    def _create_stub_elements(self) -> None:
        logger.info(f"Creating stub elements for {len(self.all_referenced_type_names)} referenced types")
        for type_name in self.all_referenced_type_names:
            if type_name in self.created or ElementName(type_name) in self.name_to_xmi:
                continue
            if type_name in ['int', 'char', 'bool', 'float', 'double', 'void', 'string', 'std::string']:
                continue
            try:
                stub_id: XmiId = XmiId(stable_id(f"stub:{type_name}"))
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
            except Exception as e:
                logger.error(f"Error creating stub for type {type_name}: {e}")

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
        for assoc in self.model.associations:
            if assoc.src in valid_xmi_ids and assoc.tgt in valid_xmi_ids:
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
            try:
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
            except Exception:
                pass

    def write(self, out_path: str, project_name: str, pretty: bool = False) -> None:
        namespace_tree: NamespaceTree = self._build_namespace_tree(self.created)
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer: XmiWriter = XmiWriter(xf, xml_model=NEW_DEFAULT_META.xml)
            writer.start_doc(project_name, model_id="model_1")
            visitor: UmlXmiWritingVisitor = UmlXmiWritingVisitor(writer, self.name_to_xmi, self.model)
            self._write_package_contents(visitor, namespace_tree)
            for assoc in self.model.associations:
                writer.write_association(assoc, uml_model=NEW_DEFAULT_META.uml)
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
            writer.end_doc()
        if pretty:
            try:
                parser = etree.XMLParser(remove_blank_text=True)
                tree = etree.parse(out_path, parser)
                tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
            except Exception as e:
                logger.warning(f"Pretty-print failed: {e}")

__all__ = ["XmiGenerator"]


