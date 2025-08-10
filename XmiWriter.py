# ---------- XMI writer ----------
# Пространства имён XMI и UML
XMI_NS = "http://www.omg.org/XMI"
UML_NS = "http://www.eclipse.org/uml2/5.0.0/UML"

# Константы для корректных имён атрибутов
XMI_ID = f"{{{XMI_NS}}}id"
XMI_IDREF = f"{{{XMI_NS}}}idref"
XMI_TYPE = f"{{{XMI_NS}}}type"

# Карта пространств имён
NSMAP = {
    "xmi": XMI_NS,
    "uml": UML_NS
}

class XmiWriter:
    def __init__(self, xf: etree.xmlfile):
        self.xf = xf
        self._ctx_stack = []

    def start_doc(self, model_name: str, model_id: str = "model_1"):
        self.xf.write_declaration()
        xmi_ctx = self.xf.element(
            f"{{{XMI_NS}}}XMI",
            nsmap=NSMAP,
            **{"xmi:version": "2.1"}
        )
        xmi_ctx.__enter__()

        model_ctx = self.xf.element(
            f"{{{UML_NS}}}Model",
            **{
                XMI_ID: model_id,
                "name": model_name
            }
        )
        model_ctx.__enter__()

        return (xmi_ctx, model_ctx)

    def end_doc(self, ctx):
        xmi_ctx, model_ctx = ctx
        model_ctx.__exit__(None, None, None)
        xmi_ctx.__exit__(None, None, None)

    def start_packaged_element(self, xmi_id: str, xmi_type: str, name: str,
                               is_abstract: bool=False, extra_attrs: Optional[Dict[str,str]] = None):
        # гарантируем, что тип будет в формате "uml:Class"
        if not xmi_type.startswith("uml:"):
            xmi_type = f"uml:{xmi_type}"
        attrs = {XMI_TYPE: xmi_type, XMI_ID: xmi_id, "name": xml_text(name)}
        if is_abstract:
            attrs["isAbstract"] = "true"
        # добавляем дополнительные атрибуты (например: {"templateParameter": "<id>"} )
        if extra_attrs:
            for k, v in extra_attrs.items():
                attrs[k] = v
        ctx = self.xf.element("packagedElement", nsmap=NSMAP, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_packaged_element(self):
        ctx = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_attribute(self, aid: str, name: str, visibility: str="private", type_ref: Optional[str]=None, is_static: bool=False):
        # NOTE: use attribute `type` to reference the classifier by xmi:id
        attrs = {XMI_ID: aid, "name": xml_text(name), "visibility": xml_text(visibility)}
        if is_static:
            attrs["isStatic"] = "true"
        if type_ref:
            attrs["type"] = type_ref
        el = etree.Element("ownedAttribute", attrib=attrs, nsmap=NSMAP)
        self.xf.write(el)

    def start_owned_operation(self, oid: str, name: str, visibility: str="public", is_static: bool=False, is_abstract: bool=False):
        attrs = {XMI_ID: oid, "name": xml_text(name)}
        if visibility:
            attrs["visibility"] = xml_text(visibility)
        if is_static:
            attrs["isStatic"] = "true"
        if is_abstract:
            attrs["isAbstract"] = "true"
        ctx = self.xf.element("ownedOperation", nsmap=NSMAP, **attrs)
        ctx.__enter__()
        self._ctx_stack.append(ctx)

    def end_owned_operation(self):
        ctx = self._ctx_stack.pop()
        ctx.__exit__(None, None, None)

    def write_owned_parameter(self, pid: str, name: str, direction: str="in", type_ref: Optional[str]=None, default_value: Optional[str]=None, is_ordered: bool=True, is_unique: bool=True):
        # NOTE: use attribute `type` to reference parameter type by xmi:id
        attrs = {XMI_ID: pid, "name": xml_text(name), "direction": xml_text(direction)}
        attrs["isOrdered"] = "true" if is_ordered else "false"
        attrs["isUnique"] = "true" if is_unique else "false"
        if type_ref:
            attrs["type"] = type_ref
        el = etree.Element("ownedParameter", attrib=attrs, nsmap=NSMAP)
        self.xf.write(el)
        if default_value is not None:
            dv = etree.Element("defaultValue", attrib={XMI_ID: stable_id(pid + ":default"), "value": xml_text(default_value)}, nsmap=NSMAP)
            self.xf.write(dv)

    def write_literal(self, lid: str, name: str):
        el = etree.Element("ownedLiteral", attrib={XMI_ID: lid, "name": xml_text(name)}, nsmap=NSMAP)
        self.xf.write(el)

    def write_generalization(self, gid: str, general_ref: str):
        # use attribute 'general' to reference parent classifier by id
        el = etree.Element("generalization", attrib={XMI_ID: gid, "general": general_ref}, nsmap=NSMAP)
        self.xf.write(el)

    def write_association(self, assoc: Dict[str, Any]):
        # Prefer precomputed stable ids (set earlier in XmiGenerator.write)
        aid = assoc.get('_assoc_id') or stable_id(f"assoc:{assoc['src']}:{assoc['tgt']}:{assoc.get('name','')}")
        assoc_el = etree.Element(
            "packagedElement",
            attrib={
                XMI_TYPE: "uml:Association",
                XMI_ID: aid,
                "name": xml_text(assoc.get("name") or "")
            },
            nsmap=NSMAP
        )

        # compute end ids (use precomputed if available)
        end1_id = assoc.get('_end1_id') or stable_id(aid + ":end1")
        end2_id = assoc.get('_end2_id') or stable_id(aid + ":end2")

        def add_bound_value(parent, tag, value):
            """Добавляет lowerValue/upperValue с правильным xmi:type."""
            if value == "-1" or value == "*" or value.strip() == "*":
                literal_type = "uml:LiteralUnlimitedNatural"
                literal_value = "*"
            else:
                literal_type = "uml:LiteralInteger"
                literal_value = str(value)
            etree.SubElement(
                parent, tag,
                attrib={
                    XMI_TYPE: literal_type,
                    XMI_ID: stable_id(parent.get(XMI_ID) + ":" + tag),
                    "value": literal_value
                },
                nsmap=NSMAP
            )

        # end1 (reference the type via attribute `type`)
        end1_id = stable_id(aid + ":end1")
        end1 = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={XMI_ID: end1_id, "type": assoc["src"], "aggregation": assoc.get("aggregation","none")},
            nsmap=NSMAP
        )
        add_bound_value(end1, "lowerValue", "1")
        add_bound_value(end1, "upperValue", "1")

        # end2
        end2_id = stable_id(aid + ":end2")
        end2 = etree.SubElement(
            assoc_el, "ownedEnd",
            attrib={XMI_ID: end2_id, "type": assoc["tgt"], "aggregation": assoc.get("aggregation","none")},
            nsmap=NSMAP
        )
        if assoc.get("multiplicity") == "*":
            add_bound_value(end2, "lowerValue", "0")
            add_bound_value(end2, "upperValue", "*")
        else:
            add_bound_value(end2, "lowerValue", "1")
            add_bound_value(end2, "upperValue", "1")

        self.xf.write(assoc_el)

    def write_packaged_element_raw(self, element: etree._Element):
        self.xf.write(element)

