#!/usr/bin/env python3
"""
XMI Generator Extension for Build Structure Elements

Extends the XMI generator to support Package and Artifact elements
with stereotypes and tagged values for build information.
"""

from typing import Dict, Any, List, Optional
from lxml import etree
import logging

from core.uml_model import UmlElement, ElementKind
from gen.xmi.writer import XmiWriter
from uml_types import XmiId
from utils.ids import stable_id

logger = logging.getLogger(__name__)

class BuildStructureXmiExtension:
    """Extension for generating XMI for build structure elements"""
    
    def __init__(self, writer: XmiWriter):
        self.writer = writer
    
    def can_handle(self, element: UmlElement) -> bool:
        """Check if this extension can handle the element"""
        return element.kind in [ElementKind.PACKAGE, ElementKind.ARTIFACT]
    
    def generate_element(self, element: UmlElement) -> None:
        """Generate XMI for package or artifact element"""
        if element.kind == ElementKind.PACKAGE:
            self._generate_package(element)
        elif element.kind == ElementKind.ARTIFACT:
            self._generate_artifact(element)
        else:
            logger.warning(f"Unsupported element kind: {element.kind}")
    
    def _generate_package(self, element: UmlElement) -> None:
        """Generate XMI for Package element with build target information"""
        
        # Get build information from original_data
        build_data = element.original_data or {}
        target_type = build_data.get('target_type', 'unknown')
        stereotype = build_data.get('stereotype', 'target')
        
        # Create Package element
        package_attrs = {
            'xmi:type': 'uml:Package',
            'xmi:id': str(element.xmi),
            'name': element.name
        }
        
        if element.namespace and element.namespace != element.name:
            package_attrs['namespace'] = element.namespace
        
        package_elem = self.writer.create_element('packagedElement', package_attrs)
        
        # Add stereotype application
        self._add_stereotype_application(package_elem, element.xmi, stereotype, target_type)
        
        # Add tagged values for build information
        self._add_build_tagged_values(package_elem, element.xmi, build_data)
        
        # Add to model
        self.writer.add_element(package_elem)
        
        logger.debug(f"Generated Package: {element.name} <<{stereotype}>>")
    
    def _generate_artifact(self, element: UmlElement) -> None:
        """Generate XMI for Artifact element with file information"""
        
        # Get file information from original_data
        file_data = element.original_data or {}
        
        # Create Artifact element
        artifact_attrs = {
            'xmi:type': 'uml:Artifact',
            'xmi:id': str(element.xmi),
            'name': element.name
        }
        
        if element.namespace and element.namespace != element.name:
            artifact_attrs['namespace'] = element.namespace
        
        artifact_elem = self.writer.create_element('packagedElement', artifact_attrs)
        
        # Add stereotype application for file
        self._add_stereotype_application(artifact_elem, element.xmi, 'file', 'source_file')
        
        # Add tagged values for file information
        self._add_file_tagged_values(artifact_elem, element.xmi, file_data)
        
        # Add to model
        self.writer.add_element(artifact_elem)
        
        logger.debug(f"Generated Artifact: {element.name} <<file>>")
    
    def _add_stereotype_application(self, parent_elem: etree.Element, 
                                  element_id: XmiId, stereotype: str, 
                                  category: str) -> None:
        """Add stereotype application to element"""
        
        # Create stereotype application ID
        stereotype_id = stable_id(f"stereotype:{element_id}:{stereotype}")
        
        # Add stereotype application element
        stereotype_attrs = {
            'xmi:type': f'BuildProfile:{stereotype}',
            'xmi:id': str(stereotype_id),
            'base_Element': str(element_id),
            'category': category
        }
        
        stereotype_elem = etree.SubElement(parent_elem, 'stereotype_application', stereotype_attrs)
        
        # Add to profiles section
        self._add_profile_application(stereotype, category)
    
    def _add_build_tagged_values(self, parent_elem: etree.Element, 
                                element_id: XmiId, build_data: Dict[str, Any]) -> None:
        """Add tagged values for build target information"""
        
        tagged_values = []
        
        # Add compile flags
        if 'compile_flags' in build_data and build_data['compile_flags']:
            tagged_values.append({
                'name': 'compile_flags',
                'value': ' '.join(build_data['compile_flags'])
            })
        
        # Add link flags
        if 'link_flags' in build_data and build_data['link_flags']:
            tagged_values.append({
                'name': 'link_flags', 
                'value': ' '.join(build_data['link_flags'])
            })
        
        # Add include paths
        if 'include_paths' in build_data and build_data['include_paths']:
            tagged_values.append({
                'name': 'include_paths',
                'value': ';'.join(build_data['include_paths'])
            })
        
        # Add output file
        if 'output_file' in build_data:
            tagged_values.append({
                'name': 'output_file',
                'value': build_data['output_file']
            })
        
        # Add build order
        if 'build_order' in build_data:
            tagged_values.append({
                'name': 'build_order',
                'value': str(build_data['build_order'])
            })
        
        # Generate tagged value elements
        for tv in tagged_values:
            self._add_tagged_value(parent_elem, element_id, tv['name'], tv['value'])
    
    def _add_file_tagged_values(self, parent_elem: etree.Element, 
                               element_id: XmiId, file_data: Dict[str, Any]) -> None:
        """Add tagged values for file artifact information"""
        
        tagged_values = []
        
        # Add file path
        if 'file_path' in file_data:
            tagged_values.append({
                'name': 'file_path',
                'value': file_data['file_path']
            })
        
        # Add compile flags
        if 'compile_flags' in file_data and file_data['compile_flags']:
            tagged_values.append({
                'name': 'compile_flags',
                'value': ' '.join(file_data['compile_flags'])
            })
        
        # Add include paths
        if 'include_paths' in file_data and file_data['include_paths']:
            tagged_values.append({
                'name': 'include_paths',
                'value': ';'.join(file_data['include_paths'])
            })
        
        # Add object file
        if 'object_file' in file_data:
            tagged_values.append({
                'name': 'object_file',
                'value': file_data['object_file']
            })
        
        # Generate tagged value elements
        for tv in tagged_values:
            self._add_tagged_value(parent_elem, element_id, tv['name'], tv['value'])
    
    def _add_tagged_value(self, parent_elem: etree.Element, 
                         element_id: XmiId, name: str, value: str) -> None:
        """Add a single tagged value to element"""
        
        tv_id = stable_id(f"taggedvalue:{element_id}:{name}")
        
        tv_attrs = {
            'xmi:type': 'uml:TaggedValue',
            'xmi:id': str(tv_id),
            'name': name,
            'value': value,
            'element': str(element_id)
        }
        
        tv_elem = etree.SubElement(parent_elem, 'taggedValue', tv_attrs)
        
        logger.debug(f"Added tagged value: {name} = {value}")
    
    def _add_profile_application(self, stereotype: str, category: str) -> None:
        """Add profile application to model (implementation depends on XmiWriter)"""
        # This would be implemented to add the profile application
        # to the XMI model header/profiles section
        logger.debug(f"Profile application: {stereotype} ({category})")

