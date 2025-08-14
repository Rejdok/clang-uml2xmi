#!/usr/bin/env python3
"""
Complete Pipeline: Compilation Database to XMI

Generates full XMI files from compile_commands.json including build structure.
"""

import sys
import os
import argparse
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compilation_database import analyze_compile_commands
from core.build_uml_generator import generate_build_uml, print_build_structure_summary
from gen.xmi.generator import XmiGenerator
from gen.xmi.build_structure_extension import save_build_profile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Generate complete XMI from compilation database')
    parser.add_argument('compile_commands', help='Path to compile_commands.json file')
    parser.add_argument('--output', '-o', help='Output XMI file path', default='output/build_structure.uml')
    parser.add_argument('--project-name', help='Project name for XMI', default='BuildStructure')
    parser.add_argument('--profile', help='Generate UML profile for build stereotypes', action='store_true')
    parser.add_argument('--summary', help='Print build structure summary', action='store_true')
    parser.add_argument('--pretty', help='Pretty-print XML output', action='store_true')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.compile_commands):
        print(f"❌ Error: File not found: {args.compile_commands}")
        sys.exit(1)
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        print(f"🔍 Analyzing compilation database: {args.compile_commands}")
        
        # Step 1: Analyze compilation database
        analysis_result = analyze_compile_commands(args.compile_commands)
        print(f"✅ Analysis completed")
        
        # Step 2: Generate UML model with build structure
        print("🏗️  Generating UML model with build structure...")
        uml_model = generate_build_uml(analysis_result)
        print(f"✅ Generated UML model with {len(uml_model.elements)} elements")
        
        # Step 3: Generate XMI file
        print(f"📝 Generating XMI file: {args.output}")
        xmi_generator = XmiGenerator(uml_model)
        xmi_generator.write(str(output_path), args.project_name, pretty=args.pretty)
        print(f"✅ XMI file generated: {args.output}")
        
        # Optional: Print summary
        if args.summary:
            if 'build_targets_analysis' in analysis_result:
                from core.build_uml_generator import BuildUmlGenerator
                generator = BuildUmlGenerator()
                build_model = generator.generate_from_analysis(analysis_result)
                print_build_structure_summary(build_model)
        
        # Optional: Generate UML profile
        if args.profile:
            profile_path = output_path.parent / 'BuildProfile.profile.uml'
            print(f"📝 Generating UML profile: {profile_path}")
            save_build_profile(str(profile_path))
            print(f"✅ Build profile saved to: {profile_path}")
        
        # Generate summary file
        summary_path = output_path.parent / f"{output_path.stem}_summary.txt"
        _generate_summary_file(uml_model, analysis_result, str(summary_path))
        print(f"📄 Summary saved to: {summary_path}")
        
        print(f"\n🎉 Complete! Generated XMI with build structure from compilation database")
        print(f"   📁 XMI file: {args.output}")
        print(f"   📄 Summary: {summary_path}")
        if args.profile:
            print(f"   🏷️  Profile: {profile_path}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Failed to generate XMI: {e}", exc_info=True)
        sys.exit(1)

def _generate_summary_file(uml_model, analysis_result, summary_path):
    """Generate summary file with detailed information"""
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("COMPILATION DATABASE TO XMI CONVERSION SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        
        # UML Model Stats
        f.write("UML MODEL STATISTICS:\n")
        f.write("-" * 30 + "\n")
        f.write(f"Total Elements: {len(uml_model.elements)}\n")
        f.write(f"Total Associations: {len(uml_model.associations)}\n")
        f.write(f"Total Dependencies: {len(uml_model.dependencies)}\n")
        f.write(f"Total Generalizations: {len(uml_model.generalizations)}\n\n")
        
        # Build Structure Analysis
        if 'build_targets_analysis' in analysis_result:
            build_analysis = analysis_result['build_targets_analysis']
            
            f.write("BUILD STRUCTURE ANALYSIS:\n")
            f.write("-" * 30 + "\n")
            
            targets = build_analysis.get('build_targets', {})
            artifacts = build_analysis.get('file_artifacts', {})
            
            f.write(f"Build Targets: {len(targets)}\n")
            f.write(f"Source Files: {len(artifacts)}\n\n")
            
            # Targets detail
            f.write("BUILD TARGETS:\n")
            for name, target in targets.items():
                f.write(f"  {name} ({target.get('type', 'unknown')}):\n")
                f.write(f"    Output: {target.get('output_file', 'unknown')}\n")
                f.write(f"    Build Order: {target.get('build_order', 'unknown')}\n")
                f.write(f"    Source Files: {len(target.get('source_files', []))}\n")
                if target.get('dependencies'):
                    f.write(f"    Dependencies: {', '.join(target['dependencies'])}\n")
                f.write("\n")
            
            # Files detail
            f.write("SOURCE FILES:\n")
            for name, artifact in artifacts.items():
                f.write(f"  {name}:\n")
                f.write(f"    Path: {artifact.get('path', 'unknown')}\n")
                f.write(f"    Object: {artifact.get('object_file', 'none')}\n")
                if artifact.get('compile_flags'):
                    flags = artifact['compile_flags'][:3]  # First 3 flags
                    f.write(f"    Flags: {' '.join(flags)}")
                    if len(artifact['compile_flags']) > 3:
                        f.write(f" ... (+{len(artifact['compile_flags'])-3} more)")
                    f.write("\n")
                f.write("\n")
        
        # UML Elements Detail
        f.write("UML ELEMENTS GENERATED:\n")
        f.write("-" * 30 + "\n")
        
        packages = []
        artifacts = []
        other = []
        
        for xmi_id, element in uml_model.elements.items():
            element_info = {
                'id': str(xmi_id),
                'name': element.name,
                'kind': element.kind.value,
                'namespace': element.namespace
            }
            
            if element.kind.value == 'package':
                packages.append(element_info)
            elif element.kind.value == 'artifact':
                artifacts.append(element_info)
            else:
                other.append(element_info)
        
        # Packages
        if packages:
            f.write(f"Packages ({len(packages)}):\n")
            for pkg in packages:
                f.write(f"  {pkg['name']} (ID: {pkg['id'][:8]}...)\n")
                if pkg['namespace']:
                    f.write(f"    Namespace: {pkg['namespace']}\n")
            f.write("\n")
        
        # Artifacts
        if artifacts:
            f.write(f"Artifacts ({len(artifacts)}):\n")
            for art in artifacts:
                f.write(f"  {art['name']} (ID: {art['id'][:8]}...)\n")
                if art['namespace']:
                    f.write(f"    Namespace: {art['namespace']}\n")
            f.write("\n")
        
        # Other elements
        if other:
            f.write(f"Other Elements ({len(other)}):\n")
            for elem in other:
                f.write(f"  {elem['name']} ({elem['kind']}) (ID: {elem['id'][:8]}...)\n")
            f.write("\n")

if __name__ == "__main__":
    main()
