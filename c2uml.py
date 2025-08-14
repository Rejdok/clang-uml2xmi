#!/usr/bin/env python3
"""
C to UML Model Builder with Method Binding

✅ PRODUCTION-READY C language processor
Uses clang-uml for accurate struct parsing + method binding by first argument type

Usage:
    python c2uml.py source.c output.json
    python c2uml.py src/*.c model.json --verbose
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.c_hybrid_builder import build_c_model_hybrid


def main():
    parser = argparse.ArgumentParser(
        description="Build UML model from C source code with intelligent method binding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Method Binding Rules (C Language):
    ✅ Functions bound to structs by first argument type:
       void point_move(Point* p, int dx, int dy) → Point::move(dx, dy)
       void point_print(const Point* p)          → Point::print()
    
    ✅ Factory functions stay unbound:
       Point point_create(int x, int y)          → UtilityFunctions::point_create(x, y)
    
    ✅ Utility functions stay unbound:
       int max(int a, int b)                     → UtilityFunctions::max(a, b)

Processing Strategy:
    ✅ clang-uml for accurate struct parsing (no regex brittleness)
    ✅ Lightweight function parsing for method binding
    ✅ Explicit strategy (no auto-detection heuristics)
    ✅ JSON format compatible with existing UML pipeline

Examples:
    # Single C file
    python c2uml.py src/point.c point_model.json
    
    # Multiple C files  
    python c2uml.py src/point.c src/rect.c geometry_model.json
    
    # With verbose binding statistics
    python c2uml.py src/*.c model.json --verbose --show-unbound
        """)
    
    parser.add_argument('sources', nargs='+', help='C source files (.c, .h) to process')
    parser.add_argument('output', help='Output JSON file path')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed binding statistics')
    
    parser.add_argument('--show-unbound', action='store_true',
                       help='List unbound utility functions')
    
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Minimal output')
    
    args = parser.parse_args()
    
    # Validate source files
    source_files = []
    for source_pattern in args.sources:
        source_path = Path(source_pattern)
        if source_path.exists():
            if source_path.suffix in ['.c', '.h']:
                source_files.append(str(source_path.absolute()))
            else:
                print(f"⚠️  Skipping non-C file: {source_pattern}")
        else:
            print(f"❌ Source file not found: {source_pattern}")
    
    if not source_files:
        parser.error("No valid C source files found")
    
    # Build C model
    if not args.quiet:
        print(f"🚀 C2UML: Processing {len(source_files)} C files")
        print("✅ Using clang-uml + method binding (production-ready)")
    
    try:
        result = build_c_model_hybrid(source_files, args.output)
        
        # Show statistics
        if args.verbose and '_metadata' in result:
            metadata = result['_metadata']
            binding_stats = metadata.get('binding_stats', {})
            
            print(f"\n📊 METHOD BINDING STATISTICS:")
            print(f"  📁 Source files: {len(metadata.get('source_files', []))}")
            print(f"  🔧 Total functions: {binding_stats.get('total_functions', 0)}")
            print(f"  🔗 Bound functions: {binding_stats.get('bound_functions', 0)}")
            print(f"  📦 Unbound functions: {binding_stats.get('unbound_functions', 0)}")
            print(f"  📈 Binding ratio: {binding_stats.get('bound_functions', 0) / max(binding_stats.get('total_functions', 1), 1):.1%}")
            print(f"  ⚠️  Binding conflicts: {binding_stats.get('binding_conflicts', 0)}")
        
        # Show unbound functions
        if args.show_unbound and 'UtilityFunctions' in result.get('elements', {}):
            utility = result['elements']['UtilityFunctions']
            unbound_methods = utility.get('methods', [])
            
            if unbound_methods:
                print(f"\n📋 UNBOUND FUNCTIONS ({len(unbound_methods)}):")
                for method in unbound_methods:
                    params = [f"{p['type']} {p['name']}" for p in method.get('parameters', [])]
                    signature = f"{method['return_type']} {method['name']}({', '.join(params)})"
                    print(f"  • {signature}")
        
        # Show struct summary
        elements = result.get('elements', {})
        struct_count = len([e for e in elements.values() if e.get('is_struct')])
        
        if not args.quiet:
            print(f"\n✅ C MODEL GENERATED SUCCESSFULLY:")
            print(f"  📁 Output: {args.output}")
            print(f"  🏗️  Structs: {struct_count}")
            print(f"  🔗 Method binding applied")
            print(f"  📋 Format: clang-uml compatible JSON")
        
    except Exception as e:
        print(f"❌ C model generation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
