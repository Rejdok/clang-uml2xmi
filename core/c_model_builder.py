#!/usr/bin/env python3
"""
C Language Model Builder with Method Binding - INTEGRATED WITH XMI PIPELINE

Builds UML models from C source code with intelligent function-to-struct binding.
Functions are bound to structs based on first argument type.

✅ PRODUCTION IMPLEMENTATION integrated with main XMI pipeline
Outputs UmlModel compatible with XmiGenerator and existing EMF compliance.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
import logging
import re
import sys
from pathlib import Path

from core import UmlModel, UmlElement, UmlMember, UmlOperation, ElementName, XmiId, ClangMetadata
from uml_types import ElementKind, Visibility
from utils.ids import stable_id

logger = logging.getLogger(__name__)

# ===============================================
# C LANGUAGE CONSTRUCTS MODEL
# ===============================================

@dataclass
class CParameter:
    """C function parameter"""
    name: str
    type: str                        # "Point*", "const char*", "int"
    is_const: bool = False
    is_pointer: bool = False
    is_array: bool = False
    array_size: Optional[str] = None  # For "char buffer[256]"

@dataclass
class CFunction:
    """C function definition"""
    name: str
    return_type: str
    parameters: List[CParameter] = field(default_factory=list)
    is_static: bool = False
    is_inline: bool = False
    source_file: str = ""
    line_number: int = 0
    
    # Comments and documentation
    comments: List[str] = field(default_factory=list)
    brief_description: str = ""
    
    def get_first_param_type(self) -> Optional[str]:
        """Get clean type of first parameter for binding"""
        if not self.parameters:
            return None
            
        first_param = self.parameters[0]
        # Clean type: "const Point*" → "Point"
        clean_type = first_param.type
        clean_type = re.sub(r'\bconst\b', '', clean_type).strip()
        clean_type = re.sub(r'[*&\[\]]+', '', clean_type).strip()
        
        return clean_type if clean_type else None

@dataclass
class CStruct:
    """C struct definition"""
    name: str
    fields: List[CParameter] = field(default_factory=list)  # Reuse CParameter for fields
    source_file: str = ""
    line_number: int = 0
    
    # Bound methods (functions bound by first argument type)
    bound_methods: List[CFunction] = field(default_factory=list)
    
    # Comments and documentation
    comments: List[str] = field(default_factory=list)
    brief_description: str = ""
    
    def add_bound_method(self, function: CFunction):
        """Add function bound to this struct"""
        self.bound_methods.append(function)
        logger.debug(f"Bound function {function.name} to struct {self.name}")

# ===============================================
# METHOD BINDING ENGINE
# ===============================================

class CMethodBinder:
    """Binds C functions to structs based on first argument type"""
    
    def __init__(self):
        self.binding_stats = {
            'total_functions': 0,
            'bound_functions': 0,
            'unbound_functions': 0,
            'binding_conflicts': 0
        }
    
    def bind_functions_to_structs(self, 
                                 functions: List[CFunction], 
                                 structs: Dict[str, CStruct]) -> Dict[str, List[CFunction]]:
        """
        Bind functions to structs based on first argument type
        
        Returns unbound functions that couldn't be bound to any struct
        """
        unbound_functions = []
        
        self.binding_stats['total_functions'] = len(functions)
        
        for function in functions:
            bound = self._try_bind_function(function, structs)
            
            if bound:
                self.binding_stats['bound_functions'] += 1
            else:
                unbound_functions.append(function)
                self.binding_stats['unbound_functions'] += 1
        
        logger.info(f"Method binding stats: {self.binding_stats}")
        return {'unbound': unbound_functions}
    
    def _try_bind_function(self, function: CFunction, structs: Dict[str, CStruct]) -> bool:
        """Try to bind single function to appropriate struct"""
        
        first_param_type = function.get_first_param_type()
        if not first_param_type:
            return False  # No parameters to bind by
        
        # Skip primitive types
        if self._is_primitive_type(first_param_type):
            return False
            
        # Find matching struct
        target_struct = structs.get(first_param_type)
        if target_struct:
            target_struct.add_bound_method(function)
            return True
            
        return False
    
    def _is_primitive_type(self, type_name: str) -> bool:
        """Check if type is C primitive (should not bind methods to)"""
        c_primitives = {
            'char', 'short', 'int', 'long', 'float', 'double',
            'signed', 'unsigned', 'void', 'size_t', 'ssize_t',
            '_Bool', 'bool'  # C99/C++ bool
        }
        
        # Remove qualifiers and check
        clean_type = re.sub(r'\b(signed|unsigned)\b', '', type_name).strip()
        return clean_type in c_primitives

# ===============================================
# C SOURCE CODE PARSER  
# ===============================================

class CSourceParser:
    """Lightweight C source code parser for struct and function extraction"""
    
    def __init__(self):
        self.structs: Dict[str, CStruct] = {}
        self.functions: List[CFunction] = []
    
    def parse_c_file(self, file_path: str) -> Dict[str, Any]:
        """Parse C source file and extract structs, functions"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return {}
        
        # Parse different C constructs
        self._parse_structs(content, file_path)
        self._parse_functions(content, file_path) 
        
        return {
            'structs': self.structs,
            'functions': self.functions,
            'source_file': file_path
        }
    
    def _parse_structs(self, content: str, file_path: str):
        """Parse struct definitions with regex"""
        
        # Match: typedef struct { ... } StructName; or struct StructName { ... };
        struct_patterns = [
            r'typedef\s+struct\s*\{([^}]*)\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*;',
            r'struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{([^}]*)\}\s*;'
        ]
        
        for pattern in struct_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                if len(match.groups()) == 2:
                    if 'typedef' in pattern:
                        struct_body, struct_name = match.groups()
                    else:
                        struct_name, struct_body = match.groups()
                    
                    # Parse struct fields
                    fields = self._parse_struct_fields(struct_body)
                    
                    # Get line number
                    line_num = content[:match.start()].count('\n') + 1
                    
                    c_struct = CStruct(
                        name=struct_name,
                        fields=fields,
                        source_file=file_path,
                        line_number=line_num
                    )
                    
                    self.structs[struct_name] = c_struct
                    logger.debug(f"Parsed struct {struct_name} with {len(fields)} fields")
    
    def _parse_struct_fields(self, struct_body: str) -> List[CParameter]:
        """Parse fields inside struct body"""
        fields = []
        
        # Simple field pattern: type name;
        field_pattern = r'([A-Za-z_][A-Za-z0-9_\s\*]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*;'
        
        for match in re.finditer(field_pattern, struct_body):
            field_type, field_name = match.groups()
            field_type = field_type.strip()
            
            # Detect array fields
            array_match = re.search(r'\[([^\]]*)\]', struct_body[match.end()-20:match.end()])
            array_size = array_match.group(1) if array_match else None
            
            field = CParameter(
                name=field_name,
                type=field_type,
                is_const='const' in field_type,
                is_pointer='*' in field_type,
                is_array=array_size is not None,
                array_size=array_size
            )
            
            fields.append(field)
        
        return fields
    
    def _parse_functions(self, content: str, file_path: str):
        """Parse function definitions with regex"""
        
        # Function pattern: return_type function_name(parameters) { or ;
        # Handle both declarations and definitions, including multiline
        func_pattern = r'^\s*([A-Za-z_][A-Za-z0-9_\s\*]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*[;{]'
        
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            return_type, func_name, params_str = match.groups()
            return_type = return_type.strip()
            
            # Skip if this looks like a struct definition or other construct
            if 'struct' in return_type or 'typedef' in return_type:
                continue
            
            # Parse parameters
            parameters = self._parse_function_parameters(params_str)
            
            # Get line number
            line_num = content[:match.start()].count('\n') + 1
            
            c_function = CFunction(
                name=func_name,
                return_type=return_type,
                parameters=parameters,
                is_static='static' in return_type,
                is_inline='inline' in return_type,
                source_file=file_path,
                line_number=line_num
            )
            
            self.functions.append(c_function)
            logger.debug(f"Parsed function {func_name} with {len(parameters)} parameters")
    
    def _parse_function_parameters(self, params_str: str) -> List[CParameter]:
        """Parse function parameter list"""
        parameters = []
        
        if not params_str.strip() or params_str.strip() == 'void':
            return parameters
        
        # Split parameters by comma (simple approach)
        param_parts = [p.strip() for p in params_str.split(',')]
        
        for param_part in param_parts:
            if not param_part:
                continue
                
            # Extract type and name: "const Point* p" → type="const Point*", name="p"
            param_match = re.match(r'(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', param_part)
            
            if param_match:
                param_type, param_name = param_match.groups()
                param_type = param_type.strip()
                
                parameter = CParameter(
                    name=param_name,
                    type=param_type,
                    is_const='const' in param_type,
                    is_pointer='*' in param_type,
                    is_array='[]' in param_part
                )
                
                parameters.append(parameter)
        
        return parameters

