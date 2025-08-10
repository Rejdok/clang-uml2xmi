
import re
from typing import *

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

