#!/usr/bin/env python3
"""
Types module for UML2Papyrus project.
Centralized type definitions organized by domain.
"""

# Public types export
from .base import (
    T, K, V,
    TypedList, TypedDict,
    XmlValue
)

from .uml import (
    ElementKind, Visibility, AggregationType, Direction,
    XmiId, ElementName, TypeName, Multiplicity,
    Namespace, AttributeName, ElementType, MultiplicityValue,
    InheritanceType, InheritanceModifier
)

from .cpp import (
    TypeToken, TypeAnalysis, TypeString, TemplateArgs,
    RawElementData, RawMemberData, RawOperationData,
    RawTemplateData, RawEnumeratorData, RawUnderlyingTypeData,
    RawBaseClassData, RawInheritanceData
)

from .xml import (
    ContextStack, ElementAttributes, ModelName, ModelId,
    IdString, HashString
)

from .protocols import (
    XmlElement, BuildResult, TypeAnalysisResult
)

__all__ = [
    # Base types
    'T', 'K', 'V', 'TypedList', 'TypedDict', 'XmlValue',
    
    # UML types
    'ElementKind', 'Visibility', 'AggregationType', 'Direction',
    'XmiId', 'ElementName', 'TypeName', 'Multiplicity',
    'Namespace', 'AttributeName', 'ElementType', 'MultiplicityValue',
    'InheritanceType', 'InheritanceModifier',
    
    # C++ types
    'TypeToken', 'TypeAnalysis', 'TypeString', 'TemplateArgs',
    'RawElementData', 'RawMemberData', 'RawOperationData',
    'RawTemplateData', 'RawEnumeratorData', 'RawUnderlyingTypeData',
    'RawBaseClassData', 'RawInheritanceData',
    
    # XML types
    'ContextStack', 'ElementAttributes', 'ModelName', 'ModelId',
    'IdString', 'HashString',
    
    # Protocols
    'XmlElement', 'BuildResult', 'TypeAnalysisResult'
]
