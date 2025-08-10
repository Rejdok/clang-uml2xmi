#!/usr/bin/env python3
"""
Base types and generic classes for UML2Papyrus project.
"""

from typing import (
    Dict, List, Tuple, Optional, Set, Union, Literal, 
    NewType, Generic, TypeVar, TypedDict, Protocol, Any
)

# ---------- Generic type variables ----------
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# ---------- Generic collection types ----------
class TypedList(List[T], Generic[T]):
    """A type-safe list that maintains type information."""
    pass

class TypedDict(Dict[K, V], Generic[K, V]):
    """A type-safe dictionary that maintains type information."""
    pass

# ---------- Common type aliases ----------
XmlValue = Union[str, int, float, bool, None]
