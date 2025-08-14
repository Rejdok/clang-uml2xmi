#!/usr/bin/env python3
"""
Compilation Database Analyzer CLI

This tool analyzes compile_commands.json files to reconstruct library structure,
dependencies, and project organization.

Usage:
    python analyze_compile_db.py <compile_commands.json>
    python analyze_compile_db.py --project <project_directory>
    python analyze_compile_db.py --output <output_file.json>
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.compilation_database import (
    analyze_compile_commands, 
    find_compile_commands,
    CompilationDatabaseParser,
    LibraryStructureReconstructor
)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze compile_commands.json to reconstruct library structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific compile_commands.json file
  python analyze_compile_db.py compile_commands.json
  
  # Find and analyze compile_commands.json in project directory
  python analyze_compile_db.py --project /path/to/project
  
  # Save analysis results to file
  python analyze_compile_db.py --output analysis.json compile_commands.json
  
  # Verbose output with detailed information
  python analyze_compile_db.py --verbose compile_commands.json
        """
    )
    
    parser.add_argument(
        'compile_commands',
        nargs='?',
        help='Path to compile_commands.json file'
    )
    
    parser.add_argument(
        '--project', '-p',
        help='Project directory to search for compile_commands.json'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file for analysis results (JSON format)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output with detailed information'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'summary', 'tree'],
        default='summary',
        help='Output format (default: summary)'
    )
    
    args = parser.parse_args()
    
    # Determine compile_commands.json path
    compile_db_path = None
    
    if args.compile_commands:
        compile_db_path = args.compile_commands
    elif args.project:
        compile_db_path = find_compile_commands(args.project)
        if not compile_db_path:
            print(f"❌ No compile_commands.json found in {args.project}")
            print("Common locations:")
            print("  - project_root/compile_commands.json")
            print("  - project_root/build/compile_commands.json")
            print("  - project_root/.cmake/compile_commands.json")
            return 1
    else:
        # Try to find in current directory
        compile_db_path = find_compile_commands(".")
        if not compile_db_path:
            print("❌ No compile_commands.json found")
            print("Please specify a file path or use --project option")
            return 1
    
    print(f"🔍 Analyzing compilation database: {compile_db_path}")
    
    try:
        # Analyze the compilation database
        analysis_result = analyze_compile_commands(compile_db_path)
        
        # Output results
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            print(f"✅ Analysis results saved to: {args.output}")
        
        # Display results
        display_analysis(analysis_result, args.format, args.verbose)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error analyzing compilation database: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

def display_analysis(analysis: dict, format_type: str, verbose: bool):
    """Display analysis results in specified format"""
    
    if format_type == 'json':
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return
    
    if format_type == 'summary':
        display_summary(analysis, verbose)
    elif format_type == 'tree':
        display_tree(analysis, verbose)

