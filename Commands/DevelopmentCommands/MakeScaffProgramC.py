#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramC Command - Creates a basic scaffolding for a C program
"""

import os
import shutil
import subprocess
import datetime
from Core.command_base import CommandBase

class MakeScaffProgramCCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a C program.
    Creates a new C project with standard directory structure and basic files.
    """
    
    name = "makeScaffProgramC"
    aliases = ["cScaff", "newC", "createC"]
    description = "Creates a basic scaffolding for a C program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the C project to create',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path where to create the project (default: current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'with_tests',
            'description': 'Whether to include testing scaffolding',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'build_system',
            'description': 'Build system to use (make, cmake, or none)',
            'required': False,
            'default': 'make'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramC my_project',
            'description': 'Creates a new C project with Makefile in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramC my_project /path/to/dir true cmake',
            'description': 'Creates a new C project with CMake and tests in the specified directory'
        },
        {
            'command': 'qzx cScaff network_tool . false none',
            'description': 'Creates a C project without tests or build system in the current directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests='true', build_system='make'):
        """
        Creates a basic scaffolding for a C program
        
        Args:
            project_name (str): Name of the C project to create
            path (str): Path where to create the project
            with_tests (str): Whether to include testing scaffolding
            build_system (str): Build system to use (make, cmake, or none)
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            # Convert string parameters to appropriate types
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Normalize build system value
            build_system = build_system.lower()
            if build_system not in ('make', 'cmake', 'none'):
                return {
                    "success": False,
                    "error": f"Invalid build system: {build_system}",
                    "message": f"Build system must be one of: make, cmake, none. Got: {build_system}"
                }
            
            # Normalize and validate project name
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
                "with_tests": with_tests,
                "build_system": build_system,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Create project directory
            os.makedirs(project_path)
            result["files_created"].append(project_path)
            
            # Create standard C project structure
            self._create_src_directory(project_path, project_name, result)
            self._create_include_directory(project_path, project_name, result)
            
            if with_tests:
                self._create_tests_directory(project_path, project_name, result)
            
            # Create build system files
            if build_system == 'make':
                self._create_makefile(project_path, project_name, with_tests, result)
            elif build_system == 'cmake':
                self._create_cmake_files(project_path, project_name, with_tests, result)
            
            # Create other project files
            self._create_readme(project_path, project_name, build_system, with_tests, result)
            self._create_gitignore(project_path, result)
            
            # Create a descriptive message
            tests_msg = "with test scaffolding" if with_tests else "without tests"
            build_msg = f"using {build_system}" if build_system != 'none' else "without a build system"
            
            message = (
                f"Successfully created C project '{project_name}' at {project_path} "
                f"{tests_msg} {build_msg}. "
                f"Created {len(result['files_created'])} files and directories."
            )
            
            # Add build instructions based on the build system
            if build_system == 'make':
                message += f" Use 'cd {project_path} && make' to build the project."
            elif build_system == 'cmake':
                message += (
                    f" Use 'cd {project_path} && mkdir build && cd build && "
                    f"cmake .. && make' to build the project."
                )
            else:
                message += " You will need to compile the files manually."
            
            # Check if gcc is installed
            if not self._is_gcc_installed():
                message += " Note: GCC doesn't appear to be installed. "
                message += "You will need a C compiler to build this project."
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating C project: {str(e)}",
                "message": f"Failed to create C project scaffolding: {str(e)}",
                "project_name": project_name
            }
    
    def _normalize_project_name(self, name):
        """
        Normalize project name to follow C naming conventions
        
        Args:
            name (str): Raw project name
            
        Returns:
            str: Normalized project name
        """
        # Replace spaces with underscores
        normalized = name.replace(' ', '_')
        # Remove invalid characters
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        # Ensure it starts with a letter or underscore
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'c_' + normalized
        return normalized.lower()
    
    def _create_src_directory(self, project_path, project_name, result):
        """
        Create src directory with initial C source files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        src_dir = os.path.join(project_path, 'src')
        os.makedirs(src_dir)
        result["files_created"].append(src_dir)
        
        # Create main.c
        main_path = os.path.join(src_dir, 'main.c')
        with open(main_path, 'w') as f:
            f.write(f'''/**
 * @file main.c
 * @brief Main entry point for the {project_name} program.
 */

#include <stdio.h>
#include <stdlib.h>
#include "{project_name}.h"

/**
 * @brief Main function for the {project_name} program.
 *
 * @param argc Number of command-line arguments
 * @param argv Array of command-line argument strings
 * @return int Exit status code
 */
int main(int argc, char **argv) {{
    printf("Hello, world from {project_name}!\\n");
    
    int result = add(5, 7);
    printf("5 + 7 = %d\\n", result);
    
    return EXIT_SUCCESS;
}}
''')
        result["files_created"].append(main_path)
        
        # Create implementation file
        impl_path = os.path.join(src_dir, f'{project_name}.c')
        with open(impl_path, 'w') as f:
            f.write(f'''/**
 * @file {project_name}.c
 * @brief Implementation of {project_name} functionality.
 */

#include "{project_name}.h"

/**
 * @brief Add two integers together.
 *
 * @param a First integer
 * @param b Second integer
 * @return int The sum of a and b
 */
int add(int a, int b) {{
    return a + b;
}}
''')
        result["files_created"].append(impl_path)
    
    def _create_include_directory(self, project_path, project_name, result):
        """
        Create include directory with header files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        include_dir = os.path.join(project_path, 'include')
        os.makedirs(include_dir)
        result["files_created"].append(include_dir)
        
        # Create header file
        header_path = os.path.join(include_dir, f'{project_name}.h')
        with open(header_path, 'w') as f:
            f.write(f'''/**
 * @file {project_name}.h
 * @brief Header file for {project_name} functionality.
 */

#ifndef {project_name.upper()}_H
#define {project_name.upper()}_H

#ifdef __cplusplus
extern "C" {{
#endif

/**
 * @brief Add two integers together.
 *
 * @param a First integer
 * @param b Second integer
 * @return int The sum of a and b
 */
int add(int a, int b);

#ifdef __cplusplus
}}
#endif

#endif /* {project_name.upper()}_H */
''')
        result["files_created"].append(header_path)
    
    def _create_tests_directory(self, project_path, project_name, result):
        """
        Create tests directory with basic testing files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir)
        result["files_created"].append(tests_dir)
        
        # Create test file
        test_path = os.path.join(tests_dir, 'test_add.c')
        with open(test_path, 'w') as f:
            f.write(f'''/**
 * @file test_add.c
 * @brief Test for the add function.
 */

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "{project_name}.h"

/**
 * @brief Test the add function.
 */
void test_add() {{
    assert(add(2, 3) == 5);
    assert(add(-1, 1) == 0);
    assert(add(0, 0) == 0);
    assert(add(100, 200) == 300);
    printf("All add tests passed!\\n");
}}

/**
 * @brief Main function for the test suite.
 *
 * @return int Exit status code
 */
int main(void) {{
    printf("Running tests for {project_name}\\n");
    test_add();
    printf("All tests passed!\\n");
    return EXIT_SUCCESS;
}}
''')
        result["files_created"].append(test_path)
    
    def _create_makefile(self, project_path, project_name, with_tests, result):
        """
        Create a Makefile for the project
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            with_tests (bool): Whether tests are included
            result (dict): Result dictionary to update
        """
        makefile_path = os.path.join(project_path, 'Makefile')
        with open(makefile_path, 'w') as f:
            f.write(f'''# Makefile for {project_name}

# Compiler settings
CC = gcc
CFLAGS = -Wall -Wextra -g -I./include

# Project files
SRC_DIR = src
INCLUDE_DIR = include
BIN_DIR = bin
OBJ_DIR = obj
TEST_DIR = tests

# Source files
SRC_FILES = $(wildcard $(SRC_DIR)/*.c)
OBJ_FILES = $(patsubst $(SRC_DIR)/%.c, $(OBJ_DIR)/%.o, $(SRC_FILES))
MAIN_OBJ = $(OBJ_DIR)/main.o
LIB_OBJ_FILES = $(filter-out $(MAIN_OBJ), $(OBJ_FILES))

# Output binary
TARGET = $(BIN_DIR)/{project_name}

# Directories to be created
DIRS = $(BIN_DIR) $(OBJ_DIR)

# Default target
all: directories $(TARGET)

# Create necessary directories
directories:
	mkdir -p $(DIRS)

# Build the target executable
$(TARGET): $(OBJ_FILES)
	$(CC) $(CFLAGS) -o $@ $^

# Compile .c files to object files
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) $(CFLAGS) -c $< -o $@

# Clean up
clean:
	rm -rf $(BIN_DIR) $(OBJ_DIR)
	rm -f $(TEST_DIR)/*_test

# Run the program
run: all
	./$(TARGET)

# Dependencies
$(OBJ_FILES): | directories
''')
            
            # Add test targets if tests are included
            if with_tests:
                f.write(f'''
# Test targets
TEST_SRC = $(wildcard $(TEST_DIR)/*.c)
TEST_BINS = $(patsubst $(TEST_DIR)/%.c, $(TEST_DIR)/%_test, $(TEST_SRC))

# Build all tests
tests: $(LIB_OBJ_FILES) $(TEST_BINS)

# Compile and link a test
$(TEST_DIR)/%_test: $(TEST_DIR)/%.c $(LIB_OBJ_FILES)
	$(CC) $(CFLAGS) -o $@ $^

# Run all tests
test: tests
	@for test in $(TEST_BINS); do ./$$test || exit 1; done
''')
            
            # Add common targets
            f.write('''
# Phony targets
.PHONY: all clean run directories tests test
''')
        
        result["files_created"].append(makefile_path)
    
    def _create_cmake_files(self, project_path, project_name, with_tests, result):
        """
        Create CMake build files for the project
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            with_tests (bool): Whether tests are included
            result (dict): Result dictionary to update
        """
        # Create root CMakeLists.txt
        cmake_path = os.path.join(project_path, 'CMakeLists.txt')
        with open(cmake_path, 'w') as f:
            f.write(f'''cmake_minimum_required(VERSION 3.10)
project({project_name} C)

# Set C standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Include directories
include_directories(include)

# Add executable target
add_executable(
    {project_name}
    src/main.c
    src/{project_name}.c
)

# Installation
install(TARGETS {project_name} DESTINATION bin)
''')
            
            # Add testing if included
            if with_tests:
                f.write(f'''
# Enable testing
enable_testing()

# Add test executable
add_executable(
    test_{project_name}
    tests/test_add.c
    src/{project_name}.c
)

# Add tests
add_test(NAME test_add COMMAND test_{project_name})
''')
        
        result["files_created"].append(cmake_path)
    
    def _create_readme(self, project_path, project_name, build_system, with_tests, result):
        """
        Create README.md file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            build_system (str): The build system used (make, cmake, or none)
            with_tests (bool): Whether tests are included
            result (dict): Result dictionary to update
        """
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A C project created with QZX scaffolding tool.

