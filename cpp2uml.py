#!/usr/bin/env python3
"""
cpp2uml_fixed.py - patched version fixing XMI reference attributes

Changes made:
 - use UML/XMI attribute names for references instead of always using xmi:idref
   * ownedAttribute/ownedParameter/ownedEnd now use attribute `type` to reference types
   * generalization uses attribute `general` to reference the parent
   * Dependency elements are emitted with `client` and `supplier` attributes
 - ensure when creating stub/type references we set consistent xmi:id values
 - small readability improvements

This file is a one-to-one edit of the provided script with the above fixes applied.
"""
from typing import Optional, List, Dict, Any, Tuple
import sys, re, uuid, hashlib, json
from dataclasses import dataclass
from lxml import etree

# Try orjson if available (faster), otherwise fallback
try:
    import orjson as _orjson  # type: ignore
    def load_json(path: str) -> Any:
        with open(path, "rb") as f:
            return _orjson.loads(f.read())
except Exception:
    def load_json(path: str) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ---------- Utilities ----------
def xid() -> str:
    return "id_" + uuid.uuid4().hex


def stable_id(s: str) -> str:
    return "id_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def xml_text(v) -> str:
    return "" if v is None else str(v)


# ---------- Type parsing helpers ----------
class CppTypeParser:
    _CONTAINER_KEYWORDS = {"vector", "list", "deque", "set", "unordered_set", "map", "unordered_map", "array", "span", "tuple"}
    _SMART_PTRS = {"unique_ptr", "shared_ptr", "weak_ptr", "scoped_ptr", "intrusive_ptr"}

    @staticmethod
    def safe_type_name(t) -> Optional[str]:
        if not t:
            return None
        if isinstance(t, str):
            s = t.strip()
            return s if s else None
        if isinstance(t, dict):
            for k in ("qualified_name", "qualifiedName", "display_name", "displayName", "name", "type"):
                if k in t and t[k]:
                    return str(t[k])
            inner = t.get("type")
            if isinstance(inner, dict):
                return inner.get("name") or inner.get("display_name")
        return None

    @staticmethod
    def tokenize_type(s: Optional[str]) -> str:
        s = s or ""
        s = re.sub(r'\b(const|volatile|mutable)\b', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    @staticmethod
    def parse_template_args(type_str: str) -> Tuple[str, List[str]]:
        s = (type_str or "").strip()
        if not s:
            return (s, [])
        depth = 0
        i = 0
        n = len(s)
        while i < n:
            if s[i] == '<':
                outer = s[:i].strip()
                i += 1
                cur = ''
                depth = 1
                args = []
                while i < n and depth > 0:
                    c = s[i]
                    if c == '<':
                        depth += 1
                        cur += c
                    elif c == '>':
                        depth -= 1
                        if depth == 0:
                            if cur.strip():
                                args.append(cur.strip())
                            i += 1
                            break
                        else:
                            cur += c
                    elif c == ',' and depth == 1:
                        args.append(cur.strip()); cur = ''
                    else:
                        cur += c
                    i += 1
                return (outer, [a.strip() for a in args])
            i += 1
        return (s, [])

    @classmethod
    def extract_all_type_identifiers(cls, type_str: Optional[str]) -> List[Dict[str,str]]:
        out = []
        s = cls.tokenize_type(type_str)
        outer, args = cls.parse_template_args(s)
        if outer:
            out.append({'name': outer, 'raw': outer})
        for arg in args:
            out.extend(cls.extract_all_type_identifiers(arg))
        return out

    @staticmethod
    def match_known_types_from_parsed(parsed_list: List[Dict[str,str]], known_names) -> List[str]:
        matched = []
        keys = list(known_names)
        for item in parsed_list:
            token = item.get('name') or ''
            if not token:
                continue
            candidates = [token]
            if '::' in token:
                candidates.append(token.split('::')[-1])
            t = re.sub(r'<.*>$', '', token).strip()
            if t != token:
                candidates.append(t)
                if '::' in t:
                    candidates.append(t.split('::')[-1])
            found = None
            for c in candidates:
                for kn in keys:
                    if kn == c or kn.endswith("::" + c) or c.endswith("::" + kn):
                        found = kn; break
                if found: break
            if found and found not in matched:
                matched.append(found)
        return matched

    @classmethod
    def analyze_type_expr(cls, type_str: Optional[str]) -> Dict[str,Any]:
        t = cls.tokenize_type(type_str)
        result = {"raw": type_str, "base": t, "is_pointer": False, "is_reference": False, "is_rref": False, "is_array": False}
        if not t:
            return result
        if re.search(r'\[\s*\]$', t) or re.search(r'\[\s*\d+\s*\]$', t):
            result["is_array"] = True
        if '&&' in t:
            result["is_rref"] = True
        if '&' in t and '&&' not in t:
            result["is_reference"] = True
        if '*' in t:
            result["is_pointer"] = True
        clean = re.sub(r'(\s*[\*\&]+)|\b(const|volatile|mutable)\b', '', t).strip()
        result["base"] = clean
        outer, args = cls.parse_template_args(clean)
        result["template_base"] = outer.split("::")[-1] if outer else outer
        result["template_args"] = args
        return result


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


# ---------- Model builder (parser + initial analysis) ----------
class CppModelBuilder:
    def __init__(self, j: Dict[str,Any]):
        self.j = j
        # mapping from chosen name (fallback) to xmi id
        self.name_to_xmi: Dict[str,str] = {}
        # internal store of created element metadata
        self.created: Dict[str, Dict[str,Any]] = {}
        self.associations: List[Dict[str,Any]] = []
        self.dependencies: List[Tuple[str,str]] = []

    @staticmethod
    def choose_name(el: Dict[str,Any]) -> str:
        return el.get("qualified_name") or el.get("display_name") or el.get("name") or el.get("id") or xid()

    def prepare(self):
        elements = self.j.get("elements") or self.j.get("entities") or self.j.get("types") or []
        for el in elements:
            if not isinstance(el, dict):
                continue
            chosen = self.choose_name(el)
            u_kind = "class"
            kind_raw = (el.get("type") or el.get("kind") or "").lower()
            if "enum" in kind_raw or el.get("is_enum"):
                u_kind = "enum"
            elif "typedef" in kind_raw or el.get("is_typedef") or el.get("is_alias"):
                u_kind = "typedef"
            elif "interface" in kind_raw or el.get("is_interface"):
                u_kind = "interface"
            elif "struct" in kind_raw or el.get("is_struct") or el.get("is_datatype"):
                u_kind = "datatype"
            xmi = xid()
            self.created[chosen] = {"xmi": xmi, "name": chosen, "kind": u_kind, "clang": el}
            self.name_to_xmi[chosen] = xmi

    def build(self):
        # prepare if not done
        if not self.created:
            self.prepare()

        # second pass: collect members, operations, templates, typedef underlying, associations
        for name, info in list(self.created.items()):
            el = info["clang"]
            kind = info["kind"]

            # templates
            templates = el.get("templates") or el.get("template_parameters") or el.get("template_args") or []
            if templates:
                info["templates"] = []
                for t in templates:
                    if isinstance(t, dict):
                        tname = t.get("name") or t.get("display_name") or t.get("type") or "T"
                    else:
                        tname = str(t)
                    info["templates"].append(tname)
            else:
                base, args = CppTypeParser.parse_template_args(info["name"])
                if args:
                    info["templates"] = args
                    info["name"] = base

            if kind == "enum":
                enumerators = el.get("enumerators") or el.get("values") or el.get("literals") or []
                info["literals"] = []
                for lit in enumerators:
                    if isinstance(lit, dict):
                        lname = lit.get("name") or lit.get("value") or str(lit)
                    else:
                        lname = str(lit)
                    info["literals"].append(lname)
                continue

            if kind == "typedef":
                underlying = el.get("underlying_type") or el.get("type") or el.get("alias_of") or {}
                ustr = None
                if isinstance(underlying, dict):
                    ustr = underlying.get("name") or underlying.get("display_name")
                elif isinstance(underlying, str):
                    ustr = underlying
                info["underlying"] = ustr
                continue

            # members
            members = el.get("members") or el.get("fields") or el.get("variables") or []
            info["members"] = []
            for m in members:
                if isinstance(m, dict):
                    mname = m.get("display_name") or m.get("name") or m.get("id") or ""
                    visibility = m.get("access") or m.get("visibility") or "private"
                    is_static = bool(m.get("is_static") or m.get("static") or False)
                    mtypeobj = m.get("type") or m.get("type_info") or {}
                    tname = CppTypeParser.safe_type_name(mtypeobj) or m.get("type_name") or m.get("type")
                    info["members"].append({"name": mname, "visibility": visibility, "is_static": is_static, "type_repr": tname})
                else:
                    info["members"].append({"name": str(m), "visibility": "private", "is_static": False, "type_repr": None})

            # operations
            operations = el.get("methods") or el.get("functions") or el.get("operations") or []
            info["operations"] = []
            for op in operations:
                opname = op.get("display_name") or op.get("name") or op.get("signature") or "op"
                visibility = op.get("access") or op.get("visibility") or "public"
                is_static = bool(op.get("is_static") or op.get("static") or False)
                is_abstract = bool(op.get("is_pure_virtual") or op.get("is_abstract") or False)
                params = op.get("parameters") or op.get("params") or op.get("arguments") or []
                param_list = []
                for p in params:
                    pname = p.get("name") or p.get("id") or "p"
                    ptype = CppTypeParser.safe_type_name(p.get("type")) or p.get("type_name")
                    pdir = p.get("direction") or "in"
                    pdefault = p.get("default_value") or p.get("default") or None
                    param_list.append({"name": pname, "type": ptype, "direction": pdir, "default": pdefault})
                rt = CppTypeParser.safe_type_name(op.get("return_type")) or CppTypeParser.safe_type_name(op.get("type")) or CppTypeParser.safe_type_name(op.get("returnType"))
                info["operations"].append({"name": opname, "visibility": visibility, "is_static": is_static, "is_abstract": is_abstract, "params": param_list, "return": rt})
                if rt:
                    info.setdefault("used_types", set()).add(rt)
                for p in param_list:
                    if p.get("type"):
                        info.setdefault("used_types", set()).add(p["type"])

        # associations: for each member try to match known types
        for name, info in self.created.items():
            owner_xmi = info["xmi"]
            raws = info.get("members") or []
            for m in raws:
                type_repr = m.get("type_repr")
                if not type_repr:
                    continue
                parsed = CppTypeParser.extract_all_type_identifiers(type_repr)
                matched = CppTypeParser.match_known_types_from_parsed(parsed, self.name_to_xmi.keys())
                an = CppTypeParser.analyze_type_expr(type_repr)
                outer_base = an.get("template_base") or ""
                is_container = any(k in outer_base for k in CppTypeParser._CONTAINER_KEYWORDS) or outer_base in CppTypeParser._CONTAINER_KEYWORDS
                is_smart = any(k in outer_base for k in CppTypeParser._SMART_PTRS) or outer_base in CppTypeParser._SMART_PTRS
                for mt in matched:
                    tgt_xmi = self.name_to_xmi.get(mt)
                    if not tgt_xmi:
                        continue
                    # heuristic aggregation
                    if is_smart:
                        aggregation = "composite" if "unique" in outer_base or "unique_ptr" in outer_base else "shared"
                        # UML uses 'shared' not standard; keep 'none' or 'composite'
                        if aggregation not in ("composite", "shared"):
                            aggregation = "none"
                    else:
                        if an["is_pointer"] or an["is_reference"] or an["is_rref"]:
                            aggregation = "shared"
                        else:
                            aggregation = "none"
                    mult = "*" if is_container or an["is_array"] else "1"
                    self.associations.append({"src": owner_xmi, "tgt": tgt_xmi, "aggregation": aggregation, "multiplicity": mult, "name": m.get("name","")})

        # dependencies: types used but unknown
        for name, info in self.created.items():
            used = info.get("used_types") or set()
            for typename in used:
                if not typename:
                    continue
                # skip if known as element
                # match via parsed tokens
                if typename in self.name_to_xmi:
                    continue
                parsed = CppTypeParser.extract_all_type_identifiers(typename)
                cand = CppTypeParser.match_known_types_from_parsed(parsed, self.name_to_xmi.keys())
                if cand:
                    # already accounted as association maybe; otherwise add dependency to first match
                    continue
                self.dependencies.append((info["name"], typename))

        # expose project_name + created + lists
        project_name = self.j.get("project_name") or self.j.get("project") or "clang_uml_model"
        return {
            "project_name": project_name,
            "created": self.created,
            "associations": self.associations,
            "dependencies": self.dependencies,
            "name_to_xmi": self.name_to_xmi
        }


# ---------- Notation writer (Papyrus minimal) ----------
class NotationWriter:
    def __init__(self, created: Dict[str, Any], out_notation: str, row_wrap: int = 10,
                 step_x: int = 300, step_y: int = 200, width: int = 180, height: int = 100):
        self.created = created
        self.out_notation = out_notation
        self.row_wrap = row_wrap
        self.step_x = step_x
        self.step_y = step_y
        self.width = width
        self.height = height

    @staticmethod
    def kind_to_node_type(kind: str) -> str:
        if kind == "enum":
            return "Enumeration"
        if kind in ("datatype", "typedef"):
            return "DataType"
        return "Class"

    def write(self):
        NSMAP_LOCAL = {
            "notation": "http://www.eclipse.org/papyrus/notation/1.0",
            "xmi": "http://www.omg.org/XMI"
        }
        root_attrs = {
            f"{{{XMI_NS}}}version": "2.0",
            f"{{{XMI_NS}}}id": stable_id("notation"),
            "name": "ClassDiagram"
        }
        diagram_el = etree.Element(f"{{{NSMAP_LOCAL['notation']}}}Diagram", nsmap=NSMAP_LOCAL, attrib=root_attrs)

        idx = 0
        for key, info in self.created.items():
            x = 40 + (idx % self.row_wrap) * self.step_x
            y = 40 + (idx // self.row_wrap) * self.step_y
            node_type = self.kind_to_node_type(info.get("kind", "class"))
            node_attrs = {
                "type": node_type,
                f"{{{XMI_NS}}}id": stable_id(info["xmi"] + ":node"),
                "elementRef": info["xmi"],
                "x": str(x),
                "y": str(y),
                "width": str(self.width),
                "height": str(self.height)
            }
            etree.SubElement(diagram_el, "children", attrib=node_attrs)
            idx += 1

        tree = etree.ElementTree(diagram_el)
        tree.write(self.out_notation, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# ---------- Model returned by analyzer ----------
@dataclass
class UmlModel:
    elements: Dict[str, Dict[str,Any]]
    associations: List[Dict[str,Any]]
    dependencies: List[Tuple[str,str]]
    generalizations: List[Tuple[str,str]]
    name_to_xmi: Dict[str,str]


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


# ---------- Application ----------
class Cpp2UmlApp:
    def __init__(self, in_json: str, out_uml: str, out_notation: str):
        self.in_json = in_json
        self.out_uml = out_uml
        self.out_notation = out_notation

    def run(self):
        j = load_json(self.in_json)
        builder = CppModelBuilder(j)
        prep = builder.build()

        # Build UmlModel structure
        model = UmlModel(
            elements=prep["created"],
            associations=prep["associations"],
            dependencies=prep["dependencies"],
            generalizations=[],  # kept empty — builder doesn't produce explicit generalizations list
            name_to_xmi=prep["name_to_xmi"]
        )

        project_name = prep["project_name"]

        # XMI generation
        xmi_gen = XmiGenerator(model)
        xmi_gen.write(self.out_uml, project_name)

        # Notation generation (Papyrus minimal)
        notation_writer = NotationWriter(model.elements, self.out_notation, row_wrap=10, step_x=300, step_y=200, width=180, height=100)
        notation_writer.write()
        print("Written", self.out_uml, "and", self.out_notation)


# ---------- main ----------
def main():
    if len(sys.argv) < 4:
        print("Usage: python3 cpp2uml.py <clang-uml.json> <out.uml> <out.notation>")
        return 1
    inp, out_uml, out_notation = sys.argv[1:4]
    app = Cpp2UmlApp(inp, out_uml, out_notation)
    app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
