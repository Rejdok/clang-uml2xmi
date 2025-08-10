
from UmlModel import UmlModel

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
        referenced_types = set()

        # 1. Члены классов
        for info in self.created.values():
            for m in info.get("members", []):
                if m.get("type_repr"):
                    referenced_types.add(m["type_repr"])

        # 2. Операции и параметры
        for info in self.created.values():
            for op in info.get("operations", []):
                if op.get("return"):
                    referenced_types.add(op["return"])
                for p in op.get("params", []):
                    if p.get("type"):
                        referenced_types.add(p["type"])

        # 3. Зависимости (owner, typ)
        for owner, typ in self.model.dependencies:
            referenced_types.add(owner)
            referenced_types.add(typ)

        # 4. Ассоциации
        for assoc in self.model.associations:
            # src/tgt — это xmi:id, добавляем как есть
            if assoc.get("src"):
                referenced_types.add(assoc["src"])
            if assoc.get("tgt"):
                referenced_types.add(assoc["tgt"])
            # memberEnd — список xmi:id концов
            for end_id in assoc.get("memberEnds", []):
                referenced_types.add(end_id)
            # ownedEnd.type — тип конца ассоциации
            for end in assoc.get("ownedEnds", []):
                t = end.get("type")
                if t:
                    referenced_types.add(t)

        # 5. Обобщения (generalization)
        for child_id, parent_id in getattr(self.model, "generalizations", []) or []:
            referenced_types.add(child_id)
            referenced_types.add(parent_id)

        # 6. Параметры свойств/атрибутов (если встречаются в raw UML)
        for info in self.created.values():
            for m in info.get("members", []):
                if m.get("type"):
                    referenced_types.add(m["type"])

        # --- СОЗДАНИЕ ЗАГЛУШЕК ---
        for tname in referenced_types:
            if not tname:
                continue
            if tname.startswith("id_"):
                # Заглушка с оригинальным xmi:id
                if tname not in self.name_to_xmi.values():
                    name = f"stub_{tname}"
                    self.name_to_xmi[name] = tname
                    self.created[name] = {
                        "kind": "datatype",
                        "name": name,
                        "xmi": tname,
                        "clang": {}
                    }
            else:
                # Заглушка по имени
                if tname not in self.name_to_xmi:
                    tid = stable_id(f"type:{tname}")
                    self.name_to_xmi[tname] = tid
                    self.created[tname] = {
                        "kind": "datatype",
                        "name": tname,
                        "xmi": tid,
                        "clang": {}
                    }


        # --- теперь запись XMI ---
        with etree.xmlfile(out_path, encoding="utf-8") as xf:
            writer = XmiWriter(xf)
            ctx = writer.start_doc(project_name, model_id="model_1")

            for key, info in list(self.created.items()):
                self._write_element(xf, writer, key, info)

            for assoc in self.model.associations:
                writer.write_association(assoc)

            for owner, typ in self.model.dependencies:
                dep_id = stable_id(f"dep:{owner}:{typ}")
                supplier = self.name_to_xmi.get(typ) or self.ensure_type_exists(typ)
                client = self.name_to_xmi.get(owner) or None
                attribs = {XMI_TYPE: "uml:Dependency", XMI_ID: dep_id, "name": f"dep_{xml_text(owner)}_to_{xml_text(typ)}"}
                if client:
                    attribs["client"] = client
                if supplier:
                    attribs["supplier"] = supplier
                dep_el = etree.Element("packagedElement", attrib=attribs, nsmap=NSMAP)
                xf.write(dep_el)

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
                tref = self.name_to_xmi.get(u) or self.ensure_type_exists(u)
                if tref:
                    writer.write_generalization(stable_id(name + ":gen"), tref)
            writer.end_packaged_element()

        else:  # class
            writer.start_packaged_element(xmi, "uml:Class", name, is_abstract=is_abstract)

            # --- templates handling ---
            for t in info.get("templates", []):
                tp_id = stable_id(name + ":tpl:" + t)
                tp_el = etree.Element("ownedTemplateParameter", attrib={
                    XMI_TYPE: "uml:ClassifierTemplateParameter",
                    XMI_ID: tp_id
                }, nsmap=NSMAP)

                # find xmi id of the template parameter type (if present)
                type_xmi = self.name_to_xmi.get(t)
                type_kind = self.created.get(t, {}).get("kind") if t in self.created else None

                # create stub if needed
                if not type_xmi:
                    type_xmi = stable_id("stub:" + t)
                    self.created[t] = {"kind": "class", "xmi": type_xmi, "name": t, "clang": {}}
                    self.name_to_xmi[t] = type_xmi
                    stub_class = etree.Element("packagedElement", attrib={
                        XMI_TYPE: "uml:Class",
                        XMI_ID: type_xmi,
                        "name": t
                    }, nsmap=NSMAP)
                    xf.write(stub_class)

                # determine uml element type
                uml_type = {
                    "class": "uml:Class",
                    "datatype": "uml:DataType",
                    "enum": "uml:Enumeration",
                    "typedef": "uml:DataType"
                }.get(type_kind, "uml:Class")

                owned_param_el = etree.Element("ownedParameteredElement", attrib={
                    XMI_TYPE: uml_type,
                    # here idref is appropriate for referencing an external packagedElement
                    f"{{{XMI_NS}}}idref": type_xmi
                }, nsmap=NSMAP)
                tp_el.append(owned_param_el)
                xf.write(tp_el)

            # --- members ---
            for m in info.get("members", []):
                aid = stable_id(name + ":attr:" + m["name"])
                tref = None
                trepr = m.get("type_repr")
                if trepr:
                    tref = self.name_to_xmi.get(trepr)
                    if not tref:
                        cand = CppTypeParser.match_known_types_from_parsed(
                            CppTypeParser.extract_all_type_identifiers(trepr),
                            self.name_to_xmi.keys()
                        )
                        tref = self.name_to_xmi.get(cand[0]) if cand else None
                    if not tref:
                        tref = self.ensure_type_exists(trepr)
                writer.write_owned_attribute(
                    aid, m["name"], visibility=m.get("visibility", "private"),
                    type_ref=tref, is_static=m.get("is_static", False) or m.get("isStatic", False)
                )

            # --- operations ---
            for op in info.get("operations", []):
                oid = stable_id(name + ":op:" + op["name"])
                writer.start_owned_operation(
                    oid, op["name"], visibility=op.get("visibility", "public"),
                    is_static=op.get("is_static", False) or op.get("isStatic", False),
                    is_abstract=op.get("is_abstract", False) or op.get("isAbstract", False)
                )
                for p in op.get("params", []):
                    pid = stable_id(name + ":op:" + op["name"] + ":param:" + p["name"])
                    pref = None
                    if p.get("type"):
                        pref = self.name_to_xmi.get(p["type"])
                        if not pref:
                            cand = CppTypeParser.match_known_types_from_parsed(
                                CppTypeParser.extract_all_type_identifiers(p["type"]),
                                self.name_to_xmi.keys()
                            )
                            pref = self.name_to_xmi.get(cand[0]) if cand else None
                        if not pref:
                            pref = self.ensure_type_exists(p["type"])
                    writer.write_owned_parameter(
                        pid, p["name"], direction=p.get("direction", "in"),
                        type_ref=pref, default_value=p.get("default")
                    )

                if op.get("return"):
                    r = op.get("return")
                    rref = self.name_to_xmi.get(r)
                    if not rref:
                        cand = CppTypeParser.match_known_types_from_parsed(
                            CppTypeParser.extract_all_type_identifiers(r),
                            self.name_to_xmi.keys()
                        )
                        rref = self.name_to_xmi.get(cand[0]) if cand else None
                    if not rref:
                        rref = self.ensure_type_exists(r)
                    if rref:
                        prid = stable_id(name + ":op:" + op["name"] + ":return")
                        writer.write_owned_parameter(prid, "return", direction="return", type_ref=rref)
                writer.end_owned_operation()

            writer.end_packaged_element()
