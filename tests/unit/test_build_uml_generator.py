#!/usr/bin/env python3
"""
Tests for build UML generator functionality
"""

import pytest
from unittest.mock import Mock, patch

from core.build_uml_generator import (
    BuildUmlGenerator,
    BuildUmlModelIntegrator,
    UmlArtifact,
    UmlPackage,
    BuildStructureModel,
    generate_build_uml,
    print_build_structure_summary
)
from core.uml_model import UmlModel, UmlElement, ElementKind
from uml_types import XmiId

class TestBuildUmlGenerator:
    def test_generator_creation(self):
        generator = BuildUmlGenerator()
        assert generator.build_model is not None
        assert isinstance(generator.build_model, BuildStructureModel)
    
    def test_generate_artifacts(self):
        generator = BuildUmlGenerator()
        
        file_artifacts = {
            "main.cpp": {
                "name": "main.cpp",
                "path": "/project/main.cpp",
                "compile_flags": ["-std=c++17", "-c"],
                "include_paths": ["./core"],
                "object_file": "main.o",
                "dependencies": []
            },
            "math.cpp": {
                "name": "math.cpp", 
                "path": "/project/math.cpp",
                "compile_flags": ["-std=c++17", "-c"],
                "include_paths": ["./core"],
                "object_file": "math.o",
                "dependencies": []
            }
        }
        
        generator._generate_artifacts(file_artifacts)
        
        assert len(generator.build_model.artifacts) == 2
        assert "main.cpp" in generator.build_model.artifacts
        assert "math.cpp" in generator.build_model.artifacts
        
        main_artifact = generator.build_model.artifacts["main.cpp"]
        assert main_artifact.name == "main.cpp"
        assert main_artifact.file_path == "/project/main.cpp"
        assert main_artifact.object_file == "main.o"
        assert "-std=c++17" in main_artifact.compile_flags
        assert "./core" in main_artifact.include_paths
    
    def test_generate_packages(self):
        generator = BuildUmlGenerator()
        
        build_targets = {
            "myapp": {
                "name": "myapp",
                "type": "executable",
                "output_file": "myapp",
                "compile_flags": ["-std=c++17"],
                "link_flags": ["-L."],
                "include_paths": ["./core"],
                "dependencies": ["math"],
                "build_order": 2
            },
            "math": {
                "name": "math",
                "type": "shared_library", 
                "output_file": "libmath.so",
                "compile_flags": ["-std=c++17"],
                "link_flags": ["-shared"],
                "include_paths": ["./core"],
                "dependencies": [],
                "build_order": 1
            }
        }
        
        generator._generate_packages(build_targets)
        
        assert len(generator.build_model.packages) == 2
        assert "myapp" in generator.build_model.packages
        assert "math" in generator.build_model.packages
        
        app_package = generator.build_model.packages["myapp"]
        assert app_package.name == "myapp"
        assert app_package.target_type == "executable"
        assert app_package.output_file == "myapp"
        assert app_package.build_order == 2
        assert "math" in app_package.dependencies
        
        math_package = generator.build_model.packages["math"]
        assert math_package.name == "math"
        assert math_package.target_type == "shared_library"
        assert math_package.output_file == "libmath.so"
        assert math_package.build_order == 1
        assert len(math_package.dependencies) == 0
    
    def test_assign_artifacts_to_packages(self):
        generator = BuildUmlGenerator()
        
        # First create artifacts
        file_artifacts = {
            "main.cpp": {"name": "main.cpp", "path": "/project/main.cpp"},
            "math.cpp": {"name": "math.cpp", "path": "/project/math.cpp"}
        }
        generator._generate_artifacts(file_artifacts)
        
        # Then create packages
        build_targets = {
            "myapp": {
                "name": "myapp",
                "type": "executable",
                "source_files": ["main.cpp"]
            },
            "math": {
                "name": "math", 
                "type": "shared_library",
                "source_files": ["math.cpp"]
            }
        }
        generator._generate_packages(build_targets)
        
        # Now assign artifacts
        generator._assign_artifacts_to_packages(build_targets)
        
        app_package = generator.build_model.packages["myapp"]
        math_package = generator.build_model.packages["math"]
        
        assert len(app_package.artifacts) == 1
        assert app_package.artifacts[0].name == "main.cpp"
        
        assert len(math_package.artifacts) == 1
        assert math_package.artifacts[0].name == "math.cpp"
    
    def test_generate_package_dependencies(self):
        generator = BuildUmlGenerator()
        
        # Create packages with dependencies
        build_targets = {
            "myapp": {
                "name": "myapp",
                "dependencies": ["math", "gui", "nonexistent"]
            },
            "math": {
                "name": "math",
                "dependencies": []
            },
            "gui": {
                "name": "gui", 
                "dependencies": ["math"]
            }
        }
        generator._generate_packages(build_targets)
        generator._generate_package_dependencies()
        
        deps = generator.build_model.dependencies
        
        assert "myapp" in deps
        assert "math" in deps["myapp"]
        assert "gui" in deps["myapp"]
        assert "nonexistent" not in deps["myapp"]  # Should filter out non-existent packages
        
        assert "gui" in deps
        assert "math" in deps["gui"]
        
        assert "math" in deps
        assert len(deps["math"]) == 0
    
    def test_full_generation_from_analysis(self):
        generator = BuildUmlGenerator()
        
        analysis_result = {
            "build_targets_analysis": {
                "file_artifacts": {
                    "main.cpp": {
                        "name": "main.cpp",
                        "path": "/project/main.cpp",
                        "compile_flags": ["-std=c++17", "-c"],
                        "include_paths": ["./core"],
                        "object_file": "main.o"
                    }
                },
                "build_targets": {
                    "myapp": {
                        "name": "myapp",
                        "type": "executable",
                        "output_file": "myapp",
                        "source_files": ["main.cpp"],
                        "compile_flags": ["-std=c++17"],
                        "link_flags": ["-L."],
                        "dependencies": [],
                        "build_order": 1
                    }
                }
            }
        }
        
        result = generator.generate_from_analysis(analysis_result)
        
        assert isinstance(result, BuildStructureModel)
        assert len(result.artifacts) == 1
        assert len(result.packages) == 1
        assert "main.cpp" in result.artifacts
        assert "myapp" in result.packages
        
        # Check that artifact is assigned to package
        package = result.packages["myapp"]
        assert len(package.artifacts) == 1
        assert package.artifacts[0].name == "main.cpp"


