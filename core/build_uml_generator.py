#!/usr/bin/env python3
"""
Build Structure UML Generator

Generates UML model for build targets and file artifacts from compilation database analysis.
Creates Package elements for targets and Artifact elements for files.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
import logging

from core.uml_model import UmlElement, UmlModel, ClangMetadata, ElementKind
from uml_types import XmiId, ElementName, TypeName, Visibility
from utils.ids import stable_id

logger = logging.getLogger(__name__)

# ===============================================
# BUILD UML STRUCTURES
# ===============================================

@dataclass
class UmlArtifact:
    """UML Artifact representing a source file"""
    xmi: XmiId
    name: ElementName
    file_path: str
    compile_flags: List[str] = field(default_factory=list)
    include_paths: List[str] = field(default_factory=list)
    object_file: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

@dataclass
class UmlPackage:
    """UML Package representing a build target"""
    xmi: XmiId
    name: ElementName
    target_type: str  # executable, shared_library, static_library
    output_file: str
    artifacts: List[UmlArtifact] = field(default_factory=list)
    compile_flags: List[str] = field(default_factory=list)
    link_flags: List[str] = field(default_factory=list)
    include_paths: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    build_order: int = 0

@dataclass
class BuildStructureModel:
    """Complete build structure UML model"""
    packages: Dict[str, UmlPackage] = field(default_factory=dict)
    artifacts: Dict[str, UmlArtifact] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)

# ===============================================
# BUILD UML GENERATOR
# ===============================================

class BuildUmlGenerator:
    """Generates UML model from build targets analysis"""
    
    def __init__(self):
        self.build_model = BuildStructureModel()
    
    def generate_from_analysis(self, analysis_result: Dict[str, Any]) -> BuildStructureModel:
        """Generate UML build structure from compilation database analysis"""
        
        # Extract build targets analysis
        if 'build_targets_analysis' not in analysis_result:
            logger.warning("No build_targets_analysis found in analysis result")
            return self.build_model
        
        build_analysis = analysis_result['build_targets_analysis']
        
        # Generate artifacts from file artifacts
        self._generate_artifacts(build_analysis.get('file_artifacts', {}))
        
        # Generate packages from build targets
        self._generate_packages(build_analysis.get('build_targets', {}))
        
        # Add artifacts to their corresponding packages
        self._assign_artifacts_to_packages(build_analysis.get('build_targets', {}))
        
        # Generate dependencies between packages
        self._generate_package_dependencies()
        
        return self.build_model
    
    def _generate_artifacts(self, file_artifacts: Dict[str, Any]) -> None:
        """Generate UML Artifacts from file artifacts"""
        for file_name, artifact_data in file_artifacts.items():
            artifact_id = stable_id(f"artifact:{file_name}")
            
            artifact = UmlArtifact(
                xmi=artifact_id,
                name=file_name,
                file_path=artifact_data.get('path', ''),
                compile_flags=artifact_data.get('compile_flags', []),
                include_paths=artifact_data.get('include_paths', []),
                object_file=artifact_data.get('object_file'),
                dependencies=artifact_data.get('dependencies', [])
            )
            
            self.build_model.artifacts[file_name] = artifact
            logger.debug(f"Generated artifact: {file_name}")
    
    def _generate_packages(self, build_targets: Dict[str, Any]) -> None:
        """Generate UML Packages from build targets"""
        for target_name, target_data in build_targets.items():
            package_id = stable_id(f"package:{target_name}")
            
            package = UmlPackage(
                xmi=package_id,
                name=target_name,
                target_type=target_data.get('type', 'unknown'),
                output_file=target_data.get('output_file', ''),
                compile_flags=target_data.get('compile_flags', []),
                link_flags=target_data.get('link_flags', []),
                include_paths=target_data.get('include_paths', []),
                dependencies=target_data.get('dependencies', []),
                build_order=target_data.get('build_order', 0)
            )
            
            self.build_model.packages[target_name] = package
            logger.debug(f"Generated package: {target_name} ({package.target_type})")
    
    def _assign_artifacts_to_packages(self, build_targets: Dict[str, Any]) -> None:
        """Assign artifacts to their corresponding packages"""
        for target_name, target_data in build_targets.items():
            if target_name not in self.build_model.packages:
                continue
            
            package = self.build_model.packages[target_name]
            source_files = target_data.get('source_files', [])
            
            for source_file in source_files:
                if source_file in self.build_model.artifacts:
                    artifact = self.build_model.artifacts[source_file]
                    package.artifacts.append(artifact)
                    logger.debug(f"Assigned artifact {source_file} to package {target_name}")
    
    def _generate_package_dependencies(self) -> None:
        """Generate dependencies between packages"""
        for package_name, package in self.build_model.packages.items():
            deps = []
            for dep_name in package.dependencies:
                if dep_name in self.build_model.packages:
                    deps.append(dep_name)
            
            self.build_model.dependencies[package_name] = deps
            logger.debug(f"Package {package_name} depends on: {deps}")

# ===============================================
# UML MODEL INTEGRATION
# ===============================================

class BuildUmlModelIntegrator:
    """Integrates build structure into existing UML model"""
    
    def __init__(self, uml_model: Optional[UmlModel] = None):
        if uml_model is None:
            self.uml_model = UmlModel(
                elements={},
                associations=[],
                dependencies=[],
                generalizations=[],
                name_to_xmi={}
            )
        else:
            self.uml_model = uml_model
    
    def integrate_build_structure(self, build_model: BuildStructureModel) -> UmlModel:
        """Integrate build structure into UML model"""
        
        # Create root package for build structure
        root_package_id = stable_id("package:BuildSystem")
        self._add_build_system_package(root_package_id)
        
        # Add packages as UML Package elements
        for package_name, package in build_model.packages.items():
            self._add_package_element(package, root_package_id)
        
        # Add artifacts as UML Artifact elements
        for artifact_name, artifact in build_model.artifacts.items():
            self._add_artifact_element(artifact)
        
        # Add package dependencies
        self._add_package_dependencies(build_model.dependencies)
        
        return self.uml_model
    
    def _add_build_system_package(self, package_id: XmiId) -> None:
        """Add root build system package"""
        build_system_element = UmlElement(
            xmi=package_id,
            name="BuildSystem",
            kind=ElementKind.PACKAGE,
            members=[],
            clang=ClangMetadata(),
            used_types=frozenset(),
            namespace="BuildSystem"
        )
        
        self.uml_model.elements[package_id] = build_system_element
        self.uml_model.name_to_xmi["BuildSystem"] = package_id
        logger.debug("Added BuildSystem root package")
    
    def _add_package_element(self, package: UmlPackage, parent_id: XmiId) -> None:
        """Add package as UML Package element with stereotypes"""
        
        # Determine stereotype based on target type
        stereotype = self._get_target_stereotype(package.target_type)
        
        package_element = UmlElement(
            xmi=package.xmi,
            name=package.name,
            kind=ElementKind.PACKAGE,
            members=[],
            clang=ClangMetadata(
                qualified_name=f"BuildSystem::{package.name}",
                display_name=f"{package.name} <<{stereotype}>>",
                name=package.name,
                type="package",
                kind=package.target_type
            ),
            used_types=frozenset(),
            namespace="BuildSystem",
            original_data={
                'target_type': package.target_type,
                'output_file': package.output_file,
                'compile_flags': package.compile_flags,
                'link_flags': package.link_flags,
                'include_paths': package.include_paths,
                'build_order': package.build_order,
                'stereotype': stereotype
            }
        )
        
        self.uml_model.elements[package.xmi] = package_element
        self.uml_model.name_to_xmi[package.name] = package.xmi
        logger.debug(f"Added package element: {package.name} <<{stereotype}>>")
    
    def _add_artifact_element(self, artifact: UmlArtifact) -> None:
        """Add artifact as UML Artifact element"""
        
        artifact_element = UmlElement(
            xmi=artifact.xmi,
            name=artifact.name,
            kind=ElementKind.ARTIFACT,
            members=[],
            clang=ClangMetadata(
                qualified_name=f"BuildSystem::{artifact.name}",
                display_name=f"{artifact.name} <<file>>",
                name=artifact.name,
                type="artifact",
                kind="file"
            ),
            used_types=frozenset(),
            namespace="BuildSystem",
            original_data={
                'file_path': artifact.file_path,
                'compile_flags': artifact.compile_flags,
                'include_paths': artifact.include_paths,
                'object_file': artifact.object_file,
                'dependencies': artifact.dependencies,
                'stereotype': 'file'
            }
        )
        
        self.uml_model.elements[artifact.xmi] = artifact_element
        self.uml_model.name_to_xmi[artifact.name] = artifact.xmi
        logger.debug(f"Added artifact element: {artifact.name} <<file>>")
    
    def _add_package_dependencies(self, dependencies: Dict[str, List[str]]) -> None:
        """Add dependencies between packages"""
        for package_name, deps in dependencies.items():
            package_id = self.uml_model.name_to_xmi.get(package_name)
            if not package_id:
                continue
            
            for dep_name in deps:
                dep_id = self.uml_model.name_to_xmi.get(dep_name)
                if dep_id:
                    # Create dependency association
                    self._create_dependency_association(package_id, dep_id, package_name, dep_name)
    
    def _create_dependency_association(self, source_id: XmiId, target_id: XmiId, 
                                     source_name: str, target_name: str) -> None:
        """Create dependency association between packages"""
        # This would be implemented to create UML dependencies
        # For now, we store it in the model metadata
        logger.debug(f"Dependency: {source_name} -> {target_name}")
    
    def _get_target_stereotype(self, target_type: str) -> str:
        """Get UML stereotype for target type"""
        stereotype_map = {
            'executable': 'executable',
            'shared_library': 'shared_library', 
            'static_library': 'static_library',
            'unknown': 'target'
        }
        return stereotype_map.get(target_type, 'target')

# ===============================================
# UTILITY FUNCTIONS
# ===============================================

def generate_build_uml(analysis_result: Dict[str, Any], 
                      existing_model: Optional[UmlModel] = None) -> UmlModel:
    """Convenience function to generate UML from build analysis"""
    
    # Generate build structure
    generator = BuildUmlGenerator()
    build_model = generator.generate_from_analysis(analysis_result)
    
    # Integrate into UML model
    integrator = BuildUmlModelIntegrator(existing_model)
    uml_model = integrator.integrate_build_structure(build_model)
    
    logger.info(f"Generated UML model with {len(build_model.packages)} packages and {len(build_model.artifacts)} artifacts")
    
    return uml_model

def print_build_structure_summary(build_model: BuildStructureModel) -> None:
    """Print summary of build structure"""
    print("\n" + "="*60)
    print("🏗️  BUILD STRUCTURE UML SUMMARY")
    print("="*60)
    
    # Packages (Targets)
    print(f"\n📦 PACKAGES (BUILD TARGETS): {len(build_model.packages)}")
    for name, package in sorted(build_model.packages.items(), key=lambda x: x[1].build_order):
        stereotype = package.target_type
        print(f"   {package.build_order}. {name} <<{stereotype}>>")
        print(f"      Output: {package.output_file}")
        print(f"      Artifacts: {len(package.artifacts)} files")
        if package.dependencies:
            print(f"      Depends on: {', '.join(package.dependencies)}")
    
    # Artifacts (Files)
    print(f"\n📄 ARTIFACTS (SOURCE FILES): {len(build_model.artifacts)}")
    for name, artifact in build_model.artifacts.items():
        print(f"   {name} -> {artifact.object_file or 'no object'}")
        if artifact.compile_flags:
            print(f"      Flags: {' '.join(artifact.compile_flags[:3])}{'...' if len(artifact.compile_flags) > 3 else ''}")
    
    # Dependencies
    print(f"\n🔗 DEPENDENCIES:")
    for package_name, deps in build_model.dependencies.items():
        if deps:
            print(f"   {package_name} -> {', '.join(deps)}")
    
    print("="*60)
