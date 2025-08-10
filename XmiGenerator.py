from typing import Any, Dict
from lxml import etree

from UmlModel import UmlModel
from Utils import stable_id, xml_text
from Model import UmlModel as UmlModelConfig, DEFAULT_MODEL
from XmiWriter import XmiWriter

# -------------------- Visitor Pattern Implementation --------------------

class XmiElementVisitor:
    """Base class for the Visitor pattern."""
    def __init__(self, writer: XmiWriter, name_to_xmi: Dict[str, str]):
        self.writer = writer
        self.name_to_xmi = name_to_xmi

    def visit(self, info: Dict[str, Any]):
        """Dispatches the element to the correct visit method."""
        kind = info.get("kind", "class")
        method_name = f'visit_{kind}'
        visitor_method = getattr(self, method_name, self.generic_visit)
        return visitor_method(info)

    def generic_visit(self, info: Dict[str, Any]):
        """Fallback for unknown element kinds."""
        print(f"Warning: No visitor method for kind '{info.get('kind')}'")

    def visit_class(self, info: Dict[str, Any]):
        raise NotImplementedError

    def visit_enum(self, info: Dict[str, Any]):
        raise NotImplementedError

    def visit_datatype(self, info: Dict[str, Any]):
        raise NotImplementedError

    def visit_typedef(self, info: Dict[str, Any]):
        raise NotImplementedError

class UmlXmiWritingVisitor(XmiElementVisitor):
    """Concrete visitor that writes UML elements to an XMI file."""

    def visit_class(self, info: Dict[str, Any]):
        name = info.get("name")
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract", False))
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.class_type, name, is_abstract=is_abstract)
        
        for m in info.get("members", []):
            aid = stable_id(xmi + ":attr:" + m["name"])
            tref = self.name_to_xmi.get(m.get("type_repr"))
            self.writer.write_owned_attribute(
                aid, m["name"], visibility=m.get("visibility", "private"),
                type_ref=tref, is_static=m.get("is_static", False)
            )
        
        for op in info.get("operations", []):
            oid = stable_id(xmi + ":op:" + op["name"])
            self.writer.start_owned_operation(
                oid, op["name"], visibility=op.get("visibility", "public"),
                is_static=op.get("is_static", False),
                is_abstract=op.get("is_abstract", False)
            )
            for p in op.get("params", []):
                pid = stable_id(oid + ":param:" + p["name"])
                pref = self.name_to_xmi.get(p.get("type"))
                self.writer.write_owned_parameter(
                    pid, p["name"], direction=p.get("direction", "in"),
                    type_ref=pref, default_value=p.get("default")
                )
            ret_type_name = op.get("return")
            if ret_type_name:
                rref = self.name_to_xmi.get(ret_type_name)
                if rref:
                    prid = stable_id(oid + ":return")
                    self.writer.write_owned_parameter(prid, "return", direction="return", type_ref=rref)
            self.writer.end_owned_operation()
        
        self.writer.end_packaged_element()

    def visit_enum(self, info: Dict[str, Any]):
        name = info.get("name")
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract", False))
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.enum_type, name, is_abstract=is_abstract)
        for lit in info.get("literals", []):
            self.writer.write_literal(stable_id(xmi + ":lit:" + lit), lit)
        self.writer.end_packaged_element()

    def visit_datatype(self, info: Dict[str, Any]):
        name = info.get("name")
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract", False))
        # Stubs are named with their full type string
        q_name = next((k for k, v in self.name_to_xmi.items() if v == xmi), name)
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, q_name, is_abstract=is_abstract)
        self.writer.end_packaged_element()

    def visit_typedef(self, info: Dict[str, Any]):
        name = info.get("name")
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract", False))
        
        # Use UML model for element type
        uml_model = DEFAULT_MODEL.uml
        self.writer.start_packaged_element(xmi, uml_model.datatype_type, name, is_abstract=is_abstract)
        if info.get("underlying"):
            tref = self.name_to_xmi.get(info["underlying"])
            if tref:
                self.writer.write_generalization(stable_id(xmi + ":gen"), tref)
        self.writer.end_packaged_element()

# -------------------- XMI Generator (Refactored) --------------------