def display_summary(analysis: dict, verbose: bool):
    """Display summary of analysis results"""
    
    print("\n" + "="*60)
    print("📊 COMPILATION DATABASE ANALYSIS SUMMARY")
    print("="*60)
    
    # Project info
    project_info = analysis['project_info']
    print(f"\n🏗️  PROJECT STRUCTURE:")
    print(f"   Source directories: {len(project_info['source_directories'])}")
    print(f"   Total source files: {project_info['total_source_files']}")
    print(f"   Include paths: {project_info['total_include_paths']}")
    print(f"   Libraries: {project_info['total_libraries']}")
    
    if verbose:
        for directory in project_info['source_directories']:
            print(f"     📁 {directory}")
    
    # Source structure
    source_structure = analysis['source_structure']
    print(f"\n📁 SOURCE FILES:")
    for ext, count in source_structure['file_types'].items():
        print(f"   {ext}: {count} files")
    
    # Include hierarchy
    include_hierarchy = analysis['include_hierarchy']
    print(f"\n📚 INCLUDE PATHS:")
    print(f"   System includes: {len(include_hierarchy['system_includes'])}")
    print(f"   Project includes: {len(include_hierarchy['project_includes'])}")
    print(f"   External includes: {len(include_hierarchy['external_includes'])}")
    
    if verbose:
        if include_hierarchy['project_includes']:
            print("     Project includes:")
            for path in include_hierarchy['project_includes'][:5]:  # Show first 5
                print(f"       📂 {path}")
            if len(include_hierarchy['project_includes']) > 5:
                print(f"       ... and {len(include_hierarchy['project_includes']) - 5} more")
        
        if include_hierarchy['external_includes']:
            print("     External includes:")
            for path in include_hierarchy['external_includes'][:5]:  # Show first 5
                print(f"       📂 {path}")
            if len(include_hierarchy['external_includes']) > 5:
                print(f"       ... and {len(include_hierarchy['external_includes']) - 5} more")
    
    # Library dependencies
    library_deps = analysis['library_dependencies']
    print(f"\n🔗 LIBRARY DEPENDENCIES:")
    print(f"   System libraries: {len(library_deps['system_libraries'])}")
    print(f"   External libraries: {len(library_deps['external_libraries'])}")
    
    if verbose:
        if library_deps['system_libraries']:
            print("     System libraries:")
            for lib in library_deps['system_libraries']:
                print(f"       📚 {lib}")
        
        if library_deps['external_libraries']:
            print("     External libraries:")
            for lib in library_deps['external_libraries']:
                print(f"       📚 {lib}")
    
    # Build configuration
    build_config = analysis['build_configuration']
    if build_config:
        print(f"\n⚙️  BUILD CONFIGURATION:")
        for key, value in build_config.items():
            print(f"   {key}: {value}")
    
    # Dependencies
    dependencies = analysis['dependency_graph']
    if dependencies['file_dependencies']:
        print(f"\n🔗 FILE DEPENDENCIES:")
        print(f"   Files with dependencies: {len(dependencies['file_dependencies'])}")
        
        if verbose:
            for file_name, deps in list(dependencies['file_dependencies'].items())[:5]:
                print(f"     📄 {file_name} -> {len(deps)} dependencies")
                if deps:
                    for dep in list(deps)[:3]:  # Show first 3
                        print(f"       └─ {dep}")
                    if len(deps) > 3:
                        print(f"       └─ ... and {len(deps) - 3} more")
            if len(dependencies['file_dependencies']) > 5:
                print(f"     ... and {len(dependencies['file_dependencies']) - 5} more files")

def display_tree(analysis: dict, verbose: bool):
    """Display analysis results in tree format"""
    
    print("\n" + "="*60)
    print("🌳 PROJECT STRUCTURE TREE")
    print("="*60)
    
    project_info = analysis['project_info']
    source_structure = analysis['source_structure']
    
    print(f"\n📁 PROJECT ROOT")
    
    # Source directories
    for directory in project_info['source_directories']:
        print(f"   📁 {Path(directory).name}/")
        
        # Files in this directory
        if directory in source_structure['directory_structure']:
            files = source_structure['directory_structure'][directory]
            for file_name in sorted(files):
                file_path = Path(file_name)
                ext = file_path.suffix
                if ext in ['.c', '.cpp', '.cc', '.cxx']:
                    print(f"      📄 {file_name}")
                elif ext in ['.h', '.hpp', '.hh', '.hxx']:
                    print(f"      📋 {file_name}")
                else:
                    print(f"      📎 {file_name}")
    
    # Include paths
    include_hierarchy = analysis['include_hierarchy']
    if include_hierarchy['project_includes']:
        print(f"\n📚 PROJECT INCLUDE PATHS")
        for path in include_hierarchy['project_includes']:
            print(f"   📂 {path}")
    
    if include_hierarchy['external_includes']:
        print(f"\n🌐 EXTERNAL INCLUDE PATHS")
        for path in include_hierarchy['external_includes']:
            print(f"   📂 {path}")
    
    # Libraries
    library_deps = analysis['library_dependencies']
    if library_deps['external_libraries']:
        print(f"\n🔗 EXTERNAL LIBRARIES")
        for lib in library_deps['external_libraries']:
            print(f"   📚 {lib}")

if __name__ == "__main__":
    sys.exit(main())
