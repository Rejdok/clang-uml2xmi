"""
Adapters for clang-uml JSON output shared across languages (C/C++).

Currently re-exporting the existing parser; real migration can move code here.
"""

from .parser import CppTypeParser

__all__ = ["CppTypeParser"]