class TestBuildUmlModelIntegrator:
    def test_integrator_creation(self):
        integrator = BuildUmlModelIntegrator()
        assert integrator.uml_model is not None
        assert isinstance(integrator.uml_model, UmlModel)
    
    def test_integrator_with_existing_model(self):
        existing_model = UmlModel(
            elements={},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={}
        )
        integrator = BuildUmlModelIntegrator(existing_model)
        assert integrator.uml_model is existing_model
    
    def test_get_target_stereotype(self):
        integrator = BuildUmlModelIntegrator()
        
        assert integrator._get_target_stereotype("executable") == "executable"
        assert integrator._get_target_stereotype("shared_library") == "shared_library"
        assert integrator._get_target_stereotype("static_library") == "static_library"
        assert integrator._get_target_stereotype("unknown") == "target"
        assert integrator._get_target_stereotype("invalid") == "target"
    
    def test_add_build_system_package(self):
        integrator = BuildUmlModelIntegrator()
        package_id = XmiId("test_package_id")
        
        integrator._add_build_system_package(package_id)
        
        assert package_id in integrator.uml_model.elements
        assert "BuildSystem" in integrator.uml_model.name_to_xmi
        
        element = integrator.uml_model.elements[package_id]
        assert element.name == "BuildSystem"
        assert element.kind == ElementKind.PACKAGE
        assert element.namespace == "BuildSystem"
    
    def test_add_package_element(self):
        integrator = BuildUmlModelIntegrator()
        parent_id = XmiId("parent_id")
        
        package = UmlPackage(
            xmi=XmiId("package_id"),
            name="TestTarget",
            target_type="executable",
            output_file="test_app",
            compile_flags=["-std=c++17"],
            link_flags=["-L."],
            build_order=1
        )
        
        integrator._add_package_element(package, parent_id)
        
        assert package.xmi in integrator.uml_model.elements
        assert "TestTarget" in integrator.uml_model.name_to_xmi
        
        element = integrator.uml_model.elements[package.xmi]
        assert element.name == "TestTarget"
        assert element.kind == ElementKind.PACKAGE
        assert element.namespace == "BuildSystem"
        assert element.original_data["target_type"] == "executable"
        assert element.original_data["stereotype"] == "executable"
    
    def test_add_artifact_element(self):
        integrator = BuildUmlModelIntegrator()
        
        artifact = UmlArtifact(
            xmi=XmiId("artifact_id"),
            name="test.cpp",
            file_path="/project/test.cpp",
            compile_flags=["-std=c++17"],
            include_paths=["./include"]
        )
        
        integrator._add_artifact_element(artifact)
        
        assert artifact.xmi in integrator.uml_model.elements
        assert "test.cpp" in integrator.uml_model.name_to_xmi
        
        element = integrator.uml_model.elements[artifact.xmi]
        assert element.name == "test.cpp"
        assert element.kind == ElementKind.ARTIFACT
        assert element.namespace == "BuildSystem"
        assert element.original_data["file_path"] == "/project/test.cpp"
        assert element.original_data["stereotype"] == "file"
    
    def test_integrate_build_structure(self):
        integrator = BuildUmlModelIntegrator()
        
        # Create a simple build model
        build_model = BuildStructureModel()
        
        artifact = UmlArtifact(
            xmi=XmiId("artifact_id"),
            name="main.cpp",
            file_path="/project/main.cpp"
        )
        build_model.artifacts["main.cpp"] = artifact
        
        package = UmlPackage(
            xmi=XmiId("package_id"),
            name="myapp",
            target_type="executable",
            output_file="myapp",
            artifacts=[artifact]
        )
        build_model.packages["myapp"] = package
        build_model.dependencies["myapp"] = []
        
        result_model = integrator.integrate_build_structure(build_model)
        
        assert isinstance(result_model, UmlModel)
        assert len(result_model.elements) >= 3  # Root package + package + artifact
        assert "BuildSystem" in result_model.name_to_xmi
        assert "myapp" in result_model.name_to_xmi  
        assert "main.cpp" in result_model.name_to_xmi