## Project Structure

- `include/`: Header files
- `src/`: Source files
- `tests/`: Test files (if applicable)

## Building the Project
''')
            
            # Add build instructions based on the build system
            if build_system == 'make':
                f.write('''
```bash
# Build the project
make

# Run the executable
make run

# Run tests (if available)
make test

# Clean build artifacts
make clean
```
''')
            elif build_system == 'cmake':
                f.write('''
```bash
# Create a build directory
mkdir -p build && cd build

# Generate build files
cmake ..

# Build the project
make

# Run tests (if available)
ctest

# Install (optional)
make install
```
''')
            else:
                f.write(f'''
This project does not include a build system. You can compile it manually:

```bash
# Compile the main program
gcc -Iinclude -o {project_name} src/*.c

# Run the program
./{project_name}
''')
                
                if with_tests:
                    f.write('''
# Compile and run tests
gcc -Iinclude -o test_add tests/test_add.c src/your_lib.c
./test_add
```
''')
                else:
                    f.write('```\n')
            
            # Add additional information
            f.write('''
## Dependencies

- C compiler (GCC recommended)
''')
            if build_system == 'make':
                f.write('- GNU Make\n')
            elif build_system == 'cmake':
                f.write('- CMake (3.10 or higher)\n')
            
            f.write('\n## License\n\n[Your License Here]\n')
        
        result["files_created"].append(readme_path)
    
    def _create_gitignore(self, project_path, result):
        """
        Create .gitignore file
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
        """
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# Build artifacts
bin/
obj/
build/
*.o
*.out
*.exe

# Editor files
.vscode/
.idea/
*.swp
*.swo

# OS specific files
.DS_Store
Thumbs.db

# Test binaries
tests/*_test
''')
        result["files_created"].append(gitignore_path)
    
    def _is_gcc_installed(self):
        """
        Check if GCC is installed
        
        Returns:
            bool: True if GCC is installed, False otherwise
        """
        try:
            process = subprocess.run(
                ["gcc", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return process.returncode == 0
        except FileNotFoundError:
            return False 