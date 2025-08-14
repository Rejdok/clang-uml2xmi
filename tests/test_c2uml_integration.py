#!/usr/bin/env python3
"""
Integration tests for C2UML (complete C language processing pipeline)

✅ Tests PRODUCTION-READY C language UML model generation
"""

import pytest
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestC2UMLIntegration:
    """Complete integration tests for C2UML pipeline"""
    
    def test_complete_c_processing_pipeline(self):
        """Test complete C → UML pipeline"""
        
        # Process example C file with C2UML (direct function call)
        from core.c_hybrid_builder import build_c_model_hybrid
        
        c_files = ["tests/assets/example.c"]
        output_path = "integration_test_output.json"
        
        c_model = build_c_model_hybrid(c_files, output_path)
        
        # Validate JSON was generated
        output_path = Path("integration_test_output.json")
        assert output_path.exists(), "Output JSON not generated"
        
        # Validate JSON structure
        assert 'elements' in c_model
        assert '_metadata' in c_model
        
        elements = c_model['elements']
        metadata = c_model['_metadata']
        
        # Should have structs
        struct_elements = {k: v for k, v in elements.items() if v.get('is_struct')}
        assert len(struct_elements) >= 2, "Should have Point and Rectangle structs"
        
        # Check Point struct
        assert 'Point' in elements
        point = elements['Point']
        
        # Struct fields
        assert len(point['members']) == 2  # x, y
        member_names = [m['name'] for m in point['members']]
        assert 'x' in member_names and 'y' in member_names
        
        # Bound methods
        assert len(point['methods']) >= 3  # point_move, point_print, point_distance_squared
        method_names = [m['name'] for m in point['methods']]
        expected_point_methods = ['point_move', 'point_print', 'point_distance_squared']
        
        for expected in expected_point_methods:
            assert expected in method_names, f"Method {expected} should be bound to Point"
        
        # Check Rectangle struct
        assert 'Rectangle' in elements
        rectangle = elements['Rectangle']
        assert len(rectangle['members']) == 2  # top_left, bottom_right
        assert len(rectangle['methods']) >= 3   # rect_init, rect_area, rect_print
        
        # Check utility functions
        if 'UtilityFunctions' in elements:
            utility = elements['UtilityFunctions']
            assert utility['is_utility'] == True
            
            utility_method_names = [m['name'] for m in utility['methods']]
            assert 'point_create' in utility_method_names  # Factory function
            assert 'max' in utility_method_names           # Utility function
        
        # Check metadata
        binding_stats = metadata['binding_stats']
        assert binding_stats['total_functions'] >= 10
        assert binding_stats['bound_functions'] >= 6
        assert binding_stats['binding_conflicts'] == 0
        assert binding_stats['bound_functions'] / binding_stats['total_functions'] > 0.5  # >50% binding
        
        print(f"✅ Integration test passed - binding ratio: {binding_stats['bound_functions'] / binding_stats['total_functions']:.1%}")
        
        # Cleanup
        if output_path.exists():
            output_path.unlink()
    
    def test_c2uml_cli_error_handling(self):
        """Test C2UML CLI error handling"""
        
        import subprocess
        
        # Test with non-existent file
        cmd = [sys.executable, "c2uml.py", "nonexistent.c", "output.json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode != 0  # Should fail gracefully
        assert "not found" in result.stdout or "not found" in result.stderr
    
    def test_c2uml_json_compatibility_with_existing_pipeline(self):
        """Test that C2UML output is compatible with existing UML pipeline"""
        
        # Generate C model
        import subprocess
        
        cmd = [sys.executable, "c2uml.py", "tests/assets/example.c", "pipeline_test.json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0
        
        # Load generated JSON
        with open("pipeline_test.json", 'r') as f:
            c_model = json.load(f)
        
        # Validate compatibility with UML pipeline expectations
        elements = c_model['elements']
        
        for element_name, element in elements.items():
            if element.get('is_struct'):
                # Should have all required fields for UML processing
                required_fields = ['name', 'namespace', 'kind', 'members', 'methods', 'source_location']
                for field in required_fields:
                    assert field in element, f"Element {element_name} missing required field: {field}"
                
                # Source location should have file and line
                src_loc = element['source_location']
                assert 'file' in src_loc and 'line' in src_loc
                
                # Members should have proper structure
                for member in element['members']:
                    assert 'name' in member and 'type' in member
                    assert 'access' in member and 'is_static' in member
                
                # Methods should have proper structure  
                for method in element['methods']:
                    assert 'name' in method and 'return_type' in method
                    assert 'access' in method and 'is_static' in method
                    assert 'parameters' in method
                    
                    # Parameters should have name and type
                    for param in method['parameters']:
                        assert 'name' in param and 'type' in param
        
        print("✅ JSON format fully compatible with existing UML pipeline")
        
        # Cleanup
        Path("pipeline_test.json").unlink(missing_ok=True)


class TestC2UMLMethodBindingAccuracy:
    """Test accuracy of method binding in real scenarios"""
    
    def test_binding_accuracy_with_complex_c_code(self):
        """Test binding accuracy with complex C patterns"""
        
        # Create more complex C test case
        complex_c_code = '''
        typedef struct {
            float x, y, z;
        } Vector3;
        
        typedef struct {
            Vector3 position;
            Vector3 velocity;
            float mass;
        } Particle;
        
        // Vector3 methods (should be bound)
        void vector3_add(Vector3* result, const Vector3* a, const Vector3* b);
        float vector3_length(const Vector3* v);
        void vector3_normalize(Vector3* v);
        
        // Particle methods (should be bound)
        void particle_update(Particle* p, float dt);
        void particle_apply_force(Particle* p, const Vector3* force);
        
        // Factory functions (should NOT be bound)
        Vector3 vector3_create(float x, float y, float z);
        Particle particle_create(Vector3 pos, float mass);
        
        // Utility functions (should NOT be bound)
        float clamp(float value, float min, float max);
        void system_init();
        '''
        
        # Write to temp file
        temp_c_file = Path("temp_complex.c")
        with open(temp_c_file, 'w') as f:
            f.write(complex_c_code)
        
        try:
            import subprocess
            
            cmd = [sys.executable, "c2uml.py", str(temp_c_file), "complex_test.json", "--verbose"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            assert result.returncode == 0
            
            # Load and analyze results
            with open("complex_test.json", 'r') as f:
                model = json.load(f)
            
            elements = model['elements']
            
            # Should have Vector3 and Particle structs
            assert 'Vector3' in elements
            assert 'Particle' in elements
            
            # Check Vector3 binding
            vector3 = elements['Vector3']
            vector3_methods = [m['name'] for m in vector3['methods']]
            expected_vector3 = ['vector3_add', 'vector3_length', 'vector3_normalize']
            
            for expected in expected_vector3:
                assert expected in vector3_methods, f"Vector3 should have {expected}"
            
            # Check Particle binding
            particle = elements['Particle']
            particle_methods = [m['name'] for m in particle['methods']]
            expected_particle = ['particle_update', 'particle_apply_force']
            
            for expected in expected_particle:
                assert expected in particle_methods, f"Particle should have {expected}"
            
            # Check unbound functions
            if 'UtilityFunctions' in elements:
                utility = elements['UtilityFunctions']
                utility_methods = [m['name'] for m in utility['methods']]
                
                # Factory and utility functions should be unbound
                expected_unbound = ['vector3_create', 'particle_create', 'clamp', 'system_init']
                for expected in expected_unbound:
                    assert expected in utility_methods, f"Utility should have {expected}"
            
            # Check binding statistics
            metadata = model['_metadata']
            binding_stats = metadata['binding_stats']
            
            # Should have good binding ratio for well-structured C code
            assert binding_stats['bound_functions'] >= 5
            assert binding_stats['bound_functions'] / binding_stats['total_functions'] >= 0.5
            
            print(f"✅ Complex C code binding: {binding_stats['bound_functions']}/{binding_stats['total_functions']} functions bound")
            
        finally:
            # Cleanup
            temp_c_file.unlink(missing_ok=True)
            Path("complex_test.json").unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