class TestUtilityFunctions:
    def test_generate_build_uml(self):
        analysis_result = {
            "build_targets_analysis": {
                "file_artifacts": {
                    "main.cpp": {
                        "name": "main.cpp",
                        "path": "/project/main.cpp"
                    }
                },
                "build_targets": {
                    "myapp": {
                        "name": "myapp",
                        "type": "executable",
                        "source_files": ["main.cpp"]
                    }
                }
            }
        }
        
        result = generate_build_uml(analysis_result)
        
        assert isinstance(result, UmlModel)
        assert len(result.elements) >= 3  # Root + package + artifact
        assert "BuildSystem" in result.name_to_xmi
        assert "myapp" in result.name_to_xmi
        assert "main.cpp" in result.name_to_xmi
    
    def test_generate_build_uml_with_existing_model(self):
        existing_model = UmlModel(
            elements={},
            associations=[],
            dependencies=[],
            generalizations=[],
            name_to_xmi={}
        )
        # Add some existing element
        existing_element = UmlElement(
            xmi=XmiId("existing_id"),
            name="ExistingClass",
            kind=ElementKind.CLASS,
            members=[],
            clang=Mock(),
            used_types=frozenset()
        )
        existing_model.elements[XmiId("existing_id")] = existing_element
        existing_model.name_to_xmi["ExistingClass"] = XmiId("existing_id")
        
        analysis_result = {
            "build_targets_analysis": {
                "file_artifacts": {},
                "build_targets": {}
            }
        }
        
        result = generate_build_uml(analysis_result, existing_model)
        
        assert isinstance(result, UmlModel)
        assert XmiId("existing_id") in result.elements
        assert "ExistingClass" in result.name_to_xmi
        assert "BuildSystem" in result.name_to_xmi
    
    @patch('builtins.print')
    def test_print_build_structure_summary(self, mock_print):
        build_model = BuildStructureModel()
        
        artifact = UmlArtifact(
            xmi=XmiId("artifact_id"),
            name="main.cpp", 
            file_path="/project/main.cpp",
            object_file="main.o"
        )
        build_model.artifacts["main.cpp"] = artifact
        
        package = UmlPackage(
            xmi=XmiId("package_id"),
            name="myapp",
            target_type="executable", 
            output_file="myapp",
            artifacts=[artifact],
            build_order=1
        )
        build_model.packages["myapp"] = package
        build_model.dependencies["myapp"] = []
        
        print_build_structure_summary(build_model)
        
        # Check that print was called with summary information
        assert mock_print.called
        calls = [str(call) for call in mock_print.call_args_list]
        summary_text = '\n'.join(calls)
        
        assert "BUILD STRUCTURE UML SUMMARY" in summary_text
        assert "myapp" in summary_text
        assert "executable" in summary_text
        assert "main.cpp" in summary_text


class TestBuildStructures:
    def test_uml_artifact_creation(self):
        artifact = UmlArtifact(
            xmi=XmiId("test_id"),
            name="test.cpp",
            file_path="/project/test.cpp",
            compile_flags=["-std=c++17"],
            include_paths=["./include"],
            object_file="test.o",
            dependencies=["other.h"]
        )
        
        assert artifact.xmi == XmiId("test_id")
        assert artifact.name == "test.cpp"
        assert artifact.file_path == "/project/test.cpp"
        assert len(artifact.compile_flags) == 1
        assert len(artifact.include_paths) == 1
        assert artifact.object_file == "test.o"
        assert len(artifact.dependencies) == 1
    
    def test_uml_package_creation(self):
        package = UmlPackage(
            xmi=XmiId("test_id"),
            name="test_target",
            target_type="shared_library",
            output_file="libtest.so",
            compile_flags=["-std=c++17"],
            link_flags=["-shared"],
            include_paths=["./include"],
            dependencies=["math"],
            build_order=2
        )
        
        assert package.xmi == XmiId("test_id")
        assert package.name == "test_target"
        assert package.target_type == "shared_library"
        assert package.output_file == "libtest.so"
        assert len(package.compile_flags) == 1
        assert len(package.link_flags) == 1
        assert len(package.include_paths) == 1
        assert len(package.dependencies) == 1
        assert package.build_order == 2
    
    def test_build_structure_model_creation(self):
        model = BuildStructureModel()
        
        assert isinstance(model.packages, dict)
        assert isinstance(model.artifacts, dict)
        assert isinstance(model.dependencies, dict)
        assert len(model.packages) == 0
        assert len(model.artifacts) == 0
        assert len(model.dependencies) == 0
