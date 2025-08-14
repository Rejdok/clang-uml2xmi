#!/usr/bin/env python3
"""
Tests for C Model Builder with Method Binding

✅ Tests for C language processing with method binding
Production-ready implementation integrated with XMI pipeline
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
# Path management handled by core/__init__.py

from core.c_model_builder import (
    CModelBuilder, CSourceParser, CMethodBinder, 
    CFunction, CStruct, CParameter, 
    build_c_uml_model
)


class TestCSourceParser:
    """Test C source code parsing"""
    
    def test_parse_simple_struct(self):
        """Test parsing of simple C struct"""
        c_code = """
        typedef struct {
            int x;
            int y;
        } Point;
        """
        
        parser = CSourceParser()
        # Create temp file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(c_code)
            temp_path = f.name
        
        try:
            parsed_data = parser.parse_c_file(temp_path)
            
            assert 'structs' in parsed_data
            assert 'Point' in parsed_data['structs']
            
            point_struct = parsed_data['structs']['Point']
            assert point_struct.name == 'Point'
            assert len(point_struct.fields) == 2
            assert point_struct.fields[0].name == 'x'
            assert point_struct.fields[1].name == 'y'
            
        finally:
            Path(temp_path).unlink()  # Cleanup
    
    def test_parse_functions(self):
        """Test parsing of C functions"""
        c_code = """
        void point_move(Point* p, int dx, int dy);
        int point_distance(const Point* a, const Point* b);
        void init_system();
        """
        
        parser = CSourceParser()
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(c_code)
            temp_path = f.name
        
        try:
            parsed_data = parser.parse_c_file(temp_path)
            
            functions = parsed_data.get('functions', [])
            assert len(functions) == 3
            
            # Check function details
            move_func = next((f for f in functions if f.name == 'point_move'), None)
            assert move_func is not None
            assert move_func.return_type == 'void'
            assert len(move_func.parameters) == 3
            assert move_func.parameters[0].type == 'Point*'
            
        finally:
            Path(temp_path).unlink()


class TestCMethodBinder:
    """Test method binding functionality"""
    
    def test_bind_functions_to_structs(self):
        """Test binding C functions to structs by first argument type"""
        
        # Create test structs
        point_struct = CStruct(name='Point', fields=[
            CParameter(name='x', type='int'),
            CParameter(name='y', type='int')
        ])
        
        structs = {'Point': point_struct}
        
        # Create test functions
        functions = [
            CFunction(name='point_move', return_type='void', parameters=[
                CParameter(name='p', type='Point*'),
                CParameter(name='dx', type='int'),
                CParameter(name='dy', type='int')
            ]),
            CFunction(name='point_print', return_type='void', parameters=[
                CParameter(name='p', type='const Point*')
            ]),
            CFunction(name='max', return_type='int', parameters=[
                CParameter(name='a', type='int'),
                CParameter(name='b', type='int')
            ])  # Should NOT be bound (primitive first arg)
        ]
        
        binder = CMethodBinder()
        unbound_data = binder.bind_functions_to_structs(functions, structs)
        
        # Check binding results
        assert len(point_struct.bound_methods) == 2  # point_move and point_print bound
        assert len(unbound_data['unbound']) == 1     # max function unbound
        
        # Check bound method names
        bound_names = [m.name for m in point_struct.bound_methods]
        assert 'point_move' in bound_names
        assert 'point_print' in bound_names
        
        # Check unbound function
        assert unbound_data['unbound'][0].name == 'max'
    
    def test_primitive_type_not_bound(self):
        """Test that functions with primitive first arguments are not bound"""
        
        structs = {}  # No structs
        
        functions = [
            CFunction(name='add', return_type='int', parameters=[
                CParameter(name='a', type='int'),
                CParameter(name='b', type='int')
            ]),
            CFunction(name='strlen', return_type='size_t', parameters=[
                CParameter(name='str', type='const char*')
            ])
        ]
        
        binder = CMethodBinder()
        unbound_data = binder.bind_functions_to_structs(functions, structs)
        
        # All functions should be unbound (primitive types)
        assert len(unbound_data['unbound']) == 2
        assert binder.binding_stats['bound_functions'] == 0
        assert binder.binding_stats['unbound_functions'] == 2
    
    def test_first_param_type_extraction(self):
        """Test extraction of clean first parameter type"""
        
        # Test various C parameter formats
        test_cases = [
            ('Point*', 'Point'),
            ('const Point*', 'Point'),
            ('Point', 'Point'),
            ('const Point', 'Point'), 
            ('struct Point*', 'struct Point'),  # struct keyword preserved
            ('int', 'int'),
            ('const char*', 'char')  # const removed, * removed → char
        ]
        
        for input_type, expected_clean in test_cases:
            param = CParameter(name='test', type=input_type)
            func = CFunction(name='test_func', return_type='void', parameters=[param])
            
            clean_type = func.get_first_param_type()
            assert clean_type == expected_clean, f"Input: {input_type}, Expected: {expected_clean}, Got: {clean_type}"


class TestCModelBuilder:
    """Test complete C model building process"""
    
    def test_build_from_example_c_file(self):
        """Test building UML model from real C source file"""
        
        example_c_path = "tests/assets/example.c"
        
        builder = CModelBuilder()
        uml_model = builder.build_from_c_sources([example_c_path])
        
        # Should have created UML elements
        assert len(uml_model.elements) > 0
        assert len(uml_model.name_to_xmi) > 0
        
        # Check that Point and Rectangle structs were parsed
        assert 'Point' in uml_model.name_to_xmi
        assert 'Rectangle' in uml_model.name_to_xmi
        
        # Get binding statistics
        binding_report = builder.get_binding_report()
        assert 'binding_stats' in binding_report
        assert binding_report['binding_stats']['total_functions'] > 0
        assert binding_report['binding_stats']['bound_functions'] > 0
        
        print(f"Binding report: {binding_report}")
    
    def test_json_format_output(self):
        """Test JSON format output compatible with existing pipeline"""
        
        example_c_path = "tests/assets/example.c"
        
        result = build_c_model_from_sources([example_c_path], output_format="json")
        
        assert 'elements' in result
        assert 'binding_report' in result
        
        elements = result['elements']
        
        # Should have Point and Rectangle elements
        assert 'Point' in elements
        assert 'Rectangle' in elements
        
        # Point should have bound methods
        point_element = elements['Point']
        assert 'methods' in point_element
        assert len(point_element['methods']) > 0
        
        # Check bound method structure
        methods = point_element['methods']
        method_names = [m['name'] for m in methods]
        
        # Should have point_move, point_print, etc. bound to Point (first arg Point*)
        expected_point_methods = ['point_move', 'point_print', 'point_distance_squared']
        for expected_method in expected_point_methods:
            assert expected_method in method_names, f"Method {expected_method} should be bound to Point"
        
        # point_create should NOT be bound (first arg is int, not Point*)
        assert 'point_create' not in method_names, "point_create should NOT be bound to Point (factory function)"
        
        print(f"Point bound methods: {method_names}")
    
    def test_struct_field_parsing(self):
        """Test that struct fields are parsed correctly"""
        
        example_c_path = "tests/assets/example.c"
        
        result = build_c_model_from_sources([example_c_path], output_format="json")
        elements = result['elements']
        
        # Point struct should have x, y fields
        point_element = elements['Point']
        assert 'members' in point_element
        
        members = point_element['members']
        member_names = [m['name'] for m in members]
        
        assert 'x' in member_names
        assert 'y' in member_names
        
        # Rectangle should have top_left, bottom_right fields
        rect_element = elements['Rectangle']
        rect_members = rect_element['members']
        rect_member_names = [m['name'] for m in rect_members]
        
        assert 'top_left' in rect_member_names
        assert 'bottom_right' in rect_member_names
        
        print(f"Point fields: {member_names}")
        print(f"Rectangle fields: {rect_member_names}")


class TestCMethodBinding:
    """Test specific method binding scenarios"""
    
    def test_point_methods_bound_correctly(self):
        """Test that Point-related functions are bound to Point struct"""
        
        example_c_path = "tests/assets/example.c"
        builder = CModelBuilder()
        uml_model = builder.build_from_c_sources([example_c_path])
        
        # Get Point struct data
        point_struct = None
        for struct in builder.parser.structs.values():
            if struct.name == 'Point':
                point_struct = struct
                break
        
        assert point_struct is not None
        assert len(point_struct.bound_methods) > 0
        
        # Check specific bindings
        bound_method_names = [m.name for m in point_struct.bound_methods]
        
        # Functions that SHOULD be bound (first arg is Point* or const Point*)
        expected_bindings = ['point_move', 'point_print', 'point_distance_squared']
        
        for expected in expected_bindings:
            assert expected in bound_method_names, f"Function {expected} should be bound to Point"
        
        # point_create should NOT be bound (first arg is int, not Point*)
        assert 'point_create' not in bound_method_names, "point_create should NOT be bound (first arg is int)"
        
        print(f"Point bound methods: {bound_method_names}")
    
    def test_utility_functions_not_bound(self):
        """Test that utility functions are not bound to any struct"""
        
        example_c_path = "tests/assets/example.c"
        builder = CModelBuilder()
        
        result = build_c_model_from_sources([example_c_path], output_format="json")
        
        # Should have UtilityFunctions element for unbound functions
        elements = result['elements']
        
        # Utility functions should exist somewhere (either as separate element or in report)
        binding_report = result['binding_report']
        assert binding_report['binding_stats']['unbound_functions'] > 0
        
        # Functions like max, min, init_graphics should not be bound to Point/Rectangle
        for struct_name in ['Point', 'Rectangle']:
            if struct_name in elements:
                struct_element = elements[struct_name]
                method_names = [m['name'] for m in struct_element.get('methods', [])]
                
                # These should NOT be bound to structs
                assert 'max' not in method_names
                assert 'min' not in method_names
                assert 'init_graphics' not in method_names
    
    def test_no_multiple_binding_candidates(self):
        """Test that there are no multiple binding candidates (C has no overloading)"""
        
        # In C, function names are unique, so no binding conflicts should occur
        example_c_path = "tests/assets/example.c"
        builder = CModelBuilder()
        uml_model = builder.build_from_c_sources([example_c_path])
        
        binding_report = builder.get_binding_report()
        
        # Should have no binding conflicts (multiple candidates)
        assert binding_report['binding_stats']['binding_conflicts'] == 0


if __name__ == "__main__":
    print("🚨 C MODEL BUILDER TESTS")
    print("Testing fallback implementation for C language processing.\n")
    
    pytest.main([__file__, "-v"])