# ===============================================
# C MODEL BUILDER WITH XMI INTEGRATION
# ===============================================

class CModelBuilder:
    """Build UML model from C source code - INTEGRATED WITH XMI PIPELINE"""
    
    def __init__(self):
        self.parser = CSourceParser()
        self.binder = CMethodBinder()
        self.binding_stats = {}
    
    def build_from_c_sources(self, c_files: List[str]) -> UmlModel:
        """
        Build UmlModel from C source files - COMPATIBLE WITH XmiGenerator
        
        Process:
        1. Parse all C files (structs, functions)
        2. Bind functions to structs by first argument type
        3. Convert to UmlModel format (same as C++ pipeline)
        4. Return UmlModel for XmiGenerator
        """
        logger.info(f"🚀 Building C UML model from {len(c_files)} source files")
        
        # Phase 1: Parse all C files
        all_structs = {}
        all_functions = []
        
        for file_path in c_files:
            logger.info(f"Parsing C file: {file_path}")
            parsed_data = self.parser.parse_c_file(file_path)
            
            # Collect all constructs
            all_structs.update(parsed_data.get('structs', {}))
            all_functions.extend(parsed_data.get('functions', []))
        
        logger.info(f"Parsed: {len(all_structs)} structs, {len(all_functions)} functions")
        
        # Phase 2: Bind functions to structs
        unbound_data = self.binder.bind_functions_to_structs(all_functions, all_structs)
        self.binding_stats = self.binder.binding_stats.copy()
        
        # Phase 3: Convert to UmlModel (compatible with XmiGenerator)
        uml_model = self._build_uml_model(all_structs, unbound_data['unbound'])
        
        logger.info(f"✅ Generated UML model with {len(uml_model.elements)} elements")
        return uml_model
    
    def _build_uml_model(self, 
                        structs: Dict[str, CStruct],
                        unbound_functions: List[CFunction]) -> UmlModel:
        """Convert C constructs to UmlModel compatible with XmiGenerator"""
        
        elements = {}
        name_to_xmi = {}
        
        # Convert structs to UML classes
        for struct_name, c_struct in structs.items():
            uml_element = self._struct_to_uml_class(c_struct)
            elements[uml_element.xmi] = uml_element
            name_to_xmi[struct_name] = uml_element.xmi
        
        # Convert unbound functions to UML operations (in a utility class)
        if unbound_functions:
            utility_class = self._create_utility_class(unbound_functions)
            elements[utility_class.xmi] = utility_class
            name_to_xmi['UtilityFunctions'] = utility_class.xmi
        
        return UmlModel(
            elements=elements,
            associations=[],  # Future: Could detect associations from struct field types
            dependencies=[],   # Future: Could detect dependencies from #include statements  
            generalizations=[], # Not applicable for C language
            name_to_xmi=name_to_xmi
        )
    
    def _struct_to_uml_class(self, c_struct: CStruct) -> UmlElement:
        """Convert C struct to UML class with bound methods"""
        
        xmi_id = XmiId(stable_id(f"c_struct:{c_struct.name}"))
        
        # Convert fields to UML members (proper UmlMember objects)
        members = []
        for field in c_struct.fields:
            uml_member = UmlMember(
                name=field.name,
                type_repr=field.type,  # XmiGenerator expects this attribute
                visibility=Visibility.PUBLIC,  # C struct fields are public
                is_static=False
            )
            members.append(uml_member)
        
        # Convert bound methods to UML operations (proper UmlOperation objects)
        operations = []
        for method in c_struct.bound_methods:
            # Convert C function parameters to UML operation parameters
            uml_params = []
            for param in method.parameters:
                uml_params.append((param.name, param.type))
            
            uml_operation = UmlOperation(
                name=method.name,
                return_type=method.return_type,
                parameters=uml_params,
                visibility=Visibility.PUBLIC,  # C functions are public by default
                is_static=method.is_static,
                is_const=False,  # C doesn't have const methods
                is_virtual=False  # C doesn't have virtual methods
            )
            operations.append(uml_operation)
        
        clang_metadata = ClangMetadata(
            qualified_name=c_struct.name,
            display_name=c_struct.name,
            name=c_struct.name,
            kind="struct",
            is_struct=True
        )
        
        return UmlElement(
            xmi=xmi_id,
            name=ElementName(c_struct.name),
            kind=ElementKind.CLASS,  # Treat C structs as UML classes
            members=members,
            clang=clang_metadata,
            used_types=frozenset(),
            underlying=None,
            operations=operations,
            templates=[],  # C doesn't have templates
            literals=[],
            namespace=None,
            original_data={'c_struct': c_struct},
            is_stub=False,
            instantiation_of=None,
            instantiation_args=[]
        )
    
    def _create_utility_class(self, unbound_functions: List[CFunction]) -> UmlElement:
        """Create utility class for unbound C functions"""
        
        xmi_id = XmiId(stable_id("c_utility_functions"))
        
        operations = []
        for function in unbound_functions:
            # Convert C function parameters to UML operation parameters
            uml_params = []
            for param in function.parameters:
                uml_params.append((param.name, param.type))
            
            uml_operation = UmlOperation(
                name=function.name,
                return_type=function.return_type,
                parameters=uml_params,
                visibility=Visibility.PUBLIC,
                is_static=False,  # Utility functions are not static
                is_const=False,
                is_virtual=False
            )
            operations.append(uml_operation)
        
        clang_metadata = ClangMetadata(
            qualified_name="UtilityFunctions",
            display_name="C Utility Functions",
            name="UtilityFunctions",
            kind="utility"
        )
        
        return UmlElement(
            xmi=xmi_id,
            name=ElementName("UtilityFunctions"),
            kind=ElementKind.CLASS,
            members=[],
            clang=clang_metadata,
            used_types=frozenset(),
            underlying=None,
            operations=operations,
            templates=[],
            literals=[],
            namespace=None,
            original_data={'unbound_functions': unbound_functions},
            is_stub=False,
            instantiation_of=None,
            instantiation_args=[]
        )
    
    def get_binding_report(self) -> Dict[str, Any]:
        """Get detailed report of method binding results"""
        return {
            'binding_stats': self.binding_stats,
            'structs_with_methods': len([s for s in self.parser.structs.values() if s.bound_methods]),
            'total_structs': len(self.parser.structs),
            'binding_ratio': self.binding_stats.get('bound_functions', 0) / max(self.binding_stats.get('total_functions', 1), 1)
        }

# ===============================================
# MAIN C PROCESSING API FOR XMI PIPELINE
# ===============================================

def build_c_uml_model(source_files: List[str]) -> UmlModel:
    """
    Main API for building UML model from C source files
    
    Returns UmlModel compatible with XmiGenerator and existing XMI pipeline
    ✅ Integrated with main project architecture
    """
    
    logger.info("🚀 C MODEL BUILDER - Integrated with XMI pipeline")
    
    builder = CModelBuilder()
    uml_model = builder.build_from_c_sources(source_files)
    
    # Log binding statistics
    binding_report = builder.get_binding_report()
    logger.info(f"📊 C Binding stats: {binding_report['binding_stats']}")
    
    return uml_model

if __name__ == "__main__":
    # Example usage
    print("✅ C Model Builder - Integrated with XMI Pipeline")
    print("Use via main cpp2uml.py: python cpp2uml.py --language c source.c output.uml output.notation")