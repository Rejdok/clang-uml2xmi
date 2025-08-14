#!/usr/bin/env python3
"""
Compilation Database Analyzer for Library Structure Recovery

This module analyzes compile_commands.json to reconstruct library structure,
dependencies, and include paths for C/C++ projects.

Features:
- Parse compile_commands.json files
- Extract include paths and library dependencies
- Reconstruct project structure
- Identify external libraries and system headers
- Generate dependency graphs
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from pathlib import Path
import json
import re
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ===============================================
# COMPILATION DATABASE MODELS
# ===============================================

@dataclass
class FileArtifact:
    """Source file artifact with compilation information"""
    name: str
    path: str
    compile_flags: List[str] = field(default_factory=list)
    include_paths: List[str] = field(default_factory=list)
    object_file: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

@dataclass
class BuildTarget:
    """Build target (executable, library) with compilation information"""
    name: str
    type: str  # executable, shared_library, static_library
    output_file: str
    source_files: List[str] = field(default_factory=list)
    object_files: List[str] = field(default_factory=list)
    compile_commands: List[str] = field(default_factory=list)
    link_command: Optional[str] = None
    compile_flags: List[str] = field(default_factory=list)
    link_flags: List[str] = field(default_factory=list)
    include_paths: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    build_order: int = 0

@dataclass
class CompileCommand:
    """Single compilation command from compile_commands.json"""
    directory: str
    command: str
    file: str
    arguments: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.arguments is None:
            self.arguments = self._parse_command()
    
    def _parse_command(self) -> List[str]:
        """Parse gcc/clang command into arguments list"""
        if not self.command:
            return []
        
        # Split command and handle quoted arguments
        args = []
        current_arg = ""
        in_quotes = False
        quote_char = None
        
        for char in self.command:
            if char in ['"', "'"] and not in_quotes:
                in_quotes = True
                quote_char = char
                current_arg += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_arg += char
            elif char.isspace() and not in_quotes:
                if current_arg:
                    args.append(current_arg)
                    current_arg = ""
            else:
                current_arg += char
        
        if current_arg:
            args.append(current_arg)
        
        return args

@dataclass
class IncludePath:
    """Include path information"""
    path: str
    is_system: bool = False
    is_relative: bool = False
    source_files: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        self.is_relative = not Path(self.path).is_absolute()
        self.is_system = self.path.startswith('/usr/include') or self.path.startswith('C:/Program Files') or self.path.startswith('C:\\Program Files')

@dataclass
class LibraryDependency:
    """Library dependency information"""
    name: str
    path: Optional[str] = None
    is_system: bool = False
    linking_type: str = "dynamic"  # dynamic, static, framework
    source_files: Set[str] = field(default_factory=set)

@dataclass
class ProjectStructure:
    """Reconstructed project structure from compilation database"""
    source_files: Dict[str, CompileCommand] = field(default_factory=dict)
    include_paths: Dict[str, IncludePath] = field(default_factory=dict)
    libraries: Dict[str, LibraryDependency] = field(default_factory=dict)
    dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    build_config: Dict[str, Any] = field(default_factory=dict)

# ===============================================
# COMPILATION DATABASE PARSER
# ===============================================

class CompilationDatabaseParser:
    """Parser for compile_commands.json files"""
    
    def __init__(self):
        self.project_structure = ProjectStructure()
    
    def parse_file(self, file_path: str) -> ProjectStructure:
        """Parse compile_commands.json file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return self.project_structure
        
        if not isinstance(data, list):
            logger.error(f"Invalid compile_commands.json format: expected list, got {type(data)}")
            return self.project_structure
        
        for item in data:
            self._parse_compile_command(item)
        
        self._analyze_dependencies()
        self._extract_build_config()
        
        return self.project_structure
    
    def _parse_compile_command(self, item: Dict[str, Any]) -> None:
        """Parse single compilation command"""
        try:
            cmd = CompileCommand(
                directory=item.get('directory', ''),
                command=item.get('command', ''),
                file=item.get('file', '')
            )
            
            # Store source file
            self.project_structure.source_files[cmd.file] = cmd
            
            # Extract include paths
            self._extract_include_paths(cmd)
            
            # Extract library dependencies
            self._extract_library_dependencies(cmd)
            
        except Exception as e:
            logger.warning(f"Failed to parse compile command: {e}")
    
    def _extract_include_paths(self, cmd: CompileCommand) -> None:
        """Extract include paths from compilation command"""
        if not cmd.arguments:
            return
        
        for i, arg in enumerate(cmd.arguments):
            if arg in ['-I', '--include-directory']:
                if i + 1 < len(cmd.arguments):
                    path = cmd.arguments[i + 1]
                    self._add_include_path(path, cmd.file)
            elif arg.startswith('-I'):
                path = arg[2:]
                self._add_include_path(path, cmd.file)
            elif arg.startswith('--include-directory='):
                path = arg.split('=', 1)[1]
                self._add_include_path(path, cmd.file)
    
    def _add_include_path(self, path: str, source_file: str) -> None:
        """Add include path to project structure"""
        # Normalize path
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        
        # Handle relative paths
        if not Path(path).is_absolute():
            # Try to make absolute relative to compilation directory
            for cmd in self.project_structure.source_files.values():
                if cmd.file == source_file:
                    abs_path = Path(cmd.directory) / path
                    path = str(abs_path.resolve())
                    break
        
        if path not in self.project_structure.include_paths:
            include_path = IncludePath(path=path)
            self.project_structure.include_paths[path] = include_path
        
        self.project_structure.include_paths[path].source_files.add(source_file)
    
    def _extract_library_dependencies(self, cmd: CompileCommand) -> None:
        """Extract library dependencies from compilation command"""
        if not cmd.arguments:
            return
        
        for i, arg in enumerate(cmd.arguments):
            if arg in ['-l', '--library']:
                if i + 1 < len(cmd.arguments):
                    lib_name = cmd.arguments[i + 1]
                    self._add_library_dependency(lib_name, cmd.file)
            elif arg.startswith('-l'):
                lib_name = arg[2:]
                self._add_library_dependency(lib_name, cmd.file)
            elif arg.startswith('--library='):
                lib_name = arg.split('=', 1)[1]
                self._add_library_dependency(lib_name, cmd.file)
            elif arg.startswith('-L'):
                # Library search path
                lib_path = arg[2:]
                self._add_library_search_path(lib_path, cmd.file)
    
    def _add_library_dependency(self, lib_name: str, source_file: str) -> None:
        """Add library dependency to project structure"""
        if lib_name not in self.project_structure.libraries:
            # Determine if it's a system library
            is_system = lib_name in [
                'c', 'm', 'dl', 'pthread', 'rt', 'util', 'crypt',
                'stdc++', 'gcc', 'gcc_s', 'quadmath'
            ]
            
            lib = LibraryDependency(
                name=lib_name,
                is_system=is_system
            )
            self.project_structure.libraries[lib_name] = lib
        
        self.project_structure.libraries[lib_name].source_files.add(source_file)
    
    def _add_library_search_path(self, lib_path: str, source_file: str) -> None:
        """Add library search path"""
        # This could be used to resolve library paths later
        pass
    
    def _analyze_dependencies(self) -> None:
        """Analyze dependencies between source files"""
        for file_name, cmd in self.project_structure.source_files.items():
            # Analyze #include statements in source files
            self._analyze_file_includes(file_name, cmd)
    
    def _analyze_file_includes(self, file_name: str, cmd: CompileCommand) -> None:
        """Analyze #include statements in source file"""
        file_path = Path(cmd.directory) / cmd.file
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        # Find #include statements
        include_pattern = r'#include\s*[<"]([^>"]+)[>"]'
        for match in re.finditer(include_pattern, content):
            included_file = match.group(1)
            
            # Try to resolve include path
            resolved_path = self._resolve_include_path(included_file, cmd.directory)
            if resolved_path:
                self.project_structure.dependencies[file_name].add(str(resolved_path))
    
    def _resolve_include_path(self, include_name: str, base_dir: str) -> Optional[Path]:
        """Resolve include path using include paths from compilation database"""
        # Try relative to base directory first
        relative_path = Path(base_dir) / include_name
        if relative_path.exists():
            return relative_path
        
        # Try include paths
        for include_path in self.project_structure.include_paths.values():
            full_path = Path(include_path.path) / include_name
            if full_path.exists():
                return full_path
        
        return None
    
    def _extract_build_config(self) -> None:
        """Extract build configuration from compilation commands"""
        config = {}
        
        for cmd in self.project_structure.source_files.values():
            if not cmd.arguments:
                continue
            
            for arg in cmd.arguments:
                if arg.startswith('-std='):
                    config['c_standard'] = arg[5:]
                elif arg.startswith('-D'):
                    define = arg[2:]
                    if '=' in define:
                        key, value = define.split('=', 1)
                        config[key] = value
                    else:
                        config[define] = True
                elif arg.startswith('-O'):
                    config['optimization'] = arg
                elif arg in ['-g', '-ggdb']:
                    config['debug_info'] = True
        
        self.project_structure.build_config = config

