#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramCpp Command - Creates a basic scaffolding for a C++ program
"""

import os
import shutil
import subprocess
import datetime
from Core.command_base import CommandBase

class MakeScaffProgramCppCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a C++ program.
    Creates a new C++ project with standard directory structure and basic files.
    """
    
    name = "makeScaffProgramCpp"
    aliases = ["cppScaff", "newCpp", "createCpp"]
    description = "Creates a basic scaffolding for a C++ program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the C++ project to create',
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
            'description': 'Whether to include testing scaffolding (using Catch2)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'build_system',
            'description': 'Build system to use (make, cmake, or none)',
            'required': False,
            'default': 'cmake'
        },
        {
            'name': 'cpp_standard',
            'description': 'C++ standard to use (11, 14, 17, 20)',
            'required': False,
            'default': '17'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramCpp my_project',
            'description': 'Creates a new C++ project using CMake in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramCpp my_project /path/to/dir true make 20',
            'description': 'Creates a new C++ project using Make, C++20 and tests in the specified directory'
        },
        {
            'command': 'qzx cppScaff util_library . false none 17',
            'description': 'Creates a C++ project without tests or build system in the current directory using C++17'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests='true', build_system='cmake', cpp_standard='17'):
        """
        Creates a basic scaffolding for a C++ program
        
        Args:
            project_name (str): Name of the C++ project to create
            path (str): Path where to create the project
            with_tests (str): Whether to include testing scaffolding
            build_system (str): Build system to use (make, cmake, or none)
            cpp_standard (str): C++ standard to use (11, 14, 17, 20)
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            # Convert string parameters to appropriate types
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Normalize and validate build system value
            build_system = build_system.lower()
            if build_system not in ('make', 'cmake', 'none'):
                return {
                    "success": False,
                    "error": f"Invalid build system: {build_system}",
                    "message": f"Build system must be one of: make, cmake, none. Got: {build_system}"
                }
            
            # Normalize and validate C++ standard
            valid_standards = ('11', '14', '17', '20')
            if str(cpp_standard) not in valid_standards:
                return {
                    "success": False,
                    "error": f"Invalid C++ standard: {cpp_standard}",
                    "message": f"C++ standard must be one of: {', '.join(valid_standards)}. Got: {cpp_standard}"
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
                "cpp_standard": cpp_standard,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Create project directory
            os.makedirs(project_path)
            result["files_created"].append(project_path)
            
            # Create standard C++ project structure
            self._create_src_directory(project_path, project_name, result)
            self._create_include_directory(project_path, project_name, result)
            
            if with_tests:
                self._create_tests_directory(project_path, project_name, result)
            
            # Create build system files
            if build_system == 'make':
                self._create_makefile(project_path, project_name, with_tests, cpp_standard, result)
            elif build_system == 'cmake':
                self._create_cmake_files(project_path, project_name, with_tests, cpp_standard, result)
            
            # Create other project files
            self._create_readme(project_path, project_name, build_system, with_tests, cpp_standard, result)
            self._create_gitignore(project_path, result)
            
            # Create a descriptive message
            tests_msg = "with test scaffolding" if with_tests else "without tests"
            build_msg = f"using {build_system}" if build_system != 'none' else "without a build system"
            
            message = (
                f"Successfully created C++ project '{project_name}' at {project_path} "
                f"{tests_msg} {build_msg} with C++{cpp_standard}. "
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
            
            # Check if a C++ compiler is installed
            if not self._is_cpp_compiler_installed():
                message += " Note: A C++ compiler doesn't appear to be installed. "
                message += "You will need a C++ compiler to build this project."
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating C++ project: {str(e)}",
                "message": f"Failed to create C++ project scaffolding: {str(e)}",
                "project_name": project_name
            }
    
    def _normalize_project_name(self, name):
        """
        Normalize project name to follow C++ naming conventions
        
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
            normalized = 'cpp_' + normalized
        return normalized.lower()
    
    def _create_src_directory(self, project_path, project_name, result):
        """
        Create src directory with initial C++ source files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        src_dir = os.path.join(project_path, 'src')
        os.makedirs(src_dir)
        result["files_created"].append(src_dir)
        
        # Create main.cpp
        main_path = os.path.join(src_dir, 'main.cpp')
        with open(main_path, 'w') as f:
            f.write(f'''/**
 * @file main.cpp
 * @brief Main entry point for the {project_name} program.
 */

#include <iostream>
#include <string>
#include "{project_name}.hpp"

/**
 * @brief Main function for the {project_name} program.
 *
 * @param argc Number of command-line arguments
 * @param argv Array of command-line argument strings
 * @return int Exit status code
 */
int main(int argc, char** argv) {{
    std::cout << "Hello, world from {project_name}!" << std::endl;
    
    int result = add(5, 7);
    std::cout << "5 + 7 = " << result << std::endl;
    
    Vector2D vec1{{1.0, 2.0}};
    Vector2D vec2{{3.0, 4.0}};
    Vector2D sum = vec1 + vec2;
    
    std::cout << "Vector sum: (" << sum.x << ", " << sum.y << ")" << std::endl;
    
    return 0;
}}
''')
        result["files_created"].append(main_path)
        
        # Create implementation file
        impl_path = os.path.join(src_dir, f'{project_name}.cpp')
        with open(impl_path, 'w') as f:
            f.write(f'''/**
 * @file {project_name}.cpp
 * @brief Implementation of {project_name} functionality.
 */

#include "{project_name}.hpp"

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

/**
 * @brief Add two Vector2D objects.
 *
 * @param lhs Left-hand side vector
 * @param rhs Right-hand side vector
 * @return Vector2D The sum of the two vectors
 */
Vector2D Vector2D::operator+(const Vector2D& rhs) const {{
    return Vector2D{{x + rhs.x, y + rhs.y}};
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
        header_path = os.path.join(include_dir, f'{project_name}.hpp')
        with open(header_path, 'w') as f:
            f.write(f'''/**
 * @file {project_name}.hpp
 * @brief Header file for {project_name} functionality.
 */

#ifndef {project_name.upper()}_HPP
#define {project_name.upper()}_HPP

/**
 * @brief Add two integers together.
 *
 * @param a First integer
 * @param b Second integer
 * @return int The sum of a and b
 */
int add(int a, int b);

/**
 * @brief A simple 2D vector class for demonstration.
 */
class Vector2D {{
public:
    double x;
    double y;
    
    /**
     * @brief Add two Vector2D objects.
     *
     * @param rhs Right-hand side vector
     * @return Vector2D The sum of the two vectors
     */
    Vector2D operator+(const Vector2D& rhs) const;
}};

#endif /* {project_name.upper()}_HPP */
''')
        result["files_created"].append(header_path)
    
    def _create_tests_directory(self, project_path, project_name, result):
        """
        Create tests directory with basic testing files using Catch2
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir)
        result["files_created"].append(tests_dir)
        
        # Create test main file
        test_main_path = os.path.join(tests_dir, 'test_main.cpp')
        with open(test_main_path, 'w') as f:
            f.write('''/**
 * @file test_main.cpp
 * @brief Test runner for Catch2 tests.
 */

#define CATCH_CONFIG_MAIN
#include "catch2/catch.hpp"
''')
        result["files_created"].append(test_main_path)
        
        # Create test file
        test_path = os.path.join(tests_dir, f'test_{project_name}.cpp')
        with open(test_path, 'w') as f:
            f.write(f'''/**
 * @file test_{project_name}.cpp
 * @brief Tests for {project_name} functionality.
 */

#include "catch2/catch.hpp"
#include "{project_name}.hpp"

TEST_CASE("Basic addition works", "[add]") {{
    REQUIRE(add(2, 3) == 5);
    REQUIRE(add(-1, 1) == 0);
    REQUIRE(add(0, 0) == 0);
    REQUIRE(add(100, 200) == 300);
}}

TEST_CASE("Vector2D addition works", "[vector2d]") {{
    Vector2D v1{{1.0, 2.0}};
    Vector2D v2{{3.0, 4.0}};
    
    Vector2D sum = v1 + v2;
    
    REQUIRE(sum.x == 4.0);
    REQUIRE(sum.y == 6.0);
}}
''')
        result["files_created"].append(test_path)
        
        # Create Catch2 single header file (simplified for this example)
        catch_dir = os.path.join(tests_dir, 'catch2')
        os.makedirs(catch_dir)
        result["files_created"].append(catch_dir)
        
        catch_path = os.path.join(catch_dir, 'catch.hpp')
        with open(catch_path, 'w') as f:
            f.write('''/**
 * Catch2 v2.13.9 - Single-header testing framework for C++11 and later
 *
 * This is a simplified placeholder for the actual Catch2 header.
 * In a real project, you would download the full header from:
 * https://github.com/catchorg/Catch2/releases/download/v2.13.9/catch.hpp
 *
 * Or use a package manager to install Catch2.
 */

#ifndef CATCH_HPP_INCLUDED
#define CATCH_HPP_INCLUDED

#include <string>
#include <iostream>
#include <vector>
#include <sstream>
#include <cmath>

// This is a minimal implementation just to make the scaffolding compile
// It doesn't actually run tests, just provides the macros

#define CATCH_CONFIG_MAIN

#define TEST_CASE(name, tags) \
    void CATCH_INTERNAL_UNIQUE_NAME(catch_internal_TestCase_)(void)

#define REQUIRE(expr) \
    if (!(expr)) { std::cerr << "REQUIRE failed: " #expr << std::endl; }

#define REQUIRE_FALSE(expr) \
    if (expr) { std::cerr << "REQUIRE_FALSE failed: " #expr << std::endl; }

#define CHECK(expr) \
    if (!(expr)) { std::cerr << "CHECK failed: " #expr << std::endl; }

#define SECTION(name) \
    if (true)

// Generate a unique name for the test case function
#define CATCH_INTERNAL_UNIQUE_NAME(name) \
    name##__LINE__

// Main function for the test runner
inline int main(int argc, char* argv[]) {
    std::cout << "Catch2 test framework (placeholder)" << std::endl;
    std::cout << "Compiles successfully but does not actually run tests." << std::endl;
    std::cout << "Replace with full Catch2 header in a real project." << std::endl;
    return 0;
}

#endif // CATCH_HPP_INCLUDED
''')
        result["files_created"].append(catch_path)
    
    def _create_makefile(self, project_path, project_name, with_tests, cpp_standard, result):
        """
        Create a Makefile for the project
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            with_tests (bool): Whether tests are included
            cpp_standard (str): C++ standard to use
            result (dict): Result dictionary to update
        """
        makefile_path = os.path.join(project_path, 'Makefile')
        with open(makefile_path, 'w') as f:
            f.write(f'''# Makefile for {project_name}

# Compiler settings
CXX = g++
CXXFLAGS = -Wall -Wextra -std=c++{cpp_standard} -I./include

# Project files
SRC_DIR = src
INCLUDE_DIR = include
BIN_DIR = bin
OBJ_DIR = obj
TEST_DIR = tests

# Source files
SRC_FILES = $(wildcard $(SRC_DIR)/*.cpp)
OBJ_FILES = $(patsubst $(SRC_DIR)/%.cpp, $(OBJ_DIR)/%.o, $(SRC_FILES))
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
	$(CXX) $(CXXFLAGS) -o $@ $^

# Compile .cpp files to object files
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

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
TEST_SRC = $(wildcard $(TEST_DIR)/*.cpp)
TEST_BINS = $(patsubst $(TEST_DIR)/%.cpp, $(TEST_DIR)/%_bin, $(filter-out $(TEST_DIR)/test_main.cpp, $(TEST_SRC)))
TEST_MAIN_OBJ = $(OBJ_DIR)/test_main.o

# Compile test main
$(TEST_MAIN_OBJ): $(TEST_DIR)/test_main.cpp
	$(CXX) $(CXXFLAGS) -I$(TEST_DIR) -c $< -o $@

# Build all tests
tests: $(LIB_OBJ_FILES) $(TEST_MAIN_OBJ) $(TEST_BINS)

# Compile and link a test
$(TEST_DIR)/%_bin: $(TEST_DIR)/%.cpp $(LIB_OBJ_FILES) $(TEST_MAIN_OBJ)
	$(CXX) $(CXXFLAGS) -I$(TEST_DIR) -o $@ $< $(LIB_OBJ_FILES)

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
    
    def _create_cmake_files(self, project_path, project_name, with_tests, cpp_standard, result):
        """
        Create CMake build files for the project
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            with_tests (bool): Whether tests are included
            cpp_standard (str): C++ standard to use
            result (dict): Result dictionary to update
        """
        # Create root CMakeLists.txt
        cmake_path = os.path.join(project_path, 'CMakeLists.txt')
        with open(cmake_path, 'w') as f:
            f.write(f'''cmake_minimum_required(VERSION 3.10)
project({project_name} CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD {cpp_standard})
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Include directories
include_directories(include)

# Add library target
add_library(
    {project_name}_lib
    src/{project_name}.cpp
)

# Add executable target
add_executable(
    {project_name}
    src/main.cpp
)

# Link the library to the executable
target_link_libraries(
    {project_name}
    PRIVATE
    {project_name}_lib
)

# Installation
install(TARGETS {project_name} DESTINATION bin)
''')
            
            # Add testing if included
            if with_tests:
                f.write(f'''
# Enable testing
enable_testing()

# Add the catch2 include directory
include_directories(tests)

# Add test executable
add_executable(
    test_{project_name}
    tests/test_main.cpp
    tests/test_{project_name}.cpp
)

# Link the library to the test executable
target_link_libraries(
    test_{project_name}
    PRIVATE
    {project_name}_lib
)

# Add test
add_test(
    NAME {project_name}_tests
    COMMAND test_{project_name}
)
''')
            
            # Add compiler warning flags
            f.write('''
# Add compiler warning flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
elseif(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE /W4)
endif()
''')
        
        result["files_created"].append(cmake_path)
        
        # Create CMake helpers
        cmake_config_dir = os.path.join(project_path, 'cmake')
        os.makedirs(cmake_config_dir)
        result["files_created"].append(cmake_config_dir)
        
        # Create a simple module
        compiler_flags_path = os.path.join(cmake_config_dir, 'CompilerFlags.cmake')
        with open(compiler_flags_path, 'w') as f:
            f.write('''# Additional compiler flags configuration

# Function to set compiler flags based on the compiler
function(set_project_compiler_flags target)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${target} PRIVATE 
            -Wall 
            -Wextra 
            -Wpedantic 
            -Werror
            -Wconversion
            -Wshadow
            -Wunused
        )
    elseif(MSVC)
        target_compile_options(${target} PRIVATE 
            /W4 
            /WX
            /permissive-
            /Zc:__cplusplus
        )
    endif()
