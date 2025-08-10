

# ---------- Model builder (parser + initial analysis) ----------
from typing import Dict, Any, List,Tuple
from CppParser import CppTypeParser

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