# ===============================================
# INTEGRATION WITH EXISTING XMI GENERATOR
# ===============================================

def extend_xmi_generator_for_build_structure(generator_class):
    """Decorator to extend XMI generator with build structure support"""
    
    original_visit_method = getattr(generator_class, 'visit_element', None)
    
    def visit_element_with_build_support(self, element: UmlElement) -> None:
        """Extended visit method that handles build structure elements"""
        
        # Check if this is a build structure element
        if hasattr(self, '_build_extension'):
            extension = self._build_extension
        else:
            extension = BuildStructureXmiExtension(self.writer)
            self._build_extension = extension
        
        if extension.can_handle(element):
            extension.generate_element(element)
        elif original_visit_method:
            original_visit_method(self, element)
        else:
            logger.warning(f"No handler for element: {element.name} ({element.kind})")
    
    # Replace the visit method
    setattr(generator_class, 'visit_element', visit_element_with_build_support)
    
    return generator_class

# ===============================================
# UTILITY FUNCTIONS  
# ===============================================

def generate_build_structure_profile() -> str:
    """Generate UML profile for build structure stereotypes"""
    
    profile_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<uml:Profile xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" 
             xmlns:uml="http://www.eclipse.org/uml2/5.0.0/UML"
             xmi:id="BuildProfile" name="BuildProfile">
             
  <!-- Executable Stereotype -->
  <packagedElement xmi:type="uml:Stereotype" xmi:id="Executable" name="executable">
    <ownedAttribute xmi:id="Executable.category" name="category" type="String"/>
    <ownedAttribute xmi:id="Executable.output_file" name="output_file" type="String"/>
    <ownedAttribute xmi:id="Executable.compile_flags" name="compile_flags" type="String"/>
    <ownedAttribute xmi:id="Executable.link_flags" name="link_flags" type="String"/>
    <ownedAttribute xmi:id="Executable.build_order" name="build_order" type="Integer"/>
  </packagedElement>
  
  <!-- Shared Library Stereotype -->
  <packagedElement xmi:type="uml:Stereotype" xmi:id="SharedLibrary" name="shared_library">
    <ownedAttribute xmi:id="SharedLibrary.category" name="category" type="String"/>
    <ownedAttribute xmi:id="SharedLibrary.output_file" name="output_file" type="String"/>
    <ownedAttribute xmi:id="SharedLibrary.compile_flags" name="compile_flags" type="String"/>
    <ownedAttribute xmi:id="SharedLibrary.link_flags" name="link_flags" type="String"/>
    <ownedAttribute xmi:id="SharedLibrary.build_order" name="build_order" type="Integer"/>
  </packagedElement>
  
  <!-- Static Library Stereotype -->
  <packagedElement xmi:type="uml:Stereotype" xmi:id="StaticLibrary" name="static_library">
    <ownedAttribute xmi:id="StaticLibrary.category" name="category" type="String"/>
    <ownedAttribute xmi:id="StaticLibrary.output_file" name="output_file" type="String"/>
    <ownedAttribute xmi:id="StaticLibrary.compile_flags" name="compile_flags" type="String"/>
    <ownedAttribute xmi:id="StaticLibrary.link_flags" name="link_flags" type="String"/>
    <ownedAttribute xmi:id="StaticLibrary.build_order" name="build_order" type="Integer"/>
  </packagedElement>
  
  <!-- File Stereotype -->
  <packagedElement xmi:type="uml:Stereotype" xmi:id="File" name="file">
    <ownedAttribute xmi:id="File.file_path" name="file_path" type="String"/>
    <ownedAttribute xmi:id="File.compile_flags" name="compile_flags" type="String"/>
    <ownedAttribute xmi:id="File.include_paths" name="include_paths" type="String"/>
    <ownedAttribute xmi:id="File.object_file" name="object_file" type="String"/>
  </packagedElement>
  
</uml:Profile>'''
    
    return profile_xml

def save_build_profile(output_path: str) -> None:
    """Save build structure profile to file"""
    profile_content = generate_build_structure_profile()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(profile_content)
    
    logger.info(f"Build structure profile saved to: {output_path}")
