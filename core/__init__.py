#!/usr/bin/env python3
"""
Core module initialization with centralized path management.

This module handles project-wide path configuration to eliminate 
sys.path.insert scattered across files.
"""

import sys
from pathlib import Path

# Single point of path configuration  
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Re-export commonly used core components
from .uml_model import UmlModel, UmlElement, UmlMember, UmlOperation, ElementName, XmiId, ClangMetadata

__all__ = [
    'UmlModel', 'UmlElement', 'UmlMember', 'UmlOperation', 
    'ElementName', 'XmiId', 'ClangMetadata'
]