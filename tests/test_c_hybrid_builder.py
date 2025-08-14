#!/usr/bin/env python3
"""
Tests for Hybrid C Model Builder (clang-uml + method binding)

✅ Tests PRODUCTION-READY hybrid implementation
"""

import pytest
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.c_hybrid_builder import CHybridBuilder, build_c_model_hybrid


class TestCHybridBuilder:
    """Test hybrid C builder (clang-uml + method binding)"""
    
    def test_hybrid_builder_basic_functionality(self):
        """Test basic functionality of hybrid builder"""
        
        c_files = [
            "tests/assets/test_c_project/point.c",
            "tests/assets/test_c_project/point.h"
        ]
        
        builder = CHybridBuilder()
        result = builder.build_c_model(c_files, "test_output.json")
        
        # Check basic structure
        assert 'elements' in result
        assert '_metadata' in result
        
        elements = result['elements']
        metadata = result['_metadata']
        
        # Should have Point element
        assert 'Point' in elements
        
        point = elements['Point']
        assert point['is_struct'] == True
        assert 'members' in point
        assert 'methods' in point
        
        # Check binding statistics
        binding_stats = metadata['binding_stats']
        assert binding_stats['total_functions'] > 0
        assert binding_stats['bound_functions'] > 0
        assert binding_stats['binding_conflicts'] == 0
        
        print(f"✅ Hybrid builder stats: {binding_stats}")
    
    def test_clang_uml_struct_accuracy(self):
        """Test that clang-uml provides accurate struct information"""
        
        c_files = ["tests/assets/test_c_project/point.h", "tests/assets/test_c_project/point.c"]
        
        result = build_c_model_hybrid(c_files, "test_accuracy.json")
        
        point = result['elements']['Point']
        
        # Check struct fields from clang-uml (should be accurate)
        members = point['members']
        member_names = [m['name'] for m in members]
        
        assert 'x' in member_names
        assert 'y' in member_names
        
        # Check field types
        x_field = next(m for m in members if m['name'] == 'x')
        y_field = next(m for m in members if m['name'] == 'y')
        
        assert x_field['type'] == 'int'
        assert y_field['type'] == 'int'
        assert x_field['access'] == 'public'  # C struct fields are public
    
    def test_method_binding_integration(self):
        """Test that method binding works with clang-uml struct data"""
        
        c_files = ["tests/assets/test_c_project/point.c", "tests/assets/test_c_project/point.h"]
        
        result = build_c_model_hybrid(c_files, "test_binding.json")
        
        # Check Point bound methods
        point = result['elements']['Point']
        methods = point['methods']
        method_names = [m['name'] for m in methods]
        
        # Should have bound methods (first arg Point*)
        expected_point_methods = ['point_move', 'point_print', 'point_distance_squared']
        for expected in expected_point_methods:
            assert expected in method_names, f"Method {expected} should be bound to Point"
        
        # point_create should NOT be bound (first arg int, not Point*)
        assert 'point_create' not in method_names, "point_create should NOT be bound (factory function)"
        
        print(f"✅ Point bound methods: {method_names}")
    
    def test_utility_functions_handling(self):
        """Test that utility functions are handled correctly"""
        
        c_files = ["tests/assets/test_c_project/point.c"]
        
        result = build_c_model_hybrid(c_files, "test_utility.json")
        
        # Should have UtilityFunctions for unbound functions
        if 'UtilityFunctions' in result['elements']:
            utility = result['elements']['UtilityFunctions']
            assert utility['is_utility'] == True
            
            utility_methods = utility['methods']
            utility_method_names = [m['name'] for m in utility_methods]
            
            # Utility functions should be here
            expected_utility = ['max', 'init_system', 'point_create']  # point_create is factory
            for expected in expected_utility:
                if expected in utility_method_names:
                    # Check that they're marked as static
                    method = next(m for m in utility_methods if m['name'] == expected)
                    assert method['is_static'] == True, f"Utility method {expected} should be static"
        
        # Check binding statistics
        metadata = result['_metadata']
        binding_stats = metadata['binding_stats']
        assert binding_stats['unbound_functions'] > 0  # Should have some unbound functions
    
    def test_json_format_compatibility(self):
        """Test that output JSON is compatible with existing pipeline"""
        
        c_files = ["tests/assets/test_c_project/point.c", "tests/assets/test_c_project/point.h"]
        
        result = build_c_model_hybrid(c_files, "test_compatibility.json")
        
        # Should have expected top-level structure
        assert 'elements' in result
        assert '_metadata' in result
        
        # Elements should have proper structure for each struct
        for element_name, element in result['elements'].items():
            if element.get('is_struct'):
                # Required fields for UML processing
                assert 'name' in element
                assert 'namespace' in element
                assert 'kind' in element  
                assert 'members' in element
                assert 'methods' in element
                
                # Source location information
                assert 'source_location' in element
                assert 'file' in element['source_location']
                assert 'line' in element['source_location']
    
    def test_no_regex_brittleness(self):
        """Test that hybrid approach is more robust than pure regex"""
        
        c_files = ["tests/assets/test_c_project/point.h"]  # Header only
        
        # Should work even with header-only files (clang-uml handles this)
        result = build_c_model_hybrid(c_files, "test_robust.json")
        
        # Should successfully process Point struct from header
        assert 'Point' in result['elements']
        
        point = result['elements']['Point']
        assert len(point['members']) == 2  # x, y fields
        
        # Should be robust to parsing variations
        metadata = result['_metadata']
        assert metadata['generated_by'] == 'clang-uml + hybrid_c_builder'
        assert metadata['processing_mode'] == 'c_language_hybrid'


class TestCHybridBuilderAdvanced:
    """Advanced tests for C hybrid builder"""
    
    def test_large_c_project_processing(self):
        """Test processing multiple C files"""
        
        # Use example.c (larger file) for testing
        c_files = ["tests/assets/example.c"]
        
        result = build_c_model_hybrid(c_files, "test_large.json")
        
        metadata = result['_metadata']
        binding_stats = metadata['binding_stats']
        
        # Should process reasonable number of functions
        assert binding_stats['total_functions'] >= 5
        assert binding_stats['bound_functions'] > 0
        assert binding_stats['binding_conflicts'] == 0
        
        # Should have multiple structs
        elements = result['elements']
        struct_count = len([e for e in elements.values() if e.get('is_struct')])
        assert struct_count > 0
    
    def test_method_parameter_handling(self):
        """Test that method parameters are handled correctly after binding"""
        
        c_files = ["tests/assets/test_c_project/point.c"]
        
        result = build_c_model_hybrid(c_files, "test_params.json")
        
        point = result['elements']['Point']
        methods = point['methods']
        
        # Find point_move method
        move_method = next((m for m in methods if m['name'] == 'point_move'), None)
        assert move_method is not None
        
        # Should have 2 parameters (dx, dy) - first parameter (Point* p) should be removed
        params = move_method['parameters']
        assert len(params) == 2
        
        param_names = [p['name'] for p in params]
        assert 'dx' in param_names
        assert 'dy' in param_names
        assert 'p' not in param_names  # First parameter should be removed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
