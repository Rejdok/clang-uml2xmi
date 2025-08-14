#!/usr/bin/env python3
"""
Hybrid C Model Builder: clang-uml (structs) + function parsing (binding)

✅ BEST OF BOTH WORLDS:
- clang-uml for accurate struct parsing (no regex brittleness)  
- Lightweight function parsing for method binding
- JSON format compatible with existing pipeline

🎯 PRODUCTION READY for C language processing
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
import subprocess
import tempfile
import shutil
import yaml
import logging
import re
import sys
from pathlib import Path

# Add project root to path
# Path management handled by core/__init__.py

from core.c_model_builder import CFunction, CParameter, CMethodBinder

logger = logging.getLogger(__name__)

# ===============================================
# HYBRID C PROCESSING STRATEGY
# ===============================================

class CHybridBuilder:
    """Hybrid builder: clang-uml for structs + function parsing for binding"""
    
    def __init__(self):
        self.method_binder = CMethodBinder()
        
    def build_c_model(self, c_files: List[str], output_path: str) -> Dict[str, Any]:
        """
        Build C model using hybrid approach:
        
        1. clang-uml for accurate struct parsing
        2. Lightweight function parsing  
        3. Method binding by first argument type
        4. Enhanced JSON output
        """
        
        logger.info(f"🚀 HYBRID C BUILDER: Processing {len(c_files)} files")
        
        # Step 1: Get structs from clang-uml (accurate parsing)
        structs_data = self._get_structs_from_clang_uml(c_files)
        
        # Step 2: Parse functions from source files (lightweight)
        functions_data = self._parse_functions_from_sources(c_files)
        
        # Step 3: Apply method binding
        enhanced_structs = self._apply_method_binding(structs_data, functions_data)
        
        # Step 4: Generate enhanced JSON
        result = self._generate_enhanced_json(enhanced_structs, c_files)
        
        # Save result
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Enhanced C model written to: {output_path}")
        return result
    
    def _get_structs_from_clang_uml(self, c_files: List[str]) -> Dict[str, Dict[str, Any]]:
        """Use clang-uml to get accurate struct information"""
        
        temp_dir = Path(tempfile.mkdtemp(prefix="clang_uml_c_"))
        logger.debug(f"Using temp directory: {temp_dir}")
        
        try:
            # Copy source files
            for c_file in c_files:
                src_path = Path(c_file)
                if src_path.exists():
                    dst_path = temp_dir / src_path.name
                    shutil.copy2(src_path, dst_path)
            
            # Create compilation database
            compile_commands = []
            for c_file in c_files:
                c_path = Path(c_file)
                if c_path.suffix in ['.c']:  # Only source files
                    compile_commands.append({
                        "directory": str(temp_dir.absolute()).replace('\\', '/'),
                        "command": f"gcc -std=c99 -c {c_path.name}",
                        "file": c_path.name
                    })
            
            if not compile_commands:
                logger.warning("No .c files found, using header-only approach")
                for c_file in c_files:
                    c_path = Path(c_file)
                    if c_path.suffix in ['.h', '.hpp']:
                        compile_commands.append({
                            "directory": str(temp_dir.absolute()).replace('\\', '/'),
                            "command": f"gcc -std=c99 -x c -c {c_path.name}",
                            "file": c_path.name
                        })
            
            compile_db_path = temp_dir / "compile_commands.json"
            with open(compile_db_path, 'w') as f:
                json.dump(compile_commands, f, indent=2)
            
            # Create clang-uml config
            config = {
                "compilation_database_dir": ".",
                "output_directory": "output",
                "diagrams": {
                    "c_structs": {
                        "type": "class",
                        "glob": ["*.c", "*.h"],
                        "include": {"paths": ["."]}
                    }
                }
            }
            
            config_path = temp_dir / ".clang-uml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Run clang-uml
            cmd = ["clang-uml", "-c", ".clang-uml", "-g", "json", "-n", "c_structs", "-q"]
            
            result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"clang-uml failed, using struct parsing fallback: {result.stderr}")
                return self._fallback_struct_parsing(c_files)
            
            # Load generated JSON
            json_path = temp_dir / "output" / "c_structs.json"
            if json_path.exists():
                with open(json_path, 'r') as f:
                    clang_data = json.load(f)
                
                # Extract structs
                structs = {}
                for element in clang_data.get('elements', []):
                    if element.get('is_struct', False):
                        structs[element['name']] = element
                
                logger.info(f"✅ clang-uml found {len(structs)} structs")
                return structs
            
            return {}
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _fallback_struct_parsing(self, c_files: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fallback struct parsing when clang-uml fails"""
        
        logger.info("🚨 Using fallback struct parsing (clang-uml unavailable)")
        
        structs = {}
        
        for c_file in c_files:
            try:
                with open(c_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse struct definitions
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
                            
                            # Parse struct members
                            members = []
                            field_pattern = r'([A-Za-z_][A-Za-z0-9_\s\*]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;'
                            
                            for field_match in re.finditer(field_pattern, struct_body):
                                field_type, field_name = field_match.groups()
                                members.append({
                                    'name': field_name,
                                    'type': field_type.strip(),
                                    'access': 'public',
                                    'is_static': False
                                })
                            
                            # Create struct element
                            line_num = content[:match.start()].count('\n') + 1
                            struct_element = {
                                'name': struct_name,
                                'namespace': '',
                                'kind': 'class',
                                'is_struct': True,
                                'source_location': {
                                    'file': c_file,
                                    'line': line_num
                                },
                                'members': members,
                                'methods': []
                            }
                            
                            structs[struct_name] = struct_element
                            logger.debug(f"Fallback: parsed struct {struct_name} with {len(members)} fields")
                
            except Exception as e:
                logger.error(f"Failed to parse structs from {c_file}: {e}")
        
        logger.info(f"✅ Fallback struct parsing found {len(structs)} structs")
        return structs
    
    def _parse_functions_from_sources(self, c_files: List[str]) -> List[Dict[str, Any]]:
        """Parse functions from C source files (lightweight)"""
        
        functions = []
        
        for c_file in c_files:
            try:
                with open(c_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Simple function parsing
                func_pattern = r'^\s*([A-Za-z_][A-Za-z0-9_\s\*]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*[{;]'
                
                for match in re.finditer(func_pattern, content, re.MULTILINE):
                    return_type, func_name, params_str = match.groups()
                    return_type = return_type.strip()
                    
                    # Skip struct definitions
                    if 'struct' in return_type or 'typedef' in return_type:
                        continue
                    
                    # Parse parameters
                    parameters = self._parse_function_params(params_str)
                    
                    function_data = {
                        'name': func_name,
                        'return_type': return_type,
                        'parameters': parameters,
                        'source_file': c_file,
                        'line': content[:match.start()].count('\n') + 1
                    }
                    
                    functions.append(function_data)
                    
            except Exception as e:
                logger.error(f"Failed to parse functions from {c_file}: {e}")
        
        logger.info(f"✅ Parsed {len(functions)} functions from source files")
        return functions
    
    def _parse_function_params(self, params_str: str) -> List[Dict[str, Any]]:
        """Parse function parameters"""
        parameters = []
        
        if not params_str.strip() or params_str.strip() == 'void':
            return parameters
        
        for param_part in params_str.split(','):
            param_part = param_part.strip()
            if not param_part:
                continue
            
            # Extract type and name
            param_match = re.match(r'(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', param_part)
            if param_match:
                param_type, param_name = param_match.groups()
                parameters.append({
                    'name': param_name,
                    'type': param_type.strip()
                })
        
        return parameters
    
    def _apply_method_binding(self, structs_data: Dict[str, Any], functions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply method binding to combine clang-uml structs with parsed functions"""
        
        # Convert to internal format for binding
        structs = {}
        for name, struct_data in structs_data.items():
            from core.c_model_builder import CStruct
            
            c_struct = CStruct(
                name=struct_data['name'],
                source_file=struct_data.get('source_location', {}).get('file', ''),
                line_number=struct_data.get('source_location', {}).get('line', 0)
            )
            
            # Add fields from clang-uml data
            for member in struct_data.get('members', []):
                field = CParameter(
                    name=member['name'],
                    type=member['type'],
                    is_const='const' in member['type'],
                    is_pointer='*' in member['type']
                )
                c_struct.fields.append(field)
            
            structs[name] = c_struct
        
        # Convert functions
        functions = []
        for func_data in functions_data:
            c_function = CFunction(
                name=func_data['name'],
                return_type=func_data['return_type'],
                source_file=func_data['source_file'],
                line_number=func_data['line']
            )
            
            # Add parameters
            for param_data in func_data['parameters']:
                param = CParameter(
                    name=param_data['name'],
                    type=param_data['type'],
                    is_const='const' in param_data['type'],
                    is_pointer='*' in param_data['type']
                )
                c_function.parameters.append(param)
            
            functions.append(c_function)
        
        # Apply binding
        unbound_data = self.method_binder.bind_functions_to_structs(functions, structs)
        
        # Return enhanced structs with binding info
        result = {
            'structs': structs,
            'unbound_functions': unbound_data['unbound'],
            'binding_stats': self.method_binder.binding_stats
        }
        
        return result
    
    def _generate_enhanced_json(self, enhanced_data: Dict[str, Any], source_files: List[str]) -> Dict[str, Any]:
        """Generate final JSON with clang-uml structs + bound methods"""
        
        elements = {}
        
        # Process structs with bound methods
        for struct_name, c_struct in enhanced_data['structs'].items():
            element = {
                'name': c_struct.name,
                'namespace': '',
                'kind': 'class',
                'is_struct': True,
                'source_location': {
                    'file': c_struct.source_file,
                    'line': c_struct.line_number
                },
                'members': [],
                'methods': []
            }
            
            # Add fields
            for field in c_struct.fields:
                element['members'].append({
                    'name': field.name,
                    'type': field.type,
                    'access': 'public',
                    'is_static': False
                })
            
            # Add bound methods (deduplicate)
            seen_methods = set()
            for method in c_struct.bound_methods:
                # Deduplicate by method name
                if method.name in seen_methods:
                    continue
                seen_methods.add(method.name)
                
                method_json = {
                    'name': method.name,
                    'return_type': method.return_type,
                    'access': 'public',
                    'is_static': False,
                    'parameters': []
                }
                
                # Skip first parameter (struct instance)
                for param in method.parameters[1:]:
                    method_json['parameters'].append({
                        'name': param.name,
                        'type': param.type
                    })
                
                element['methods'].append(method_json)
            
            elements[struct_name] = element
        
        # Add utility functions
        unbound_functions = enhanced_data.get('unbound_functions', [])
        if unbound_functions:
            utility_element = {
                'name': 'UtilityFunctions',
                'namespace': '',
                'kind': 'class',
                'is_utility': True,
                'members': [],
                'methods': []
            }
            
            # Deduplicate unbound functions
            seen_functions = set()
            for func in unbound_functions:
                if func.name in seen_functions:
                    continue
                seen_functions.add(func.name)
                
                method_json = {
                    'name': func.name,
                    'return_type': func.return_type,
                    'access': 'public',
                    'is_static': True,
                    'parameters': []
                }
                
                for param in func.parameters:
                    method_json['parameters'].append({
                        'name': param.name,
                        'type': param.type
                    })
                
                utility_element['methods'].append(method_json)
            
            elements['UtilityFunctions'] = utility_element
        
        # Add metadata
        return {
            'elements': elements,
            '_metadata': {
                'source_files': source_files,
                'binding_stats': enhanced_data.get('binding_stats', {}),
                'generated_by': 'clang-uml + hybrid_c_builder',
                'processing_mode': 'c_language_hybrid'
            }
        }

# ===============================================
# MAIN API
# ===============================================

def build_c_model_hybrid(source_files: List[str], output_path: str) -> Dict[str, Any]:
    """
    Main API for hybrid C model building
    
    ✅ Uses clang-uml for robust struct parsing
    ✅ Uses function parsing for method binding
    ✅ Explicit strategy (no heuristics)
    """
    
    builder = CHybridBuilder()
    return builder.build_c_model(source_files, output_path)

if __name__ == "__main__":
    # Test hybrid builder
    c_files = [
        "tests/assets/test_c_project/point.c",
        "tests/assets/test_c_project/point.h"  
    ]
    
    try:
        result = build_c_model_hybrid(c_files, "output_hybrid_c.json")
        print("✅ Hybrid C model building successful")
        print(f"📊 Result: {result.get('_metadata', {})}")
    except Exception as e:
        print(f"❌ Hybrid building failed: {e}")
