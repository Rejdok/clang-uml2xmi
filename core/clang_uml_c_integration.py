#!/usr/bin/env python3
"""
Integration with clang-uml for C language processing

Uses clang-uml to generate accurate JSON from C source code,
then applies method binding and C-specific processing.

✅ ROBUST IMPLEMENTATION using clang-uml (no regex fallbacks)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
import subprocess
import tempfile
import logging
import shutil
from pathlib import Path

from core.c_model_builder import CMethodBinder, CFunction, CStruct, CParameter

logger = logging.getLogger(__name__)

# ===============================================
# CLANG-UML C INTEGRATION
# ===============================================

@dataclass
class ClangUmlCConfig:
    """Configuration for clang-uml C processing"""
    output_format: str = "json"
    compilation_flags: List[str] = None
    include_paths: List[str] = None
    exclude_paths: List[str] = None
    
    def __post_init__(self):
        if self.compilation_flags is None:
            self.compilation_flags = ["-std=c99"]
        if self.include_paths is None:
            self.include_paths = ["."]
        if self.exclude_paths is None:
            self.exclude_paths = []

class ClangUmlCProcessor:
    """Process C source code using clang-uml + method binding"""
    
    def __init__(self, config: Optional[ClangUmlCConfig] = None):
        self.config = config or ClangUmlCConfig()
        self.method_binder = CMethodBinder()
    
    def process_c_sources(self, c_files: List[str], output_path: str) -> Dict[str, Any]:
        """
        Process C source files using clang-uml + method binding
        
        Steps:
        1. Create temporary clang-uml project
        2. Generate JSON using clang-uml  
        3. Parse JSON and extract C constructs
        4. Apply method binding by first argument type
        5. Return enhanced JSON with bound methods
        """
        
        logger.info(f"✅ Processing {len(c_files)} C files with clang-uml")
        
        # Create temporary project structure
        temp_dir = self._create_temp_project(c_files)
        
        try:
            # Generate JSON using clang-uml
            json_path = self._run_clang_uml(temp_dir)
            
            # Load and parse clang-uml JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                clang_uml_data = json.load(f)
            
            # Apply C-specific processing and method binding
            enhanced_data = self._apply_c_processing(clang_uml_data, c_files)
            
            # Save enhanced JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Enhanced C model written to: {output_path}")
            return enhanced_data
            
        finally:
            # Cleanup temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _create_temp_project(self, c_files: List[str]) -> Path:
        """Create temporary project structure for clang-uml"""
        
        temp_dir = Path(tempfile.mkdtemp(prefix="clang_uml_c_"))
        logger.debug(f"Created temp directory: {temp_dir}")
        
        # Copy C files to temp directory
        for c_file in c_files:
            src_path = Path(c_file)
            if src_path.exists():
                dst_path = temp_dir / src_path.name
                shutil.copy2(src_path, dst_path)
                logger.debug(f"Copied {src_path} → {dst_path}")
        
        # Create compile_commands.json
        compile_commands = []
        for c_file in c_files:
            c_path = Path(c_file)
            if c_path.suffix in ['.c', '.cpp']:  # Only for source files
                compile_commands.append({
                    "directory": str(temp_dir.absolute()).replace('\\', '/'),
                    "command": f"gcc {' '.join(self.config.compilation_flags)} -c {c_path.name}",
                    "file": c_path.name
                })
        
        compile_db_path = temp_dir / "compile_commands.json"
        with open(compile_db_path, 'w') as f:
            json.dump(compile_commands, f, indent=2)
        
        # Create .clang-uml config
        clang_uml_config = {
            "compilation_database_dir": ".",
            "output_directory": "output",
            "diagrams": {
                "c_class_diagram": {
                    "type": "class",
                    "glob": ["*.c", "*.h"],
                    "include": {
                        "paths": self.config.include_paths
                    }
                }
            }
        }
        
        import yaml
        config_path = temp_dir / ".clang-uml"
        with open(config_path, 'w') as f:
            yaml.dump(clang_uml_config, f, default_flow_style=False)
        
        return temp_dir
    
    def _run_clang_uml(self, project_dir: Path) -> Path:
        """Run clang-uml to generate JSON"""
        
        cmd = [
            "clang-uml", 
            "-c", ".clang-uml",
            "-g", "json", 
            "-n", "c_class_diagram",
            "-q"  # Quiet mode
        ]
        
        logger.debug(f"Running: {' '.join(cmd)} in {project_dir}")
        
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"clang-uml failed: {result.stderr}")
            raise RuntimeError(f"clang-uml generation failed: {result.stderr}")
        
        json_path = project_dir / "output" / "c_class_diagram.json"
        if not json_path.exists():
            raise RuntimeError(f"Expected JSON output not found: {json_path}")
        
        return json_path
    
    def _apply_c_processing(self, clang_uml_data: Dict[str, Any], source_files: List[str]) -> Dict[str, Any]:
        """Apply C-specific processing to clang-uml JSON data"""
        
        # Extract elements from clang-uml JSON format
        elements = clang_uml_data.get('elements', [])
        
        # Convert to our internal format
        structs = {}
        functions = []
        
        for element in elements:
            if element.get('type') == 'class' and element.get('kind') == 'struct':
                # Convert clang-uml class to C struct
                struct = self._convert_clang_element_to_struct(element)
                structs[struct.name] = struct
            
            elif element.get('type') == 'method':
                # Convert clang-uml method to C function
                function = self._convert_clang_element_to_function(element)
                functions.append(function)
        
        # Apply method binding
        logger.info(f"Applying method binding to {len(functions)} functions and {len(structs)} structs")
        unbound_data = self.method_binder.bind_functions_to_structs(functions, structs)
        
        # Convert back to enhanced JSON format
        enhanced_json = self._convert_to_enhanced_json(structs, unbound_data['unbound'])
        
        # Add metadata
        enhanced_json['_metadata'] = {
            'source_files': source_files,
            'binding_stats': self.method_binder.binding_stats,
            'generated_by': 'clang-uml + c_method_binding',
            'processing_mode': 'c_language'
        }
        
        return enhanced_json
    
    def _convert_clang_element_to_struct(self, element: Dict[str, Any]) -> CStruct:
        """Convert clang-uml class element to C struct"""
        
        struct = CStruct(
            name=element.get('name', 'UnknownStruct'),
            source_file=element.get('source_location', {}).get('file', ''),
            line_number=element.get('source_location', {}).get('line', 0)
        )
        
        # Convert members to fields
        for member in element.get('members', []):
            field = CParameter(
                name=member.get('name', ''),
                type=member.get('type', ''),
                is_const='const' in member.get('type', ''),
                is_pointer='*' in member.get('type', ''),
                is_array='[]' in member.get('type', '')
            )
            struct.fields.append(field)
        
        return struct
    
    def _convert_clang_element_to_function(self, element: Dict[str, Any]) -> CFunction:
        """Convert clang-uml method element to C function"""
        
        function = CFunction(
            name=element.get('name', 'unknown'),
            return_type=element.get('type', 'void'),
            source_file=element.get('source_location', {}).get('file', ''),
            line_number=element.get('source_location', {}).get('line', 0)
        )
        
        # Convert parameters
        for param in element.get('parameters', []):
            parameter = CParameter(
                name=param.get('name', ''),
                type=param.get('type', ''),
                is_const='const' in param.get('type', ''),
                is_pointer='*' in param.get('type', ''),
                is_array='[]' in param.get('type', '')
            )
            function.parameters.append(parameter)
        
        return function
    
    def _convert_to_enhanced_json(self, structs: Dict[str, CStruct], unbound_functions: List[CFunction]) -> Dict[str, Any]:
        """Convert C structures with bound methods to enhanced JSON"""
        
        elements = {}
        
        # Convert structs with bound methods
        for struct_name, struct in structs.items():
            element_json = {
                'name': struct.name,
                'namespace': '',
                'kind': 'class',
                'is_struct': True,
                'source_location': {
                    'file': struct.source_file,
                    'line': struct.line_number
                },
                'members': [],
                'methods': []
            }
            
            # Add struct fields
            for field in struct.fields:
                member_json = {
                    'name': field.name,
                    'type': field.type,
                    'access': 'public',  # C struct fields are public
                    'is_static': False
                }
                element_json['members'].append(member_json)
            
            # Add bound methods
            for method in struct.bound_methods:
                method_json = {
                    'name': method.name,
                    'return_type': method.return_type,
                    'access': 'public',
                    'is_static': False,
                    'parameters': []
                }
                
                # Skip first parameter (the struct instance)
                for param in method.parameters[1:]:
                    param_json = {
                        'name': param.name,
                        'type': param.type
                    }
                    method_json['parameters'].append(param_json)
                
                element_json['methods'].append(method_json)
            
            elements[struct_name] = element_json
        
        # Add unbound functions as utility class if any
        if unbound_functions:
            utility_element = {
                'name': 'UtilityFunctions',
                'namespace': '',
                'kind': 'class',
                'is_utility': True,
                'methods': []
            }
            
            for func in unbound_functions:
                method_json = {
                    'name': func.name,
                    'return_type': func.return_type,
                    'access': 'public',
                    'is_static': True,  # Utility functions are static
                    'parameters': []
                }
                
                for param in func.parameters:
                    param_json = {
                        'name': param.name,
                        'type': param.type
                    }
                    method_json['parameters'].append(param_json)
                
                utility_element['methods'].append(method_json)
            
            elements['UtilityFunctions'] = utility_element
        
        return elements

# ===============================================
# HIGH-LEVEL C PROCESSING API
# ===============================================

def process_c_project_with_clang_uml(c_files: List[str], 
                                    output_path: str,
                                    config: Optional[ClangUmlCConfig] = None) -> Dict[str, Any]:
    """
    Main API for processing C project with clang-uml + method binding
    
    Args:
        c_files: List of C source file paths
        output_path: Where to save enhanced JSON
        config: Optional configuration
    
    Returns:
        Enhanced JSON with method binding applied
    """
    
    logger.info("🚀 PROCESSING C PROJECT WITH CLANG-UML")
    logger.info("✅ Using robust clang-uml parsing (no regex fallbacks)")
    
    processor = ClangUmlCProcessor(config)
    return processor.process_c_sources(c_files, output_path)

# ===============================================
# CLI INTEGRATION EXAMPLE
# ===============================================

def example_clang_uml_c_processing():
    """Example of using clang-uml for C processing"""
    
    print("=== CLANG-UML C PROCESSING EXAMPLE ===")
    print("✅ Using clang-uml for accurate C parsing")
    print("🔗 Applying method binding by first argument type")
    print()
    
    # Example usage
    c_files = [
        "tests/assets/test_c_project/point.c",
        "tests/assets/test_c_project/point.h"
    ]
    
    config = ClangUmlCConfig(
        compilation_flags=["-std=c99", "-Wall"],
        include_paths=["."]
    )
    
    try:
        result = process_c_project_with_clang_uml(c_files, "output_c_enhanced.json", config)
        
        print(f"✅ Processed {len(c_files)} C files")
        print(f"📊 Binding stats: {result.get('_metadata', {}).get('binding_stats', {})}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")

if __name__ == "__main__":
    example_clang_uml_c_processing()
