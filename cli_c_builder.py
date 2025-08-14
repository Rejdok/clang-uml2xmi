#!/usr/bin/env python3
"""
CLI interface for C Model Builder

Usage:
    python cli_c_builder.py source.c output.json [--strategy explicit] [--format json]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.c_model_builder import build_c_model_from_sources, CModelBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Build UML model from C source code with method binding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage - C source to JSON  
    python cli_c_builder.py src/point.c output.json
    
    # Multiple C files
    python cli_c_builder.py src/*.c model.json
    
    # Direct UML model output
    python cli_c_builder.py src/point.c --format uml
    
    # Explicit strategy (no auto-detection)
    python cli_c_builder.py src/point.c output.json --strategy explicit

Method Binding Rules:
    - Functions bound to structs by first argument type
    - point_move(Point* p, ...) → Point::move(...)
    - Utility functions → UtilityFunctions class
    - Factory functions stay unbound (first arg not struct pointer)
        """)
    
    parser.add_argument('sources', nargs='+', help='C source files to process')
    parser.add_argument('output', help='Output file path')
    
    parser.add_argument('--format', choices=['json', 'uml'], default='json',
                       help='Output format: json (clang-uml compatible) or uml (direct UML model)')
    
    parser.add_argument('--strategy', choices=['explicit'], default='explicit',
                       help='Processing strategy (explicit=no auto-detection heuristics)')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output with binding statistics')
    
    parser.add_argument('--show-unbound', action='store_true', 
                       help='Show unbound functions in output')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.format == 'json' and not args.output:
        parser.error("Output file required for JSON format")
    
    # Validate source files exist
    source_files = []
    for source_pattern in args.sources:
        source_path = Path(source_pattern)
        if source_path.exists():
            source_files.append(str(source_path))
        else:
            print(f"Warning: Source file not found: {source_pattern}")
    
    if not source_files:
        parser.error("No valid source files found")
    
    # Build model
    print(f"🚨 C MODEL BUILDER (FALLBACK) - Processing {len(source_files)} files")
    print("📋 Strategy: explicit (no auto-detection heuristics)")
    
    try:
        result = build_c_model_from_sources(source_files, output_format=args.format)
        
        # Show binding statistics if verbose
        if args.verbose and 'binding_report' in result:
            report = result['binding_report']
            print(f"\n📊 METHOD BINDING STATISTICS:")
            print(f"  Total functions: {report['binding_stats']['total_functions']}")
            print(f"  Bound functions: {report['binding_stats']['bound_functions']}")
            print(f"  Unbound functions: {report['binding_stats']['unbound_functions']}")
            print(f"  Binding ratio: {report['binding_ratio']:.1%}")
            print(f"  Structs with methods: {report['structs_with_methods']}/{report['total_structs']}")
        
        # Output results
        if args.format == 'json':
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result['elements'], f, indent=2, ensure_ascii=False)
            print(f"✅ JSON model written to: {args.output}")
            
            if args.show_unbound and 'binding_report' in result:
                unbound_count = result['binding_report']['binding_stats']['unbound_functions']
                if unbound_count > 0:
                    print(f"⚠️  {unbound_count} unbound functions (utility functions)")
        
        elif args.format == 'uml':
            uml_model = result['uml_model']
            print(f"✅ UML model generated with {len(uml_model.elements)} elements")
            if args.output:
                # TODO: Serialize UML model to file if needed
                print(f"📝 UML model details available (serialization not implemented)")
        
        print("🎯 C model building completed successfully")
        
    except Exception as e:
        print(f"❌ Error building C model: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
