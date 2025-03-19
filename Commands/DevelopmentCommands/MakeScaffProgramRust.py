#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramRust Command - Creates a basic scaffolding for a Rust program
"""

import os
import shutil
import subprocess
import datetime
from Core.command_base import CommandBase

class MakeScaffProgramRustCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Rust program.
    Creates a new Rust project with standard directory structure and basic files.
    """
    
    name = "makeScaffProgramRust"
    aliases = ["rustScaff", "newRust", "createRust"]
    description = "Creates a basic scaffolding for a Rust program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Rust project to create',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path where to create the project (default: current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'binary',
            'description': 'Whether to create a binary application (true) or a library (false)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'with_tests',
            'description': 'Whether to include test scaffolding',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramRust my_project',
            'description': 'Creates a new Rust binary project named "my_project" in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramRust my_library false',
            'description': 'Creates a new Rust library project named "my_library" in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramRust my_project /path/to/dir true false',
            'description': 'Creates a new Rust binary project without tests in the specified directory'
        }
    ]
    
    def execute(self, project_name, path='.', binary='true', with_tests='true'):
        """
        Creates a basic scaffolding for a Rust program
        
        Args:
            project_name (str): Name of the Rust project to create
            path (str): Path where to create the project
            binary (str): Whether to create a binary application (true) or a library (false)
            with_tests (str): Whether to include test scaffolding
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            # Convert string parameters to appropriate types
            if isinstance(binary, str):
                binary = binary.lower() in ('true', 'yes', 'y', '1', 't')
            
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Normalize and validate project name (convert spaces to underscores, etc.)
            project_name = self._normalize_project_name(project_name)
            if not project_name:
                return {
                    "success": False,
                    "error": "Invalid project name",
                    "message": "Project name cannot be empty and must contain valid characters (letters, numbers, underscores)."
                }
            
            # Ensure path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}",
                    "message": f"Cannot create project: the specified path '{path}' does not exist."
                }
            
            # Determine full project path
            project_path = os.path.join(path, project_name)
            
            # Check if project directory already exists
            if os.path.exists(project_path):
                return {
                    "success": False,
                    "error": f"Project directory already exists: {project_path}",
                    "message": f"Cannot create project: directory '{project_path}' already exists."
                }
            
            # Initialize result dictionary
            result = {
                "success": True,
                "project_name": project_name,
                "project_path": project_path,
                "project_type": "binary" if binary else "library",
                "with_tests": with_tests,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Create project directory
            os.makedirs(project_path)
            result["files_created"].append(project_path)
            
            # Create standard Rust project structure
            self._create_src_directory(project_path, binary, result)
            
            if with_tests:
                self._create_tests_directory(project_path, result)
            
            # Create project files
            self._create_cargo_toml(project_path, project_name, binary, result)
            self._create_gitignore(project_path, result)
            self._create_readme(project_path, project_name, binary, result)
            
            # Create a descriptive message
            project_type = "binary application" if binary else "library"
            tests_msg = "with test scaffolding" if with_tests else "without tests"
            
            message = (
                f"Successfully created Rust {project_type} '{project_name}' at {project_path} {tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'cd {project_path} && cargo build' to build the project."
            )
            
            # Check if cargo is installed
            if not self._is_cargo_installed():
                message += " Note: Rust and Cargo don't appear to be installed. "
                message += "Install from https://www.rust-lang.org/tools/install to build the project."
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating Rust project: {str(e)}",
                "message": f"Failed to create Rust project scaffolding: {str(e)}",
                "project_name": project_name
            }
    
    def _normalize_project_name(self, name):
        """
        Normalize project name to follow Rust naming conventions
        
        Args:
            name (str): Raw project name
            
        Returns:
            str: Normalized project name
        """
        # Replace spaces with underscores and remove invalid chars
        normalized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        # Ensure the name starts with a letter or underscore (Rust package naming convention)
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'r_' + normalized
        return normalized.lower()
    
    def _create_src_directory(self, project_path, is_binary, result):
        """
        Create src directory with initial source files
        
        Args:
            project_path (str): Path to the project
            is_binary (bool): Whether this is a binary project
            result (dict): Result dictionary to update
        """
        src_dir = os.path.join(project_path, 'src')
        os.makedirs(src_dir)
        result["files_created"].append(src_dir)
        
        if is_binary:
            # Create main.rs for binary projects
            main_path = os.path.join(src_dir, 'main.rs')
            with open(main_path, 'w') as f:
                f.write('''fn main() {
    println!("Hello, world from Rust!");
}
''')
            result["files_created"].append(main_path)
        else:
            # Create lib.rs for library projects
            lib_path = os.path.join(src_dir, 'lib.rs')
            with open(lib_path, 'w') as f:
                f.write('''/// A sample library function.
/// 
/// # Examples
/// 
/// ```
/// let result = my_library::add(2, 3);
/// assert_eq!(result, 5);
/// ```
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 3), 5);
    }
}
''')
            result["files_created"].append(lib_path)
    
    def _create_tests_directory(self, project_path, result):
        """
        Create tests directory with sample test
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
        """
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir)
        result["files_created"].append(tests_dir)
        
        # Create integration test file
        test_path = os.path.join(tests_dir, 'integration_test.rs')
        with open(test_path, 'w') as f:
            f.write('''// Integration tests go here
#[cfg(test)]
mod integration_tests {
    // Import items from your library
    // use your_library_name::*;

    #[test]
    fn test_sample_integration() {
        assert_eq!(2 + 2, 4);
    }
}
''')
        result["files_created"].append(test_path)
    
    def _create_cargo_toml(self, project_path, project_name, is_binary, result):
        """
        Create Cargo.toml file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            is_binary (bool): Whether this is a binary project
            result (dict): Result dictionary to update
        """
        cargo_path = os.path.join(project_path, 'Cargo.toml')
        
        cargo_type = "bin" if is_binary else "lib"
        with open(cargo_path, 'w') as f:
            f.write(f'''[package]
name = "{project_name}"
version = "0.1.0"
edition = "2021"
authors = ["QZX Scaffold Generator"]

# See more keys and their definitions at https://doc.rust-lang.org/cargo/reference/manifest.html

[dependencies]
''')
            
            # Add extra configuration for library if needed
            if not is_binary:
                f.write('''
[lib]
name = "{}"
path = "src/lib.rs"
'''.format(project_name))

        result["files_created"].append(cargo_path)
    
    def _create_gitignore(self, project_path, result):
        """
        Create .gitignore file
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
        """
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''/target
**/*.rs.bk
Cargo.lock
''')
        result["files_created"].append(gitignore_path)
    
    def _create_readme(self, project_path, project_name, is_binary, result):
        """
        Create README.md file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            is_binary (bool): Whether this is a binary project
            result (dict): Result dictionary to update
        """
        readme_path = os.path.join(project_path, 'README.md')
        project_type = "Binary application" if is_binary else "Library"
        
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name}

{project_type} created with QZX scaffolding tool.

## Build

To build this project:

```
cargo build
```

## Run

To run this project:

```
cargo run
```

## Test

To run tests:

```
cargo test
```
''')
        result["files_created"].append(readme_path)
    
    def _is_cargo_installed(self):
        """
        Check if cargo (Rust build tool) is installed
        
        Returns:
            bool: True if cargo is installed, False otherwise
        """
        try:
            subprocess.run(
                ["cargo", "--version"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False 