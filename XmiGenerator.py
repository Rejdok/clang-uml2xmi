
from typing import Any, Dict
from CppParser import CppTypeParser
from UmlModel import UmlModel
from Utils import stable_id, xml_text
from lxml import etree

from XmiCommon import *
from XmiWriter import XmiWriter

# ---------- XMI Generator (extracting big run block into methods) ----------
class XmiGenerator:
    def __init__(self, model: UmlModel):
        self.model = model
        # alias for easier access
        self.created = model.elements
        self.name_to_xmi = model.name_to_xmi

    def ensure_type_exists(self, type_name):
        # Если передан уже готовый xmi:id
        if type_name.startswith("id_"):
            tid = type_name
            # Есть ли уже такой id в name_to_xmi?
            if tid not in self.name_to_xmi.values():
                # Придумываем имя для заглушки
                name = f"stub_{tid}"
                self.name_to_xmi[name] = tid
                self.created[name] = {
                    "kind": "datatype",
                    "name": name,
                    "xmi": tid,
                    "clang": {}
                }
            return tid

        # Если это имя
        tid = self.name_to_xmi.get(type_name)
        if tid:
            return tid
        tid = stable_id(f"type:{type_name}")
        self.name_to_xmi[type_name] = tid
        self.created[type_name] = {
            "kind": "datatype",
            "name": type_name,
            "xmi": tid,
            "clang": {}
        }
        return tid

    def write(self, out_path: str, project_name: str):
        # Pre-pass to ensure all referenced types have a stub element created for them
        # This prevents creating elements during the main write loop, which causes issues.
        all_referenced_type_names = set()
        for info in self.created.values():
            # Members
            for m in info.get("members", []):
                if m.get("type_repr"):
                    all_referenced_type_names.add(m["type_repr"])
            # Operations
            for op in info.get("operations", []):
                if op.get("return"):
                    all_referenced_type_names.add(op["return"])
                for p in op.get("params", []):
                    if p.get("type"):
                        all_referenced_type_names.add(p["type"])
            # Templates
            for t in info.get("templates", []):
                all_referenced_type_names.add(t)

        # Dependencies
        for _, typ in self.model.dependencies:
            all_referenced_type_names.add(typ)
        
        # Typedefs
        for info in self.created.values():
            if info.get("kind") == "typedef" and info.get("underlying"):
                all_referenced_type_names.add(info["underlying"])

        for type_name in all_referenced_type_names:
            if type_name:
                self.ensure_type_exists(type_name)

        # Main write process
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer = XmiWriter(xf)
            ctx = writer.start_doc(project_name, model_id="model_1")

            processed_keys = set()
            while True:
                keys_to_process = [k for k in self.created.keys() if k not in processed_keys]
                if not keys_to_process:
                    break
                
                for key in keys_to_process:
                    if key in self.created:
                        info = self.created[key]
                        self._write_element(xf, writer, key, info)
                    processed_keys.add(key)

            # Write associations
            for assoc in self.model.associations:
                writer.write_association(assoc)

            # Write dependencies
            for owner, typ in self.model.dependencies:
                dep_id = stable_id(f"dep:{owner}:{typ}")
                supplier = self.name_to_xmi.get(typ)
                client = self.name_to_xmi.get(owner)
                
                if client and supplier:
                    attribs = {
                        XMI_TYPE: "uml:Dependency", 
                        XMI_ID: dep_id, 
                        "name": f"dep_{xml_text(owner)}_to_{xml_text(typ)}",
                        "client": client,
                        "supplier": supplier
                    }
                    dep_el = etree.Element("packagedElement", attrib=attribs, nsmap=NSMAP)
                    xf.write(dep_el)

            # Write generalizations
            for child_id, parent_id in getattr(self.model, "generalizations", []) or []:
                writer.write_generalization(stable_id(child_id + ":gen"), parent_id)

            writer.end_doc(ctx)

    def _write_element(self, xf: etree.xmlfile, writer: XmiWriter, key: str, info: Dict[str,Any]):
        kind = info.get("kind", "class")
        name = info.get("name") or key
        xmi = info["xmi"]
        is_abstract = bool(info.get("clang", {}).get("is_abstract") or info.get("clang", {}).get("abstract") or False)

        if kind == "enum":
            writer.start_packaged_element(xmi, "Enumeration", name, is_abstract=is_abstract)
            for lit in info.get("literals", []):
                writer.write_literal(stable_id(name + ":lit:" + lit), lit)
            writer.end_packaged_element()

        elif kind in ("datatype", "typedef"):
            writer.start_packaged_element(xmi, "DataType", name, is_abstract=is_abstract)
            if kind == "typedef" and info.get("underlying"):
                u = info.get("underlying")
                # For typedef, we create a generalization to the underlying type
                tref = self.name_to_xmi.get(u)
                if tref:
                    writer.write_generalization(stable_id(name + ":gen"), tref)
            writer.end_packaged_element()

        else:  # class, interface, etc.
            writer.start_packaged_element(xmi, "uml:Class", name, is_abstract=is_abstract)

            # --- templates handling ---
            # This logic remains complex as it deals with UML template specifics
            for t in info.get("templates", []):
                tp_id = stable_id(name + ":tpl:" + t)
                # The type itself is guaranteed to exist due to the pre-pass
                type_xmi = self.name_to_xmi.get(t)

                tp_el = etree.Element("ownedTemplateSignature", attrib={
                    XMI_TYPE: "uml:RedefinableTemplateSignature",
                    XMI_ID: stable_id(xmi + "_ts")
                }, nsmap=NSMAP)
                
                param_el = etree.SubElement(tp_el, "ownedParameter", attrib={
                    XMI_TYPE: "uml:ClassifierTemplateParameter",
                    XMI_ID: tp_id
                })
                
                owned_param_el = etree.SubElement(param_el, "ownedParameteredElement", attrib={
                    XMI_TYPE: "uml:Class",
                    XMI_ID: stable_id(tp_id + "_pe"),
                    "name": t
                })
                xf.write(tp_el)

            # --- members ---
            for m in info.get("members", []):
                aid = stable_id(name + ":attr:" + m["name"])
                tref = self.name_to_xmi.get(m.get("type_repr"))
                writer.write_owned_attribute(
                    aid, m["name"], visibility=m.get("visibility", "private"),
                    type_ref=tref, is_static=m.get("is_static", False)
                )

            # --- operations ---
            for op in info.get("operations", []):
                oid = stable_id(name + ":op:" + op["name"])
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