endfunction()
''')
        result["files_created"].append(compiler_flags_path)
    
    def _create_readme(self, project_path, project_name, build_system, with_tests, cpp_standard, result):
        """
        Create README.md file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            build_system (str): The build system used (make, cmake, or none)
            with_tests (bool): Whether tests are included
            cpp_standard (str): C++ standard to use
            result (dict): Result dictionary to update
        """
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A C++{cpp_standard} project created with QZX scaffolding tool.

## Project Structure

- `include/`: Header files
- `src/`: Source files
- `tests/`: Test files (using Catch2)
''')
            
            if build_system == 'cmake':
                f.write('- `cmake/`: CMake configuration modules\n')
            
            f.write('''
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
cmake --build .

# Run tests (if available)
ctest

# Install (optional)
cmake --install .
```
''')
            else:
                f.write(f'''
This project does not include a build system. You can compile it manually:

```bash
# Compile the main program
g++ -std=c++{cpp_standard} -Iinclude -o {project_name} src/*.cpp

# Run the program
./{project_name}
''')
                
                if with_tests:
                    f.write(f'''
# Compile and run tests
g++ -std=c++{cpp_standard} -Iinclude -Itests -o test_{project_name} tests/*.cpp src/{project_name}.cpp
./test_{project_name}
```
''')
                else:
                    f.write('```\n')
            
            # Add additional information
            f.write(f'''
## Dependencies

- C++{cpp_standard} compatible compiler (g++, clang++, MSVC, etc.)
''')
            
            if build_system == 'make':
                f.write('- GNU Make\n')
            elif build_system == 'cmake':
                f.write('- CMake (3.10 or higher)\n')
            
            if with_tests:
                f.write('- Catch2 (included as a single header in `tests/catch2/catch.hpp`)\n')
            
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
*.dll
*.so
*.dylib

# CMake
CMakeFiles/
CMakeCache.txt
cmake_install.cmake
Makefile
*.cmake
!cmake/*.cmake
Testing/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS specific files
.DS_Store
Thumbs.db

# Compiled test binaries
tests/*_bin
tests/*_test
''')
        result["files_created"].append(gitignore_path)
    
    def _is_cpp_compiler_installed(self):
        """
        Check if a C++ compiler is installed
        
        Returns:
            bool: True if a C++ compiler is installed, False otherwise
        """
        # Try g++ first
        try:
            process = subprocess.run(
                ["g++", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if process.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Try clang++ next
        try:
            process = subprocess.run(
                ["clang++", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if process.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Try cl.exe for Windows
        try:
            process = subprocess.run(
                ["cl"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            # cl.exe returns an error code even on help, but it should output something
            if process.stderr or process.stdout:
                return True
        except FileNotFoundError:
            pass
        
        return False 