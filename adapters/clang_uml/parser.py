"""
Shared parser facade for clang-uml JSON.

This module hosts the actual implementation of CppTypeParser, so language builders
(C/C++) can import a stable adapter path: adapters.clang_uml.parser.CppTypeParser
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any, Union

from uml_types import (
    TypeToken, TypeAnalysis, TypeAnalysisResult,
    TypeString, TemplateArgs, TypeName
)


class CppTypeParser:
    _CONTAINER_KEYWORDS: frozenset[str] = frozenset({
        "vector", "list", "deque", "set", "unordered_set",
        "map", "unordered_map", "array", "span", "tuple"
    })
    _SMART_PTRS: frozenset[str] = frozenset({
        "unique_ptr", "shared_ptr", "weak_ptr", "scoped_ptr", "intrusive_ptr"
    })

    @staticmethod
    def safe_type_name(t: Union[None, str, Dict[str, Any]]) -> Optional[str]:
        if not t:
            return None
        if isinstance(t, str):
            s: str = t.strip()
            return s if s else None
        if isinstance(t, dict):
            for k in ("qualified_name", "qualifiedName", "display_name", "displayName", "name", "type"):
                if k in t and t[k]:
                    return str(t[k])
            inner: Any = t.get("type")
            if isinstance(inner, dict):
                return inner.get("name") or inner.get("display_name")
        return None

    @staticmethod
    def tokenize_type(s: Optional[str]) -> str:
        s = s or ""
        s = re.sub(r'\b(const|volatile|mutable)\b', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        # Remove simple macro noise/trailing blocks like " > {}" or trailing braces
        s = re.sub(r'(>)\s*\{\s*\}\s*$', r'\1', s)
        s = re.sub(r'\s*\{[^{}]*\}\s*$', '', s)
        s = re.sub(r';[^\n]*$', '', s)
        return s

    @staticmethod
    def parse_type_expr(type_str: Optional[str], _depth_limit: int = 12) -> Dict[str, Any]:
        s: str = CppTypeParser.tokenize_type(type_str)
        if not s:
            return {"kind": "name", "name": ""}
        if s.startswith('decltype(') and s.endswith(')'):
            inner_expr: str = s[9:-1]
            inner = None
            if _depth_limit > 0:
                inner = CppTypeParser.parse_type_expr(inner_expr, _depth_limit - 1)
            return {"kind": "decltype", "expr": s, "inner": inner}
        outer, args = CppTypeParser.parse_template_args(s)
        if args:
            parsed_args: List[Dict[str, Any]] = []
            for a in args:
                a_s = (a or '').strip()
                if not a_s:
                    continue
                if re.match(r'^[0-9]+[uUlLfF]*$', a_s):
                    parsed_args.append({"kind": "literal", "value": a_s})
                else:
                    if _depth_limit > 0:
                        parsed_args.append(CppTypeParser.parse_type_expr(a_s, _depth_limit - 1))
            return {"kind": "template", "base": outer, "args": parsed_args}
        return {"kind": "name", "name": s}

    @staticmethod
    def parse_template_args(type_str: str) -> Tuple[str, List[str]]:
        s: str = CppTypeParser.tokenize_type(type_str)
        if not s:
            return (s, [])
        if s.startswith('decltype(') and s.endswith(')'):
            return (s, [])
        depth: int = 0
        i: int = 0
        n: int = len(s)
        while i < n:
            if s[i] == '<':
                outer: str = s[:i].strip()
                i += 1
                cur: str = ''
                depth = 1
                args: List[str] = []
                while i < n and depth > 0:
                    c: str = s[i]
                    if c == '<':
                        depth += 1
                        cur += c
                    elif c == '>':
                        depth -= 1
                        if depth == 0:
                            if cur.strip():
                                arg = cur.strip()
                                if CppTypeParser._is_valid_template_arg(arg):
                                    args.append(arg)
                            i += 1
                            break
                        else:
                            cur += c
                    elif c == ',' and depth == 1:
                        if cur.strip():
                            arg = cur.strip()
                            if CppTypeParser._is_valid_template_arg(arg):
                                args.append(arg)
                        cur = ''
                    else:
                        cur += c
                    i += 1
                if cur.strip():
                    arg = cur.strip()
                    if CppTypeParser._is_valid_template_arg(arg):
                        args.append(arg)
                return (outer, args)
            i += 1
        return (s, [])

    @staticmethod
    def _is_valid_template_arg(arg: str) -> bool:
        arg = arg.strip()
        if not arg:
            return False
        if re.match(r'^[^\w\s<>:]+$', arg):
            return False
        if arg.count('<') != arg.count('>'):
            return False
        if len(arg) < 2:
            return False
        if re.match(r'^[^\w<]+', arg):
            return False
        return True

    @staticmethod
    def extract_template_base(type_str: str) -> str:
        base, _ = CppTypeParser.parse_template_args(type_str)
        return base

    @staticmethod
    def is_template_instance(type_str: str) -> bool:
        return '<' in type_str and '>' in type_str

    @staticmethod
    def normalize_template_name(type_str: str) -> str:
        base, args = CppTypeParser.parse_template_args(type_str)
        if args:
            return f"{base}<...>"
        return base

    @staticmethod
    def extract_template_parameters(type_str: str) -> List[str]:
        _, args = CppTypeParser.parse_template_args(type_str)
        return args

    @staticmethod
    def is_specialization_of(base_template: str, specialized_type: str) -> bool:
        if not CppTypeParser.is_template_instance(specialized_type):
            return False
        spec_base, _ = CppTypeParser.parse_template_args(specialized_type)
        return spec_base == base_template

    @staticmethod
    def match_known_types_from_parsed(parsed_list: List[TypeToken], known_names: Union[List[str], Tuple[str, ...], set[str]]) -> List[str]:
        matched: List[str] = []
        keys: List[str] = list(known_names)
        for item in parsed_list:
            token: str = item.get('name') or ''
            if not token:
                continue
            candidates: List[str] = [token]
            if '::' in token:
                candidates.append(token.split('::')[-1])
                candidates.append(token.replace('::', '_'))
            if '<' in token:
                base_template = CppTypeParser.extract_template_base(token)
                candidates.append(base_template)
                if '::' in base_template:
                    candidates.append(base_template.split('::')[-1])
                candidates.append(f"{base_template}<...>")
            found: Optional[str] = None
            for c in candidates:
                for kn in keys:
                    if kn == c or kn.endswith("::" + c):
                        found = kn
                        break
                    if '<' in kn and '<' in c:
                        kn_base = CppTypeParser.extract_template_base(kn)
                        c_base = CppTypeParser.extract_template_base(c)
                        if kn_base == c_base:
                            found = kn
                            break
                    elif '<' in kn and c in kn:
                        found = kn
                        break
                if found:
                    break
            if found and found not in matched:
                matched.append(found)
        return matched

    @classmethod
    def extract_all_type_identifiers(cls, type_str: Optional[str]) -> List[TypeToken]:
        out: List[TypeToken] = []
        s: str = cls.tokenize_type(type_str)
        if s.startswith('decltype(') and s.endswith(')'):
            inner_expr = s[9:-1]
            inner_tokens = cls.extract_all_type_identifiers(inner_expr)
            out.extend(inner_tokens)
            out.append({'name': s, 'raw': s})
            return out
        outer, args = cls.parse_template_args(s)
        if outer and cls._is_valid_type_name(outer):
            out.append({'name': outer, 'raw': outer})
        for arg in args:
            arg_tokens = cls.extract_all_type_identifiers(arg)
            out.extend(arg_tokens)
            if not arg_tokens and arg.strip() and cls._is_valid_type_name(arg.strip()):
                out.append({'name': arg.strip(), 'raw': arg.strip()})
        return out

    @staticmethod
    def _is_valid_type_name(type_name: str) -> bool:
        type_name = type_name.strip()
        if not type_name:
            return False
        if re.match(r'^[^\w\s<>:]+$', type_name):
            return False
        if len(type_name) < 2:
            return False
        if re.match(r'^[^\w<]+', type_name):
            return False
        if type_name.count('<') != type_name.count('>'):
            return False
        return True

    @classmethod
    def analyze_type_expr(cls, type_str: Optional[str]) -> TypeAnalysis:
        t: str = cls.tokenize_type(type_str)
        result: TypeAnalysis = {"raw": type_str, "base": t, "is_pointer": False, "is_reference": False, "is_rref": False, "is_array": False}
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
        clean: str = re.sub(r'(\s*[\*\&]+)|\b(const|volatile|mutable)\b', '', t).strip()
        result["base"] = clean
        outer, args = cls.parse_template_args(clean)
        result["template_base"] = outer.split("::")[-1] if outer else outer
        result["template_args"] = args
        return result


__all__ = ["CppTypeParser"]

рородолжай