class XmiGenerator:
    def __init__(self, model: UmlModel):
        self.model = model
        self.created = model.elements
        self.name_to_xmi = model.name_to_xmi

    def ensure_type_exists(self, type_name: str):
        if not type_name: return None
        if type_name.startswith("id_"):
            tid = type_name
            if tid not in self.name_to_xmi.values():
                name = f"stub_{tid}"
                self.name_to_xmi[name] = tid
                self.created[name] = {"kind": "datatype", "name": name, "xmi": tid, "clang": {}}
            return tid
        
        tid = self.name_to_xmi.get(type_name)
        if tid: return tid
            
        tid = stable_id(f"type:{type_name}")
        self.name_to_xmi[type_name] = tid
        self.created[type_name] = {"kind": "datatype", "name": type_name, "xmi": tid, "clang": {}}
        return tid

    def _build_namespace_tree(self, elements_to_process: Dict):
        root = {'_children': {}, '_elements': []}
        for q_name, element_info in elements_to_process.items():
            parts = q_name.split('::')
            element_info['name'] = parts[-1]
            ns_parts = parts[:-1]
            
            node = root
            for part in ns_parts:
                node = node['_children'].setdefault(part, {'_children': {}, '_elements': []})
            
            node['_elements'].append(element_info)
        return root

    def _write_package_contents(self, visitor: XmiElementVisitor, ns_node: Dict, ns_path: str = ""):
        for name, child_node in ns_node['_children'].items():
            current_path = f"{ns_path}::{name}" if ns_path else name
            pkg_id = stable_id(f"pkg:{current_path}")
            
            visitor.writer.start_packaged_element(pkg_id, "uml:Package", name)
            self._write_package_contents(visitor, child_node, current_path)
            visitor.writer.end_packaged_element()

        for element_info in ns_node['_elements']:
            visitor.visit(element_info)

    def write(self, out_path: str, project_name: str):
        # Step 1: Comprehensive pre-pass for stubs
        all_referenced_type_names = set()
        for info in self.created.values():
            for m in info.get("members", []):
                if m.get("type_repr"): all_referenced_type_names.add(m["type_repr"])
            for op in info.get("operations", []):
                if op.get("return"): all_referenced_type_names.add(op["return"])
                for p in op.get("params", []):
                    if p.get("type"): all_referenced_type_names.add(p["type"])
            for t in info.get("templates", []): all_referenced_type_names.add(t)
        for _, typ in self.model.dependencies:
            all_referenced_type_names.add(typ)
        for info in self.created.values():
            if info.get("kind") == "typedef" and info.get("underlying"):
                all_referenced_type_names.add(info["underlying"])
        
        for type_name in all_referenced_type_names:
            self.ensure_type_exists(type_name)

        # Step 2: Separate real elements from stubs
        real_elements = {k: v for k, v in self.created.items() if v.get('kind') != 'datatype'}
        stub_elements = {k: v for k, v in self.created.items() if v.get('kind') == 'datatype'}

        # Step 3: Build namespace tree for real elements only
        namespace_tree = self._build_namespace_tree(real_elements)

        # Step 4: Write the document
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer = XmiWriter(xf, xml_model=DEFAULT_MODEL.xml)
            writer.start_doc(project_name, model_id="model_1")
            
            visitor = UmlXmiWritingVisitor(writer, self.name_to_xmi)
            
            # Write packaged elements
            self._write_package_contents(visitor, namespace_tree)
            
            # Write all stubs at the root level
            for q_name, stub_info in stub_elements.items():
                # Pass the original qualified name to the visitor
                stub_info['name'] = q_name
                visitor.visit_datatype(stub_info)
            
            # Associations, Dependencies, and Generalizations are written at the root level
            for assoc in self.model.associations:
                writer.write_association(assoc, uml_model=DEFAULT_MODEL.uml)

            for owner_q_name, typ in self.model.dependencies:
                client_info = self.created.get(owner_q_name)
                if not client_info: continue
                client_id = client_info['xmi']
                supplier_id = self.name_to_xmi.get(typ)
                
                if client_id and supplier_id:
                    dep_id = stable_id(f"dep:{owner_q_name}:{typ}")
                    
                    # Use model for dependency attributes
                    uml_model = DEFAULT_MODEL.uml
                    xml_model = DEFAULT_MODEL.xml
                    
                    attribs = {
                        xml_model.xmi_type: "uml:Dependency", 
                        xml_model.xmi_id: dep_id,
                        "name": f"dep_{xml_text(owner_q_name)}_to_{xml_text(typ)}",
                        "client": client_id, 
                        "supplier": supplier_id
                    }
                    dep_el = etree.Element("packagedElement", attrib=attribs, nsmap=xml_model.uml_nsmap)
                    xf.write(dep_el)

            for child_id, parent_id in getattr(self.model, "generalizations", []) or []:
                writer.write_generalization(stable_id(child_id + ":gen"), parent_id)

            writer.end_doc()
