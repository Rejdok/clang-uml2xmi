#!/usr/bin/env python3
"""
Integration layer for C++ Metadata with existing UML codebase

⚠️  TEMPORARY FALLBACK INTEGRATION ⚠️
This module integrates the C++ metadata system with existing codebase.
Will be replaced when we migrate to clang-uml C++ library integration.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
import logging

from core.cpp_metadata import (
    CppElement, CppMetadata, CppTemplateData, BidirectionalConverter, 
    CppProfileRegistry, TemplateSyncStrategy, RawTemplateParam, UMLTemplateParameter
)
from core.uml_model import UmlElement, UmlModel, ElementName, XmiId
from uml_types import ElementKind

logger = logging.getLogger(__name__)

# ===============================================
# INTEGRATION WITH EXISTING UML MODEL
# ===============================================

class EnhancedUmlElement(UmlElement):
    """Extended UmlElement with C++ metadata support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add C++ metadata layer
        self.cpp_metadata: Optional[CppMetadata] = None
        self.bidirectional_state: str = "clean"  # "clean", "modified", "conflicted"
    
    def has_cpp_metadata(self) -> bool:
        return self.cpp_metadata is not None
    
    def is_cpp_template(self) -> bool:
        return (self.cpp_metadata and 
                self.cpp_metadata.template_data and 
                len(self.cpp_metadata.template_data.uml_parameters) > 0)
    
    def get_clean_template_params(self) -> List[str]:
        """Get clean template parameter names for UML Editor"""
        if not self.is_cpp_template():
            return []
        
        return [param.name for param in self.cpp_metadata.template_data.uml_parameters]
    
    def get_cpp_code_fragment(self) -> str:
        """Generate C++ code fragment for this element"""
        if not self.cpp_metadata:
            return f"// No C++ metadata for {self.name}"
        
        converter = BidirectionalConverter()
        cpp_element = CppElement(uml_element=self, cpp_metadata=self.cpp_metadata)
        return converter.generate_cpp_code(cpp_element)

class CppEnhancedModelBuilder:
    """🚨 FALLBACK: Enhanced model builder with C++ metadata processing"""
    
    def __init__(self, profile_registry: Optional[CppProfileRegistry] = None):
        self.converter = BidirectionalConverter(profile_registry)
        self.profile_registry = profile_registry or CppProfileRegistry()
        
    def build_enhanced_model(self, raw_elements: Dict[ElementName, Dict[str, Any]]) -> UmlModel:
        """Build UML model with C++ metadata from clang-uml JSON"""
        
        enhanced_elements = {}
        name_to_xmi = {}
        
        for name, raw_data in raw_elements.items():
            try:
                # Create enhanced element with C++ metadata
                enhanced_element = self._create_enhanced_element(name, raw_data)
                
                enhanced_elements[enhanced_element.xmi] = enhanced_element
                name_to_xmi[name] = enhanced_element.xmi
                
            except Exception as e:
                logger.error(f"Failed to process element {name}: {e}")
                # Fallback to basic element creation
                basic_element = self._create_basic_element(name, raw_data)
                enhanced_elements[basic_element.xmi] = basic_element
                name_to_xmi[name] = basic_element.xmi
        
        # TODO: Process associations, dependencies, generalizations with C++ metadata
        return UmlModel(
            elements=enhanced_elements,
            associations=[],
            dependencies=[],  
            generalizations=[],
            name_to_xmi=name_to_xmi
        )
    
    def _create_enhanced_element(self, name: ElementName, raw_data: Dict[str, Any]) -> EnhancedUmlElement:
        """Create enhanced UML element with C++ metadata"""
        
        # Extract C++ metadata using bidirectional converter
        cpp_metadata = self.converter._extract_cpp_metadata(raw_data)
        
        # Process templates with fallback strategies  
        if raw_data.get('template_parameters') or raw_data.get('is_template'):
            cpp_metadata.template_data = self.converter._process_templates_with_fallback(raw_data)
            
            # 🚨 FALLBACK: If all template parameters are corrupted, disable template processing
            if (cpp_metadata.template_data.has_corrupted_data and 
                not cpp_metadata.template_data.uml_parameters):
                logger.warning(f"All template parameters corrupted for {name}, treating as non-template")
                cpp_metadata.template_data = None
                raw_data['is_template'] = False
        
        # Create basic UML element (reuse existing logic)
        basic_element = self._create_basic_element(name, raw_data)
        
        # Enhance with C++ metadata
        enhanced = EnhancedUmlElement(
            xmi=basic_element.xmi,
            name=basic_element.name, 
            kind=basic_element.kind,
            members=basic_element.members,
            clang=basic_element.clang,
            used_types=basic_element.used_types,
            underlying=basic_element.underlying
        )
        
        enhanced.cpp_metadata = cpp_metadata
        
        # Override templates with clean UML representation
        if enhanced.is_cpp_template():
            enhanced.templates = enhanced.get_clean_template_params()
            logger.info(f"Enhanced template {name} with {len(enhanced.templates)} clean parameters")
        
        return enhanced
    
    def _create_basic_element(self, name: ElementName, raw_data: Dict[str, Any]) -> UmlElement:
        """Create basic UML element using existing codebase logic"""
        # This would integrate with existing element creation logic
        # For now, create minimal element
        
        from utils.ids import stable_id
        from core.uml_model import ClangMetadata
        
        return UmlElement(
            xmi=XmiId(stable_id(str(name))),
            name=name,
            kind=ElementKind.CLASS,  # Simplified
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            underlying=None
        )

# ===============================================
# XMI GENERATION WITH C++ METADATA
# ===============================================