# ===============================================
# LIBRARY STRUCTURE RECONSTRUCTOR
# ===============================================

class LibraryStructureReconstructor:
    """Reconstructs library structure from compilation database"""
    
    def __init__(self, project_structure: ProjectStructure):
        self.project_structure = project_structure
    
    def reconstruct_library_structure(self) -> Dict[str, Any]:
        """Reconstruct complete library structure"""
        result = {
            'project_info': self._extract_project_info(),
            'source_structure': self._analyze_source_structure(),
            'include_hierarchy': self._build_include_hierarchy(),
            'library_dependencies': self._analyze_library_dependencies(),
            'build_configuration': self.project_structure.build_config,
            'dependency_graph': self._build_dependency_graph()
        }
        
        # Convert sets to lists for JSON serialization
        return self._prepare_for_json(result)
    
    def _prepare_for_json(self, data: Any) -> Any:
        """Convert sets to lists for JSON serialization"""
        if isinstance(data, dict):
            return {k: self._prepare_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, set):
            return list(data)
        else:
            return data
    
    def _extract_project_info(self) -> Dict[str, Any]:
        """Extract basic project information"""
        source_dirs = set()
        for cmd in self.project_structure.source_files.values():
            source_dirs.add(cmd.directory)
        
        return {
            'source_directories': list(source_dirs),
            'total_source_files': len(self.project_structure.source_files),
            'total_include_paths': len(self.project_structure.include_paths),
            'total_libraries': len(self.project_structure.libraries)
        }
    
    def _analyze_source_structure(self) -> Dict[str, Any]:
        """Analyze source file structure"""
        file_types = defaultdict(int)
        directories = defaultdict(set)
        
        for file_name, cmd in self.project_structure.source_files.items():
            file_path = Path(file_name)
            extension = file_path.suffix.lower()
            file_types[extension] += 1
            directories[cmd.directory].add(file_name)
        
        return {
            'file_types': dict(file_types),
            'directory_structure': {k: list(v) for k, v in directories.items()}
        }
    
    def _build_include_hierarchy(self) -> Dict[str, Any]:
        """Build include path hierarchy"""
        system_includes = []
        project_includes = []
        external_includes = []
        
        for path, include_path in self.project_structure.include_paths.items():
            if include_path.is_system:
                system_includes.append(path)
            elif include_path.is_relative:
                project_includes.append(path)
            else:
                external_includes.append(path)
        
        return {
            'system_includes': system_includes,
            'project_includes': project_includes,
            'external_includes': external_includes
        }
    
    def _analyze_library_dependencies(self) -> Dict[str, Any]:
        """Analyze library dependencies"""
        system_libs = []
        external_libs = []
        
        for lib_name, lib in self.project_structure.libraries.items():
            if lib.is_system:
                system_libs.append(lib_name)
            else:
                external_libs.append(lib_name)
        
        return {
            'system_libraries': system_libs,
            'external_libraries': external_libs,
            'library_details': {
                name: {
                    'path': lib.path,
                    'is_system': lib.is_system,
                    'linking_type': lib.linking_type,
                    'source_files': list(lib.source_files)
                }
                for name, lib in self.project_structure.libraries.items()
            }
        }
    
    def _build_dependency_graph(self) -> Dict[str, Any]:
        """Build dependency graph between source files"""
        return {
            'file_dependencies': dict(self.project_structure.dependencies),
            'include_path_usage': {
                path: list(include_path.source_files)
                for path, include_path in self.project_structure.include_paths.items()
            }
        }

