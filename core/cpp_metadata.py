#!/usr/bin/env python3
"""
C++ Metadata Object Model for Bidirectional Code ↔ Model Conversion

⚠️  TEMPORARY SOLUTION ⚠️
This is a FALLBACK implementation until we rewrite the project to use clang-uml as core library.
Current approach with JSON parsing + heuristics is BRITTLE and should be replaced with direct 
clang-uml integration for robust template processing and metadata preservation.

TODO: Replace entire approach with clang-uml C++ library integration + Python bindings.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Literal
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

# ===============================================
# CORE C++ CONSTRUCTS MODEL
# ===============================================

class CppStandard(Enum):
    """C++ Standard versions for feature compatibility"""
    CPP98 = "cpp98"
    CPP03 = "cpp03" 
    CPP11 = "cpp11"
    CPP14 = "cpp14"
    CPP17 = "cpp17"
    CPP20 = "cpp20"
    CPP23 = "cpp23"

class KeywordScope(Enum):
    """Where C++ keywords can be applied"""
    CLASS = "class"
    METHOD = "method" 
    FIELD = "field"
    PARAMETER = "parameter"
    GLOBAL = "global"

class TemplateParameterKind(Enum):
    """UML Template Parameter kinds"""
    TYPENAME = "typename"
    VALUE = "value" 
    TEMPLATE = "template"

@dataclass
class SourceLocation:
    """Location in source code for bidirectional mapping"""
    file: str
    line: int
    column: int
    translation_unit: str = ""

@dataclass
class CppKeyword:
    """C++ Keywords (const, static, virtual, final, etc.)"""
    name: str                        # "const", "virtual", "final"
    scope: KeywordScope              # where it applies
    semantic_meaning: str = ""       # для кодогенерации

@dataclass  
class CppAttribute:
    """C++ Attributes [[nodiscard]], [[deprecated]], etc."""
    namespace: str = ""              # "std", "" for standard/custom
    name: str = ""                   # "nodiscard", "deprecated"  
    arguments: List[str] = field(default_factory=list)  # ["message"]
    standard: CppStandard = CppStandard.CPP11
    
    def __str__(self) -> str:
        ns_prefix = f"{self.namespace}::" if self.namespace else ""
        args_str = f"({', '.join(self.arguments)})" if self.arguments else ""
        return f"[[{ns_prefix}{self.name}{args_str}]]"

@dataclass
class CppMacro:
    """C++ Macro definitions and usage"""
    name: str                        # "EXPORT_API", "DEBUG_CLASS"
    definition: str = ""             # "#define EXPORT_API __declspec(dllexport)"
    arguments: List[str] = field(default_factory=list)  # For function-like macros
    source_file: str = ""            # Where defined
    is_function_like: bool = False   # MACRO() vs MACRO

@dataclass
class CppConstraint:
    """C++ Template constraints and static assertions"""  
    type: Literal["requires", "static_assert", "concept"] = "requires"
    expression: str = ""             # "std::is_arithmetic_v<T>"
    message: str = ""                # Error message for static_assert

# ===============================================
# TEMPLATE PROCESSING (DUAL REPRESENTATION)
# ===============================================

@dataclass
class RawTemplateParam:
    """Raw template parameter data from clang-uml (potentially corrupted)"""
    original_text: str               # "type::constant> {}\r\nFMT_TYPE_CONSTANT..."
    kind: str = "argument"           # "argument", "template_type" from clang-uml
    is_corrupted: bool = False       # Contains macro garbage
    corruption_level: int = 0        # 0=clean, 1=minor, 2=major, 3=unusable
    
    def __post_init__(self):
        """Auto-detect corruption level"""
        self.corruption_level = self._detect_corruption()
        self.is_corrupted = self.corruption_level > 0
    
    def _detect_corruption(self) -> int:
        """🚨 HEURISTIC ALERT: Corruption detection heuristics"""
        if not self.original_text or not isinstance(self.original_text, str):
            return 3
            
        text = self.original_text.strip()
        
        # Major corruption indicators
        major_patterns = [
            'FMT_TYPE_CONSTANT',
            'type::constant>',
            r'\{[^}]*\}',  # Macro body remnants
        ]
        
        # Minor corruption indicators  
        minor_patterns = [
            r'\|\|',       # Logical operators
            r'\r\n',       # Line breaks
            r'\n',
        ]
        
        for pattern in major_patterns:
            if re.search(pattern, text):
                return 2
                
        for pattern in minor_patterns:
            if re.search(pattern, text):
                return 1
                
        # Too long is suspicious
        if len(text) > 200:
            return 2
            
        return 0

@dataclass
class UMLTemplateParameter:
    """Clean UML representation for UML Editor"""
    name: str                        # "T", "Allocator" 
    kind: TemplateParameterKind = TemplateParameterKind.TYPENAME
    default_value: Optional[str] = None  # "std::allocator<T>"
    constraints: List[CppConstraint] = field(default_factory=list)
    
    # Hidden metadata for code generation (not visible in UML Editor)
    _cpp_raw_data: Optional[RawTemplateParam] = field(default=None, repr=False)

@dataclass
class CppTemplateData:
    """Dual-layer template representation for bidirectional conversion"""
    # FOR UML EDITOR: Clean, editable UML elements
    uml_parameters: List[UMLTemplateParameter] = field(default_factory=list)
    
    # FOR CODE GENERATION: Complete raw data preservation
    raw_parameters: List[RawTemplateParam] = field(default_factory=list) 
    
    # SYNC METADATA
    sync_strategy: str = "fallback"  # "strict", "fallback", "display_name"
    has_corrupted_data: bool = False
    recovery_notes: List[str] = field(default_factory=list)

# ===============================================
# COMPREHENSIVE C++ METADATA CONTAINER
# ===============================================

@dataclass
class CppMetadata:
    """Complete container for all C++ language constructs"""
    
    # BASIC C++ CONSTRUCTS  
    keywords: List[CppKeyword] = field(default_factory=list)
    attributes: List[CppAttribute] = field(default_factory=list) 
    macros: List[CppMacro] = field(default_factory=list)
    
    # TEMPLATE SYSTEM
    template_data: Optional[CppTemplateData] = None
    
    # CONSTRAINTS & ASSERTIONS
    constraints: List[CppConstraint] = field(default_factory=list)
    
    # UML STEREOTYPES (for UML Editor)
    stereotypes: List[str] = field(default_factory=list)  # ["utility", "entity"]
    
    # BIDIRECTIONAL MAPPING
    source_location: Optional[SourceLocation] = None
    original_data: Dict[str, Any] = field(default_factory=dict)  # Raw JSON from clang-uml
    
    # VERSIONING & COMPATIBILITY
    cpp_standard: CppStandard = CppStandard.CPP17
    compiler_specific: Dict[str, Any] = field(default_factory=dict)  # GCC, Clang, MSVC specific

@dataclass  
class CppElement:
    """Enhanced UML Element with complete C++ metadata"""
    # CORE UML (for UML Editor/EMF)
    uml_element: Any  # UmlElement from existing codebase
    
    # C++ METADATA (for code generation) 
    cpp_metadata: CppMetadata
    
    # BIDIRECTIONAL CONVERSION STATE
    sync_state: str = "clean"        # "clean", "modified", "conflicted"
    last_sync: Optional[str] = None  # timestamp
    
    def is_template(self) -> bool:
        """Check if element has template information"""
        return (self.cpp_metadata.template_data is not None and 
                len(self.cpp_metadata.template_data.uml_parameters) > 0)
    
    def has_corruption(self) -> bool:
        """Check if element has corrupted template data"""
        return (self.cpp_metadata.template_data is not None and
                self.cpp_metadata.template_data.has_corrupted_data)

# ===============================================
# TEMPLATE PROCESSING STRATEGIES
# ===============================================

class TemplateSyncStrategy:
    """🚨 FALLBACK STRATEGIES - Replace with clang-uml integration"""
    
    @staticmethod 
    def cpp_to_uml(raw_param: RawTemplateParam) -> Optional[UMLTemplateParameter]:
        """
        Convert corrupted C++ template param to clean UML representation
        
        ⚠️ WARNING: This uses HEURISTICS and may fail on edge cases!
        TODO: Replace with direct clang AST access via clang-uml library.
        """
        if raw_param.corruption_level >= 3:
            logger.warning(f"Template parameter too corrupted to recover: {raw_param.original_text[:50]}...")
            return None
            
        # 🚨 HEURISTIC: Try to extract clean parameter name
        clean_name = TemplateSyncStrategy._extract_clean_name(raw_param.original_text)
        if not clean_name:
            return None
            
        # 🚨 HEURISTIC: Guess parameter kind  
        param_kind = TemplateSyncStrategy._guess_parameter_kind(raw_param)
        
        return UMLTemplateParameter(
            name=clean_name,
            kind=param_kind,
            _cpp_raw_data=raw_param  # Preserve raw data for code generation
        )
    
    @staticmethod 
    def _extract_clean_name(corrupted_text: str) -> Optional[str]:
        """🚨 HEURISTIC: Extract clean parameter name from corrupted text"""
        if not corrupted_text:
            return None
            
        text = corrupted_text.strip()
        
        # Remove obvious corruption
        text = re.split(r'[\r\n]', text)[0].strip()  # Take first line
        
        # If already clean, return as-is
        if re.match(r'^[A-Za-z_][A-Za-z0-9_:<>, ]*$', text) and len(text) < 100:
            return text
            
        # Try to extract meaningful parts (stop before corruption indicators)
        clean_patterns = [
            r'^(std::[A-Za-z_][A-Za-z0-9_:]*?)(?:[^A-Za-z0-9_:.]|$)',  # std types, stop before corruption
            r'^(typename\s+[A-Za-z_][A-Za-z0-9_:]*?)(?:[^A-Za-z0-9_:.]|$)',  # typename declarations
            r'^([A-Za-z_][A-Za-z0-9_:]*?)(?:[^A-Za-z0-9_:.]|$)',       # Names, stop before corruption
        ]
        
        for pattern in clean_patterns:
            match = re.match(pattern, text)
            if match:
                return match.group(1)
        
        # Last resort - take everything before first suspicious character
        clean_part = re.split(r'[|{}\r\n]', text)[0].strip()
        if clean_part and len(clean_part) > 0:
            return clean_part
            
        return None
    
    @staticmethod 
    def _guess_parameter_kind(raw_param: RawTemplateParam) -> TemplateParameterKind:
        """🚨 HEURISTIC: Guess template parameter kind"""
        text = raw_param.original_text.lower()
        
        # Value parameters often have numeric or literal patterns
        if re.search(r'\b(int|size_t|bool|true|false|\d+)\b', text):
            return TemplateParameterKind.VALUE
            
        # Template template parameters
        if 'template' in text:
            return TemplateParameterKind.TEMPLATE
            
        # Default to typename
        return TemplateParameterKind.TYPENAME
    
    @staticmethod
    def uml_to_cpp(uml_param: UMLTemplateParameter) -> str:
        """Generate C++ code from UML template parameter"""
        if uml_param._cpp_raw_data and not uml_param._cpp_raw_data.is_corrupted:
            # Use original if available and clean
            return uml_param._cpp_raw_data.original_text
            
        # Generate from UML data
        kind_prefix = {
            TemplateParameterKind.TYPENAME: "typename",
            TemplateParameterKind.VALUE: "",  # Inferred from type
            TemplateParameterKind.TEMPLATE: "template<class>"
        }
        
        prefix = kind_prefix.get(uml_param.kind, "typename")
        name = uml_param.name
        default = f" = {uml_param.default_value}" if uml_param.default_value else ""
        
        return f"{prefix} {name}{default}".strip()

# ===============================================
# C++ PROFILES & TYPE LIBRARIES
# ===============================================

@dataclass
class CppTypeProfile:
    """Type-specific rules for C++ library types (std, boost, etc.)"""
    namespace: str                   # "std", "boost"
    type_name: str                   # "vector", "shared_ptr"
    
    # Template argument roles
    argument_roles: Dict[int, str] = field(default_factory=dict)  # {0: "element", 1: "allocator"}
    
    # UML representation rules
    multiplicity_rules: Dict[str, str] = field(default_factory=dict)  # {"element": "*"}
    aggregation_rules: Dict[str, str] = field(default_factory=dict)   # {"element": "none"}
    
    # Code generation rules
    include_headers: List[str] = field(default_factory=list)     # ["<vector>", "<memory>"]
    namespace_aliases: Dict[str, str] = field(default_factory=dict)  # {"std": "std"}

class CppProfileRegistry:
    """Registry of C++ type profiles for smart UML generation"""
    
    def __init__(self):
        self.profiles: Dict[str, CppTypeProfile] = {}
        self._load_standard_profiles()
    
    def _load_standard_profiles(self):
        """Load standard library profiles"""
        # STL Containers
        self.profiles["std::vector"] = CppTypeProfile(
            namespace="std",
            type_name="vector", 
            argument_roles={0: "element", 1: "allocator"},
            multiplicity_rules={"element": "*"},
            aggregation_rules={"element": "none"},
            include_headers=["<vector>"]
        )
        
        self.profiles["std::map"] = CppTypeProfile(
            namespace="std",
            type_name="map",
            argument_roles={0: "key", 1: "value", 2: "compare", 3: "allocator"}, 
            multiplicity_rules={"key": "*", "value": "*"},
            aggregation_rules={"key": "none", "value": "none"},
            include_headers=["<map>"]
        )
        
        # Smart Pointers  
        self.profiles["std::unique_ptr"] = CppTypeProfile(
            namespace="std",
            type_name="unique_ptr",
            argument_roles={0: "element", 1: "deleter"},
            multiplicity_rules={"element": "1"},
            aggregation_rules={"element": "composite"},
            include_headers=["<memory>"]
        )
        
        self.profiles["std::shared_ptr"] = CppTypeProfile(
            namespace="std", 
            type_name="shared_ptr",
            argument_roles={0: "element"},
            multiplicity_rules={"element": "1"},
            aggregation_rules={"element": "shared"}, 
            include_headers=["<memory>"]
        )
    
    def get_profile(self, type_name: str) -> Optional[CppTypeProfile]:
        """Get profile for a type"""
        return self.profiles.get(type_name)
    
    def register_profile(self, profile: CppTypeProfile):
        """Register custom profile"""
        key = f"{profile.namespace}::{profile.type_name}" if profile.namespace else profile.type_name
        self.profiles[key] = profile

# ===============================================
# BIDIRECTIONAL CONVERSION INTERFACES  
# ===============================================

class BidirectionalConverter:
    """Interface for bidirectional C++ ↔ UML conversion"""
    
    def __init__(self, profile_registry: Optional[CppProfileRegistry] = None):
        self.profiles = profile_registry or CppProfileRegistry()
        
    def parse_cpp_element(self, raw_data: Dict[str, Any]) -> CppElement:
        """
        Parse C++ element from clang-uml JSON data
        
        ⚠️ TEMPORARY FALLBACK: This processes corrupted JSON data with heuristics.
        TODO: Replace with direct clang-uml C++ library integration.
        """
        # Extract basic metadata  
        cpp_metadata = self._extract_cpp_metadata(raw_data)
        
        # Process templates with fallback strategies
        if raw_data.get('template_parameters') or raw_data.get('is_template'):
            cpp_metadata.template_data = self._process_templates_with_fallback(raw_data)
        
        # Create UML element (existing codebase integration)
        uml_element = self._create_uml_element(raw_data)
        
        return CppElement(
            uml_element=uml_element,
            cpp_metadata=cpp_metadata,
            sync_state="clean"
        )
    
    def generate_cpp_code(self, cpp_element: CppElement) -> str:
        """Generate C++ code from CppElement"""
        # This is where bidirectional magic happens
        # Use preserved metadata to reconstruct original C++
        
        code_parts = []
        
        # Generate template declaration
        if cpp_element.is_template():
            template_code = self._generate_template_declaration(cpp_element.cpp_metadata.template_data)
            if template_code:  # Only add if not empty
                code_parts.append(template_code)
        
        # Generate class/struct with attributes and keywords
        class_code = self._generate_class_declaration(cpp_element)
        if class_code:  # Only add if not None
            code_parts.append(class_code)
        
        return "\n".join(code_parts) if code_parts else "// No code generated"
    
    def _extract_cpp_metadata(self, raw_data: Dict[str, Any]) -> CppMetadata:
        """Extract C++ metadata from raw JSON"""
        # 🚨 FALLBACK IMPLEMENTATION - Replace with clang-uml integration
        metadata = CppMetadata()
        metadata.original_data = raw_data.copy()
        
        # Extract source location
        if source_loc := raw_data.get('source_location'):
            metadata.source_location = SourceLocation(
                file=source_loc.get('file', ''),
                line=source_loc.get('line', 0), 
                column=source_loc.get('column', 0),
                translation_unit=source_loc.get('translation_unit', '')
            )
        
        return metadata
    
    def _process_templates_with_fallback(self, raw_data: Dict[str, Any]) -> CppTemplateData:
        """Process template data with multiple fallback strategies"""
        template_data = CppTemplateData()
        
        # Strategy 1: Try to parse template_parameters
        raw_params = raw_data.get('template_parameters', [])
        for raw_param_data in raw_params:
            # Handle both dict and string formats
            if isinstance(raw_param_data, dict):
                param_text = str(raw_param_data.get('type', '') or raw_param_data.get('name', ''))
                param_kind = raw_param_data.get('kind', 'argument')
            elif isinstance(raw_param_data, str):
                param_text = raw_param_data
                param_kind = 'argument'
            else:
                continue  # Skip invalid data
                
            raw_param = RawTemplateParam(
                original_text=param_text,
                kind=param_kind
            )
            template_data.raw_parameters.append(raw_param)
            
            # Try to convert to clean UML parameter
            uml_param = TemplateSyncStrategy.cpp_to_uml(raw_param)
            if uml_param:
                template_data.uml_parameters.append(uml_param)
            else:
                template_data.has_corrupted_data = True
                template_data.recovery_notes.append(f"Failed to recover parameter: {raw_param.original_text[:50]}...")
        
        # Update corruption status based on raw parameters
        if any(param.is_corrupted for param in template_data.raw_parameters):
            template_data.has_corrupted_data = True
        
        # Strategy 2: Fallback to display_name if all parameters are corrupted
        if not template_data.uml_parameters and raw_data.get('display_name'):
            template_data.sync_strategy = "display_name"
            # Try to extract template info from display_name
            # This is last resort fallback
        
        return template_data
    
    def _create_uml_element(self, raw_data: Dict[str, Any]) -> Any:
        """Create UML element using existing codebase"""
        # Integration point with existing UmlElement creation
        # This would use the existing builder logic
        pass
    
    def _generate_template_declaration(self, template_data: CppTemplateData) -> str:
        """Generate C++ template declaration"""
        if not template_data.uml_parameters:
            return ""
            
        param_strings = []
        for param in template_data.uml_parameters:
            param_str = TemplateSyncStrategy.uml_to_cpp(param)
            param_strings.append(param_str)
        
        return f"template<{', '.join(param_strings)}>"
    
    def _generate_class_declaration(self, cpp_element: CppElement) -> str:
        """Generate C++ class declaration with all metadata"""
        # Generate class with keywords, attributes, etc.
        # This is where we reconstruct full C++ syntax
        
        # 🚨 FALLBACK IMPLEMENTATION - Basic class generation
        class_name = str(cpp_element.uml_element.name).split("::")[-1] if cpp_element.uml_element else "UnknownClass"
        
        # Add attributes
        attributes_str = ""
        if cpp_element.cpp_metadata.attributes:
            attr_strs = [str(attr) for attr in cpp_element.cpp_metadata.attributes]
            attributes_str = " ".join(attr_strs) + "\n"
        
        # Add keywords  
        keywords_str = ""
        if cpp_element.cpp_metadata.keywords:
            class_keywords = [kw.name for kw in cpp_element.cpp_metadata.keywords if kw.scope == KeywordScope.CLASS]
            keywords_str = " ".join(class_keywords) + " " if class_keywords else ""
        
        return f"{attributes_str}{keywords_str}class {class_name} {{\n    // Generated from UML\n}};"

# ===============================================
# FALLBACK NOTES & MIGRATION PATH
# ===============================================

"""
🚨 IMPORTANT MIGRATION NOTES:

This entire module is a TEMPORARY FALLBACK solution until we rewrite the project 
to use clang-uml as a core C++ library instead of JSON parsing.

CURRENT PROBLEMS:
- Heuristic-based template parameter parsing is brittle
- JSON data loss prevents perfect bidirectional conversion  
- Complex maintenance overhead for edge cases

MIGRATION PATH:
1. Research clang-uml C++ library integration options
2. Create Python bindings (pybind11) for clang-uml
3. Replace this entire fallback system with direct AST access
4. Implement true bidirectional conversion with no data loss

TIMELINE:
- Fallback solution: 2-4 weeks (current sprint)
- clang-uml integration: 1-3 months (future sprint)
- Full migration: 3-6 months (long term)

FILES TO REPLACE DURING MIGRATION:
- This entire module (core/cpp_metadata.py)
- build/cpp/details.py (template processing)
- gen/xmi/template_utils.py (heuristics)
- All template-related heuristics and fallbacks
"""