class CppAwareXmiGenerator:
    """🚨 FALLBACK: XMI Generator that handles C++ metadata"""
    
    def __init__(self, model: UmlModel, profile_registry: Optional[CppProfileRegistry] = None):
        self.model = model
        self.profiles = profile_registry or CppProfileRegistry()
    
    def generate_enhanced_xmi(self, output_path: str, model_name: str = "CppModel"):
        """Generate XMI with C++ metadata preservation"""
        
        from gen.xmi.writer import XmiWriter
        from lxml import etree
        
        with etree.xmlfile(output_path, encoding='utf-8') as xf:
            writer = XmiWriter(xf)
            writer.start_doc(model_name)
            
            # Process elements with C++ metadata
            for element in self.model.elements.values():
                if isinstance(element, EnhancedUmlElement):
                    self._write_enhanced_element(writer, element)
                else:
                    self._write_basic_element(writer, element)
            
            writer.end_doc()
    
    def _write_enhanced_element(self, writer: Any, element: EnhancedUmlElement):
        """Write UML element with C++ metadata as stereotypes"""
        
        # Write basic UML structure
        writer.start_packaged_element(
            element.xmi, 
            "uml:Class",  # Simplified
            str(element.name).split("::")[-1]
        )
        
        # Write template signature if present (clean UML representation)
        if element.is_cpp_template():
            self._write_template_signature(writer, element)
        
        # Write C++ metadata as UML stereotypes and annotations
        if element.cpp_metadata:
            self._write_cpp_stereotypes(writer, element.cpp_metadata)
        
        writer.end_packaged_element()
    
    def _write_template_signature(self, writer: Any, element: EnhancedUmlElement):
        """Write clean UML template signature for UML Editor"""
        template_data = element.cpp_metadata.template_data
        
        if not template_data or not template_data.uml_parameters:
            return
            
        # Generate clean template signature for EMF compliance
        from utils.ids import stable_id
        signature_id = stable_id(str(element.xmi) + ":templateSignature") 
        
        # Write template signature that UML editors can understand
        writer.write_element("ownedTemplateSignature", {"xmi:id": signature_id})
        
        for i, param in enumerate(template_data.uml_parameters):
            param_id = stable_id(str(element.xmi) + f":param:{i}")
            param_attrs = {
                "xmi:id": param_id,
                "name": param.name
            }
            
            if param.default_value:
                param_attrs["default"] = param.default_value
                
            writer.write_element("ownedParameter", param_attrs)
    
    def _write_cpp_stereotypes(self, writer: Any, cpp_metadata: CppMetadata):
        """Write C++ metadata as UML stereotypes for preservation"""
        
        # Keywords as stereotype
        if cpp_metadata.keywords:
            keyword_names = [kw.name for kw in cpp_metadata.keywords] 
            writer.write_stereotype("CppKeywords", {"value": ",".join(keyword_names)})
        
        # Attributes as stereotype  
        if cpp_metadata.attributes:
            attr_strs = [str(attr) for attr in cpp_metadata.attributes]
            writer.write_stereotype("CppAttributes", {"value": ";".join(attr_strs)})
        
        # Template raw data preservation (for code generation)
        if (cpp_metadata.template_data and 
            cpp_metadata.template_data.raw_parameters):
            raw_data = {
                "corruption_level": max(p.corruption_level for p in cpp_metadata.template_data.raw_parameters),
                "raw_count": len(cpp_metadata.template_data.raw_parameters),
                "strategy": cpp_metadata.template_data.sync_strategy
            }
            writer.write_stereotype("CppTemplateMetadata", raw_data)
    
    def _write_basic_element(self, writer: Any, element: UmlElement):
        """Write basic UML element without C++ enhancements"""
        writer.start_packaged_element(element.xmi, "uml:Class", str(element.name).split("::")[-1])
        writer.end_packaged_element()

# ===============================================
# CONFIGURATION AND REGISTRY  
# ===============================================

class CppEnhancedConfig:
    """Configuration for C++ enhanced processing"""
    
    def __init__(self):
        # Template processing strategy
        self.template_strategy: str = "fallback"  # "strict", "fallback", "display_name"
        
        # Corruption tolerance 
        self.max_corruption_level: int = 2  # 0=clean only, 3=accept all
        
        # Code generation settings
        self.preserve_raw_data: bool = True
        self.generate_stereotypes: bool = True
        
        # Profile settings
        self.enable_std_profiles: bool = True
        self.custom_profile_paths: List[str] = []
        
        # Migration warnings
        self.show_fallback_warnings: bool = True

# Global registry for enhanced processing
_default_profile_registry = CppProfileRegistry()
_default_config = CppEnhancedConfig()

def get_enhanced_builder(config: Optional[CppEnhancedConfig] = None) -> CppEnhancedModelBuilder:
    """Factory function for enhanced model builder"""
    config = config or _default_config
    return CppEnhancedModelBuilder(_default_profile_registry)

# ===============================================
# MIGRATION & DEPRECATION WARNINGS
# ===============================================

def log_migration_warning():
    """Log migration warning for fallback implementation"""
    if _default_config.show_fallback_warnings:
        logger.warning("""
        🚨 USING FALLBACK C++ METADATA PROCESSING 🚨
        
        This is a temporary solution with heuristic-based template processing.
        For production use, migrate to clang-uml C++ library integration.
        
        Current limitations:
        - Template parameter corruption may cause data loss
        - Heuristic-based name extraction may fail on edge cases  
        - Bidirectional conversion quality depends on input data quality
        
        Migration path: Replace with direct clang AST access via clang-uml library.
        """)

# Auto-log warning on import
log_migration_warning()
