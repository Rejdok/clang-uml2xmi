from typing import Any, Dict
from lxml import etree

from UmlModel import UmlModel
from Utils import stable_id, xml_text
from XmiCommon import *
from XmiWriter import XmiWriter

class XmiGenerator:
    def __init__(self, model: UmlModel):
        self.model = model
        self.created = model.elements
        self.name_to_xmi = model.name_to_xmi

    def ensure_type_exists(self, type_name: str):
        if not type_name:
            return None
        if type_name.startswith("id_"):
            tid = type_name
            if tid not in self.name_to_xmi.values():
                name = f"stub_{tid}"
                self.name_to_xmi[name] = tid
                self.created[name] = {"kind": "datatype", "name": name, "xmi": tid, "clang": {}}
            return tid
        
        tid = self.name_to_xmi.get(type_name)
        if tid:
            return tid
            
        tid = stable_id(f"type:{type_name}")
        self.name_to_xmi[type_name] = tid
        self.created[type_name] = {"kind": "datatype", "name": type_name, "xmi": tid, "clang": {}}
        return tid

    def _build_namespace_tree(self):
        root = {'_children': {}, '_elements': []}
        for q_name, element_info in self.created.items():
            parts = q_name.split('::')
            element_info['name'] = parts[-1]
            ns_parts = parts[:-1]
            
            node = root
            for part in ns_parts:
                node = node['_children'].setdefault(part, {'_children': {}, '_elements': []})
            
            node['_elements'].append(element_info)
        return root

    def _write_package_contents(self, writer: XmiWriter, ns_node: Dict, ns_path: str = ""):
        # Write sub-packages first
        for name, child_node in ns_node['_children'].items():
            current_path = f"{ns_path}::{name}" if ns_path else name
            pkg_id = stable_id(f"pkg:{current_path}")
            
            writer.start_packaged_element(pkg_id, "uml:Package", name)
            self._write_package_contents(writer, child_node, current_path)
            writer.end_packaged_element()

        # Write elements (classes, enums, etc.) in the current package
        for element_info in ns_node['_elements']:
            self._write_element(writer, element_info)

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

        # Step 2: Build the namespace hierarchy
        namespace_tree = self._build_namespace_tree()

        # Step 3: Write the document
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer = XmiWriter(xf)
            writer.start_doc(project_name, model_id="model_1")

            self._write_package_contents(writer, namespace_tree)
            
            # Associations, Dependencies, and Generalizations are written at the root level
            for assoc in self.model.associations:
                writer.write_association(assoc)

            for owner_q_name, typ in self.model.dependencies:
                client_info = self.created.get(owner_q_name)
                if not client_info: continue

                client_id = client_info['xmi']
                supplier_id = self.name_to_xmi.get(typ)
                
                if client_id and supplier_id:
                    dep_id = stable_id(f"dep:{owner_q_name}:{typ}")
                    attribs = {
                        XMI_TYPE: "uml:Dependency", XMI_ID: dep_id,
                        "name": f"dep_{xml_text(owner_q_name)}_to_{xml_text(typ)}",
                        "client": client_id, "supplier": supplier_id
                    }
                    dep_el = etree.Element("packagedElement", attrib=attribs, nsmap=NSMAP)
                    xf.write(dep_el)

            for child_id, parent_id in getattr(self.model, "generalizations", []) or []:
                writer.write_generalization(stable_id(child_id + ":gen"), parent_id)

            writer.end_doc()

    def _write_element(self, writer: XmiWriter, info: Dict[str,Any]):
        kind = info.get("kind", "class")
        name = info.get("name")
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract", False))

        if kind == "enum":
            writer.start_packaged_element(xmi, "Enumeration", name, is_abstract=is_abstract)
            for lit in info.get("literals", []):
                writer.write_literal(stable_id(xmi + ":lit:" + lit), lit)
            writer.end_packaged_element()
        elif kind == "datatype":
             writer.start_packaged_element(xmi, "DataType", name, is_abstract=is_abstract)
             writer.end_packaged_element()
        elif kind == "typedef":
            writer.start_packaged_element(xmi, "DataType", name, is_abstract=is_abstract)
            if info.get("underlying"):
                tref = self.name_to_xmi.get(info["underlying"])
                if tref:
                    writer.write_generalization(stable_id(xmi + ":gen"), tref)
            writer.end_packaged_element()
        else:  # class
            writer.start_packaged_element(xmi, "uml:Class", name, is_abstract=is_abstract)
            
            for m in info.get("members", []):
                aid = stable_id(xmi + ":attr:" + m["name"])
                tref = self.name_to_xmi.get(m.get("type_repr"))
                writer.write_owned_attribute(
                    aid, m["name"], visibility=m.get("visibility", "private"),
                    type_ref=tref, is_static=m.get("is_static", False)
                )
            
            for op in info.get("operations", []):
                oid = stable_id(xmi + ":op:" + op["name"])
                writer.start_owned_operation(
                    oid, op["name"], visibility=op.get("visibility", "public"),
                    is_static=op.get("is_static", False),
                    is_abstract=op.get("is_abstract", False)
                )
                for p in op.get("params", []):
                    pid = stable_id(oid + ":param:" + p["name"])
                    pref = self.name_to_xmi.get(p.get("type"))
                    writer.write_owned_parameter(
                        pid, p["name"], direction=p.get("direction", "in"),
                        type_ref=pref, default_value=p.get("default")
                    )
                ret_type_name = op.get("return")
                if ret_type_name:
                    rref = self.name_to_xmi.get(ret_type_name)
                    if rref:
                        prid = stable_id(oid + ":return")
                        writer.write_owned_parameter(prid, "return", direction="return", type_ref=rref)
                writer.end_owned_operation()
            
            writer.end_packaged_element()
