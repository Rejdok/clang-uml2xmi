#!/usr/bin/env python3
"""
C++-specific types for UML2Papyrus project.
"""

from typing import Dict, List, Union, Any, NewType

# ---------- Type aliases for C++ parsing ----------
TypeToken = Dict[str, str]
TypeAnalysis = Dict[str, Union[str, bool, List[str], None]]
TypeString = NewType('TypeString', str)
TemplateArgs = NewType('TemplateArgs', List[str])

# ---------- Type aliases for model building ----------
RawElementData = Dict[str, Any]
RawMemberData = Dict[str, Any]
RawOperationData = Dict[str, Any]
RawTemplateData = Union[Dict[str, Any], str]
RawEnumeratorData = Union[Dict[str, Any], str]
RawUnderlyingTypeData = Union[Dict[str, Any], str]

# ---------- New types for inheritance handling ----------
RawBaseClassData = Union[Dict[str, Any], str]
RawInheritanceData = List[RawBaseClassData]
