#!/usr/bin/env python3
"""
Test script for Build UML Generator
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compilation_database import analyze_compile_commands
from core.build_uml_generator import generate_build_uml, print_build_structure_summary

def test_build_uml_generation():
    """Test Build UML generation on real compilation database"""
    
    # Use our test compile commands
    compile_db_path = "tests/assets/test_c_project/build_targets_compile_commands.json"
    
    print("🔍 Analyzing compilation database...")
    analysis_result = analyze_compile_commands(compile_db_path)
    
    print("🏗️  Generating Build UML...")
    uml_model = generate_build_uml(analysis_result)
    
    print(f"✅ Generated UML model with {len(uml_model.elements)} elements")
    
    # Print details of generated elements
    print("\n📦 UML Elements Generated:")
    for xmi_id, element in uml_model.elements.items():
        stereotype = ""
        if hasattr(element, 'original_data') and element.original_data:
            stereotype = f" <<{element.original_data.get('stereotype', '')}>>"
        
        print(f"   {element.name}{stereotype} ({element.kind.value})")
        if element.namespace:
            print(f"      Namespace: {element.namespace}")
        if hasattr(element, 'original_data') and element.original_data:
            if 'target_type' in element.original_data:
                print(f"      Target Type: {element.original_data['target_type']}")
            if 'output_file' in element.original_data:
                print(f"      Output: {element.original_data['output_file']}")
            if 'file_path' in element.original_data:
                print(f"      File Path: {element.original_data['file_path']}")
    
    # Test build structure summary
    if 'build_targets_analysis' in analysis_result:
        from core.build_uml_generator import BuildUmlGenerator
        generator = BuildUmlGenerator()
        build_model = generator.generate_from_analysis(analysis_result)
        print_build_structure_summary(build_model)
    
    return uml_model

if __name__ == "__main__":
    model = test_build_uml_generation()
    print(f"\n🎉 Test completed! Generated {len(model.elements)} UML elements.")
