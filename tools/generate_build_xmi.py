#!/usr/bin/env python3
"""
Build Structure XMI Generator Tool

Generates XMI files with build structure information from compilation database.
"""

import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compilation_database import analyze_compile_commands
from core.build_uml_generator import generate_build_uml, print_build_structure_summary
from gen.xmi.build_structure_extension import save_build_profile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Generate XMI with build structure from compilation database')
    parser.add_argument('compile_commands', help='Path to compile_commands.json file')
    parser.add_argument('--output', '-o', help='Output directory for XMI files', default='output')
    parser.add_argument('--profile', help='Generate UML profile for build stereotypes', action='store_true')
    parser.add_argument('--summary', help='Print build structure summary', action='store_true')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.compile_commands):
        print(f"❌ Error: File not found: {args.compile_commands}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    print(f"🔍 Analyzing compilation database: {args.compile_commands}")
    
    try:
        # Analyze compilation database
        analysis_result = analyze_compile_commands(args.compile_commands)
        
        # Generate UML model with build structure
        print("🏗️  Generating UML model with build structure...")
        uml_model = generate_build_uml(analysis_result)
        
        print(f"✅ Generated UML model with {len(uml_model.elements)} elements")
        
        # Print summary if requested
        if args.summary:
            if 'build_targets_analysis' in analysis_result:
                from core.build_uml_generator import BuildUmlGenerator
                generator = BuildUmlGenerator()
                build_model = generator.generate_from_analysis(analysis_result)
                print_build_structure_summary(build_model)
        
        # Generate UML profile if requested
        if args.profile:
            profile_path = os.path.join(args.output, 'BuildProfile.profile.uml')
            print(f"📝 Generating UML profile: {profile_path}")
            save_build_profile(profile_path)
            print(f"✅ Build profile saved to: {profile_path}")
        
        # Save UML model structure (for debugging)
        model_info_path = os.path.join(args.output, 'build_model_info.txt')
        with open(model_info_path, 'w', encoding='utf-8') as f:
            f.write("BUILD STRUCTURE UML MODEL INFORMATION\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Total Elements: {len(uml_model.elements)}\n")
            f.write(f"Total Associations: {len(uml_model.associations)}\n")
            f.write(f"Total Dependencies: {len(uml_model.dependencies)}\n")
            f.write(f"Total Generalizations: {len(uml_model.generalizations)}\n\n")
            
            f.write("ELEMENTS:\n")
            f.write("-" * 20 + "\n")
            
            for xmi_id, element in uml_model.elements.items():
                f.write(f"ID: {xmi_id}\n")
                f.write(f"Name: {element.name}\n") 
                f.write(f"Kind: {element.kind.value}\n")
                f.write(f"Namespace: {element.namespace}\n")
                
                if hasattr(element, 'original_data') and element.original_data:
                    f.write("Build Data:\n")
                    for key, value in element.original_data.items():
                        if isinstance(value, list):
                            f.write(f"  {key}: {', '.join(map(str, value))}\n")
                        else:
                            f.write(f"  {key}: {value}\n")
                
                f.write("\n")
        
        print(f"📄 Model information saved to: {model_info_path}")
        
        # Note: Full XMI generation would require integrating with existing XMI generator
        print("🚧 Note: Full XMI file generation requires integration with existing XMI generator")
        print("    The UML model structure has been generated and can be used by XMI generators")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Failed to generate build XMI: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