# ===============================================
# BUILD TARGET ANALYZER
# ===============================================

class BuildTargetAnalyzer:
    """Analyzes compile commands to extract build targets and build sequence"""
    
    def __init__(self, project_structure: ProjectStructure):
        self.project_structure = project_structure
        self.file_artifacts: Dict[str, FileArtifact] = {}
        self.build_targets: Dict[str, BuildTarget] = {}
        self.compile_phase: List[CompileCommand] = []
        self.link_phase: List[CompileCommand] = []
    
    def analyze_build_targets(self) -> Dict[str, Any]:
        """Analyze compilation database to extract build targets"""
        # 1. Separate compile and link phases
        self._separate_build_phases()
        
        # 2. Parse compile commands to create file artifacts
        self._parse_compile_commands()
        
        # 3. Parse link commands to create build targets
        self._parse_link_commands()
        
        # 4. Determine target dependencies and build order
        self._analyze_target_dependencies()
        
        # 5. Aggregate cumulative flags
        self._aggregate_target_flags()
        
        return {
            'file_artifacts': {name: self._artifact_to_dict(artifact) 
                             for name, artifact in self.file_artifacts.items()},
            'build_targets': {name: self._target_to_dict(target) 
                            for name, target in self.build_targets.items()},
            'build_sequence': {
                'compile_phase': [cmd.command for cmd in self.compile_phase],
                'link_phase': [cmd.command for cmd in self.link_phase]
            }
        }
    
    def _separate_build_phases(self) -> None:
        """Separate compilation commands into compile and link phases"""
        for cmd in self.project_structure.source_files.values():
            if '-c' in cmd.arguments:
                # Compilation phase (source to object)
                self.compile_phase.append(cmd)
            elif any(arg.startswith('ar ') or arg == 'ar' for arg in cmd.arguments) or cmd.arguments[0] == 'ar':
                # Archive creation (static library)
                self.link_phase.append(cmd)
            elif any(arg.endswith('.o') for arg in cmd.arguments):
                # Link phase (objects to executable/library)
                self.link_phase.append(cmd)
    
    def _parse_compile_commands(self) -> None:
        """Parse compile commands to extract file artifacts"""
        for cmd in self.compile_phase:
            artifact = self._parse_compile_command(cmd)
            if artifact:
                self.file_artifacts[artifact.name] = artifact
    
    def _parse_compile_command(self, cmd: CompileCommand) -> Optional[FileArtifact]:
        """Parse single compile command to extract file artifact"""
        if not cmd.arguments:
            return None
        
        source_file = cmd.file
        object_file = None
        compile_flags = []
        include_paths = []
        
        i = 0
        while i < len(cmd.arguments):
            arg = cmd.arguments[i]
            
            if arg == '-c':
                compile_flags.append(arg)
            elif arg == '-o' and i + 1 < len(cmd.arguments):
                object_file = cmd.arguments[i + 1]
                i += 1
            elif arg.startswith('-I'):
                path = arg[2:] if len(arg) > 2 else (cmd.arguments[i + 1] if i + 1 < len(cmd.arguments) else "")
                if path:
                    include_paths.append(path)
                    if len(arg) == 2:
                        i += 1
            elif arg.startswith('-D') or arg.startswith('-std=') or arg in ['-g', '-O2', '-Wall', '-Wextra']:
                compile_flags.append(arg)
            
            i += 1
        
        return FileArtifact(
            name=source_file,
            path=str(Path(cmd.directory) / source_file),
            compile_flags=compile_flags,
            include_paths=include_paths,
            object_file=object_file
        )
    
    def _parse_link_commands(self) -> None:
        """Parse link commands to extract build targets"""
        for cmd in self.link_phase:
            target = self._parse_link_command(cmd)
            if target:
                self.build_targets[target.name] = target
    
    def _parse_link_command(self, cmd: CompileCommand) -> Optional[BuildTarget]:
        """Parse single link command to extract build target"""
        if not cmd.arguments:
            return None
        
        # Handle ar commands for static libraries
        if cmd.arguments[0] == 'ar':
            return self._parse_ar_command(cmd)
        
        output_file = None
        object_files = []
        link_flags = []
        libraries = []
        
        i = 0
        while i < len(cmd.arguments):
            arg = cmd.arguments[i]
            
            if arg == '-o' and i + 1 < len(cmd.arguments):
                output_file = cmd.arguments[i + 1]
                i += 1
            elif arg.startswith('-l'):
                lib_name = arg[2:] if len(arg) > 2 else (cmd.arguments[i + 1] if i + 1 < len(cmd.arguments) else "")
                if lib_name:
                    libraries.append(lib_name)
                    if len(arg) == 2:
                        i += 1
            elif arg.startswith('-L') or arg.startswith('-Wl') or arg in ['-shared', '-static']:
                link_flags.append(arg)
            elif arg.endswith('.o'):
                object_files.append(arg)
            elif arg.endswith(('.so', '.a', '.dll', '.lib')):
                libraries.append(arg)
            
            i += 1
        
        if not output_file:
            return None
        
        # Determine target type and name
        target_name, target_type = self._determine_target_type(output_file)
        
        # Find source files for this target
        source_files = []
        for obj_file in object_files:
            for artifact in self.file_artifacts.values():
                if artifact.object_file == obj_file:
                    source_files.append(artifact.name)
                    break
        
        return BuildTarget(
            name=target_name,
            type=target_type,
            output_file=output_file,
            source_files=source_files,
            object_files=object_files,
            link_command=cmd.command,
            link_flags=link_flags,
            dependencies=libraries
        )
    
    def _parse_ar_command(self, cmd: CompileCommand) -> Optional[BuildTarget]:
        """Parse ar command for static library creation"""
        # ar rcs libgui.a window.o
        if len(cmd.arguments) < 3:
            return None
        
        ar_flags = cmd.arguments[1]  # rcs
        output_file = cmd.arguments[2]  # libgui.a
        object_files = cmd.arguments[3:]  # window.o
        
        # Determine target type and name
        target_name, target_type = self._determine_target_type(output_file)
        
        # Find source files for this target
        source_files = []
        for obj_file in object_files:
            for artifact in self.file_artifacts.values():
                if artifact.object_file == obj_file:
                    source_files.append(artifact.name)
                    break
        
        return BuildTarget(
            name=target_name,
            type=target_type,
            output_file=output_file,
            source_files=source_files,
            object_files=object_files,
            link_command=cmd.command,
            link_flags=[ar_flags],
            dependencies=[]
        )
    
    def _determine_target_type(self, output_file: str) -> Tuple[str, str]:
        """Determine target name and type from output file"""
        file_path = Path(output_file)
        filename = file_path.name
        
        if filename.startswith('lib') and filename.endswith('.so'):
            # Shared library: libmath.so -> math
            return filename[3:-3], 'shared_library'
        elif filename.startswith('lib') and filename.endswith('.a'):
            # Static library: libmath.a -> math  
            return filename[3:-2], 'static_library'
        elif filename.endswith(('.dll', '.so')):
            # Dynamic library
            return filename.rsplit('.', 1)[0], 'shared_library'
        elif filename.endswith(('.a', '.lib')):
            # Static library
            return filename.rsplit('.', 1)[0], 'static_library'
        else:
            # Executable
            return filename.rsplit('.', 1)[0], 'executable'
    
    def _analyze_target_dependencies(self) -> None:
        """Analyze dependencies between targets and determine build order"""
        # Build dependency graph
        target_deps = {}
        for target_name, target in self.build_targets.items():
            target_deps[target_name] = []
            for dep in target.dependencies:
                # Check if dependency is another target
                for other_target_name, other_target in self.build_targets.items():
                    if dep == other_target_name or dep == other_target.output_file:
                        target_deps[target_name].append(other_target_name)
        
        # Topological sort for build order
        build_order = self._topological_sort(target_deps)
        for i, target_name in enumerate(build_order):
            if target_name in self.build_targets:
                self.build_targets[target_name].build_order = i + 1
    
    def _topological_sort(self, deps: Dict[str, List[str]]) -> List[str]:
        """Topological sort for build order"""
        # Simple topological sort implementation
        in_degree = {node: 0 for node in deps}
        for node in deps:
            for dep in deps[node]:
                if dep in in_degree:
                    in_degree[dep] += 1
        
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in deps.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        
        return result
    
    def _aggregate_target_flags(self) -> None:
        """Aggregate cumulative compile flags and include paths for targets"""
        for target in self.build_targets.values():
            all_compile_flags = set()
            all_include_paths = set()
            compile_commands = []
            
            for source_file in target.source_files:
                if source_file in self.file_artifacts:
                    artifact = self.file_artifacts[source_file]
                    all_compile_flags.update(artifact.compile_flags)
                    all_include_paths.update(artifact.include_paths)
                    
                    # Find compile command for this file
                    for cmd in self.compile_phase:
                        if cmd.file == source_file:
                            compile_commands.append(cmd.command)
                            break
            
            target.compile_flags = list(all_compile_flags)
            target.include_paths = list(all_include_paths)
            target.compile_commands = compile_commands
    
    def _artifact_to_dict(self, artifact: FileArtifact) -> Dict[str, Any]:
        """Convert FileArtifact to dictionary"""
        return {
            'name': artifact.name,
            'path': artifact.path,
            'compile_flags': artifact.compile_flags,
            'include_paths': artifact.include_paths,
            'object_file': artifact.object_file,
            'classes': artifact.classes,
            'dependencies': artifact.dependencies
        }
    
    def _target_to_dict(self, target: BuildTarget) -> Dict[str, Any]:
        """Convert BuildTarget to dictionary"""
        return {
            'name': target.name,
            'type': target.type,
            'output_file': target.output_file,
            'source_files': target.source_files,
            'object_files': target.object_files,
            'compile_commands': target.compile_commands,
            'link_command': target.link_command,
            'compile_flags': target.compile_flags,
            'link_flags': target.link_flags,
            'include_paths': target.include_paths,
            'dependencies': target.dependencies,
            'build_order': target.build_order
        }

# ===============================================
# UTILITY FUNCTIONS
# ===============================================

def analyze_compile_commands(file_path: str) -> Dict[str, Any]:
    """Convenience function to analyze compile_commands.json"""
    parser = CompilationDatabaseParser()
    project_structure = parser.parse_file(file_path)
    
    # Original library structure analysis
    reconstructor = LibraryStructureReconstructor(project_structure)
    lib_structure = reconstructor.reconstruct_library_structure()
    
    # Build target analysis
    target_analyzer = BuildTargetAnalyzer(project_structure)
    target_analysis = target_analyzer.analyze_build_targets()
    
    # Combine results
    result = lib_structure.copy()
    result.update({
        'build_targets_analysis': target_analysis
    })
    
    return result

def find_compile_commands(project_root: str) -> Optional[str]:
    """Find compile_commands.json in project directory"""
    project_path = Path(project_root)
    
    # Common locations
    candidates = [
        project_path / "compile_commands.json",
        project_path / "build" / "compile_commands.json",
        project_path / ".cmake" / "compile_commands.json"
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    
    return None
