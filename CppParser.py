
import re
from typing import Dict, List, Optional, Tuple, Any, Union, Literal

from uml_types import (
    TypeToken, TypeAnalysis, TypeAnalysisResult,
    TypeString, TemplateArgs, TypeName
)

class CppTypeParser:
    _CONTAINER_KEYWORDS: frozenset[str] = frozenset({"vector", "list", "deque", "set", "unordered_set", "map", "unordered_map", "array", "span", "tuple"})
    _SMART_PTRS: frozenset[str] = frozenset({"unique_ptr", "shared_ptr", "weak_ptr", "scoped_ptr", "intrusive_ptr"})

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
        return s

    @staticmethod
    def parse_template_args(type_str: str) -> Tuple[str, List[str]]:
        """Enhanced template argument parsing with better handling of complex templates."""
        s: str = (type_str or "").strip()
        if not s:
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
                                args.append(cur.strip())
                            i += 1
                            break
                        else:
                            cur += c
                    elif c == ',' and depth == 1:
                        args.append(cur.strip())
                        cur = ''
                    else:
                        cur += c
                    i += 1
                
                # Clean up any remaining content
                if cur.strip():
                    args.append(cur.strip())
                
                return (outer, [a.strip() for a in args if a.strip()])
            i += 1
        return (s, [])

    @staticmethod
    def extract_template_base(type_str: str) -> str:
        """Extract the base template name without arguments."""
        base, _ = CppTypeParser.parse_template_args(type_str)
        return base

    @staticmethod
    def is_template_instance(type_str: str) -> bool:
        """Check if a type string represents a template instance."""
        return '<' in type_str and '>' in type_str

    @staticmethod
    def normalize_template_name(type_str: str) -> str:
        """Normalize template name by removing template arguments for comparison."""
        base, args = CppTypeParser.parse_template_args(type_str)
        if args:
            return f"{base}<...>"
        return base

    @staticmethod
    def extract_template_parameters(type_str: str) -> List[str]:
        """Extract template parameter types from a template instantiation."""
        _, args = CppTypeParser.parse_template_args(type_str)
        return args

    @staticmethod
    def is_specialization_of(base_template: str, specialized_type: str) -> bool:
        """Check if specialized_type is a specialization of base_template."""
        if not CppTypeParser.is_template_instance(specialized_type):
            return False
        
        spec_base, _ = CppTypeParser.parse_template_args(specialized_type)
        return spec_base == base_template

    @classmethod
    def extract_all_type_identifiers(cls, type_str: Optional[str]) -> List[TypeToken]:
        """Enhanced type identifier extraction with better template handling."""
        out: List[TypeToken] = []
        s: str = cls.tokenize_type(type_str)
        outer: str
        args: List[str]
        outer, args = cls.parse_template_args(s)
        
        if outer:
            out.append({'name': outer, 'raw': outer})
        
        # Process template arguments more thoroughly
        for arg in args:
            # Skip primitive types and simple identifiers
            if arg in ['int', 'float', 'double', 'char', 'bool', 'void', 'string', 'std::string']:
                continue
            
            # Extract type identifiers from complex template arguments
            arg_tokens = cls.extract_all_type_identifiers(arg)
            out.extend(arg_tokens)
        
        return out

    @staticmethod
    def match_known_types_from_parsed(parsed_list: List[TypeToken], known_names: Union[List[str], Tuple[str, ...], set[str]]) -> List[str]:
        """Enhanced type matching with improved template handling."""
        matched: List[str] = []
        keys: List[str] = list(known_names)
        
        for item in parsed_list:
            token: str = item.get('name') or ''
            if not token:
                continue
            
            candidates: List[str] = [token]
            
            # Add namespace variants
            if '::' in token:
                candidates.append(token.split('::')[-1])
                # Also try without namespace
                candidates.append(token.replace('::', '_'))
            
            # Handle template types
            if '<' in token:
                # Add base template name
                base_template = CppTypeParser.extract_template_base(token)
                candidates.append(base_template)
                
                # Add simple name of base template
                if '::' in base_template:
                    candidates.append(base_template.split('::')[-1])
                
                # Add template with placeholder arguments
                candidates.append(f"{base_template}<...>")
            
            # Try to find matches
            found: Optional[str] = None
            for c in candidates:
                for kn in keys:
                    # Exact match
                    if kn == c:
                        found = kn
                        break
                    # Namespace suffix match
                    elif kn.endswith("::" + c):
                        found = kn
                        break
                    # Template specialization match
                    elif '<' in kn and '<' in c:
                        kn_base = CppTypeParser.extract_template_base(kn)
                        c_base = CppTypeParser.extract_template_base(c)
                        if kn_base == c_base:
                            found = kn
                            break
                    # Fuzzy template matching
                    elif '<' in kn and c in kn:
                        found = kn
                        break
                if found:
                    break
            
            if found and found not in matched:
                matched.append(found)
        
        return matched

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
        outer: str
        args: List[str]
        outer, args = cls.parse_template_args(clean)
        result["template_base"] = outer.split("::")[-1] if outer else outer
        result["template_args"] = args
        return result

