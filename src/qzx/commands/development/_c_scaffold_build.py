"""Build-system, README, and orchestration helpers for scaffoldC."""

from __future__ import annotations

import os

from qzx.commands.development._scaffold_utils import (
    normalize_project_name,
    parse_scaffold_boolean,
    prepare_scaffold_project,
)


MAKEFILE_BASE = """# Makefile for __PROJECT__

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
TARGET = $(BIN_DIR)/__PROJECT__

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
"""

MAKEFILE_TESTS = """
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
"""

MAKEFILE_END = """
# Phony targets
.PHONY: all clean run directories tests test
"""

CMAKE_BASE = """cmake_minimum_required(VERSION 3.10)
project(__PROJECT__ C)

# Set C standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Include directories
include_directories(include)

# Add executable target
add_executable(
    __PROJECT__
    src/main.c
    src/__PROJECT__.c
)

# Installation
install(TARGETS __PROJECT__ DESTINATION bin)
"""

CMAKE_TESTS = """
# Enable testing
enable_testing()

# Add test executable
add_executable(
    test___PROJECT__
    tests/test_add.c
    src/__PROJECT__.c
)

# Add tests
add_test(NAME test_add COMMAND test___PROJECT__)
"""

README_HEADER = """# __TITLE__

A C project created with QZX scaffolding tool.

## Project Structure

- `include/`: Header files
- `src/`: Source files
- `tests/`: Test files (if applicable)

## Building the Project
"""

README_MAKE = """
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
"""

README_CMAKE = """
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
"""

README_NONE = """
This project does not include a build system. You can compile it manually:

```bash
# Compile the main program
gcc -Iinclude -o __PROJECT__ src/*.c

# Run the program
./__PROJECT__
"""

README_MANUAL_TESTS = """
# Compile and run tests
gcc -Iinclude -o test_add tests/test_add.c src/your_lib.c
./test_add
```
"""

README_DEPENDENCIES = """
## Dependencies

- C compiler (GCC recommended)
"""

GITIGNORE = """# Build artifacts
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
"""


def scaffold_c_project(
    command,
    project_name,
    path=".",
    with_tests=True,
    build_system="make",
):
    """Validate scaffoldC inputs, prepare the project, and populate its files."""
    try:
        with_tests = parse_scaffold_boolean(with_tests, "with_tests")
        build_system = build_system.lower()
        if build_system not in {"make", "cmake", "none"}:
            return {
                "success": False,
                "error": f"Invalid build system: {build_system}",
                "message": (
                    "Build system must be one of: make, cmake, none. "
                    f"Got: {build_system}"
                ),
            }
        project_name = normalize_project_name(
            project_name,
            replacement_characters=(" ",),
            leading_prefix="c_",
        )
        result = prepare_scaffold_project(
            project_name,
            path,
            {
                "with_tests": with_tests,
                "build_system": build_system,
            },
        )
        if not result["success"]:
            return result
        return populate_c_project(
            command,
            project_name,
            build_system,
            with_tests,
            result,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error creating C project: {str(exc)}",
            "message": f"Failed to create C project scaffolding: {str(exc)}",
            "project_name": project_name,
        }


def populate_c_project(command, project_name, build_system, with_tests, result):
    """Create project files through ScaffoldC compatibility hooks."""
    project_path = result["project_path"]
    command._create_src_directory(project_path, project_name, result)
    command._create_include_directory(project_path, project_name, result)
    if with_tests:
        command._create_tests_directory(project_path, project_name, result)
    if build_system == "make":
        command._create_makefile(project_path, project_name, with_tests, result)
    elif build_system == "cmake":
        command._create_cmake_files(
            project_path,
            project_name,
            with_tests,
            result,
        )
    command._create_readme(
        project_path,
        project_name,
        build_system,
        with_tests,
        result,
    )
    command._create_gitignore(project_path, result)
    result["message"] = success_message(
        command,
        project_name,
        project_path,
        build_system,
        with_tests,
        result,
    )
    return result


def success_message(
    command,
    project_name,
    project_path,
    build_system,
    with_tests,
    result,
):
    tests_msg = "with test scaffolding" if with_tests else "without tests"
    build_msg = (
        f"using {build_system}"
        if build_system != "none"
        else "without a build system"
    )
    message = (
        f"Successfully created C project '{project_name}' at {project_path} "
        f"{tests_msg} {build_msg}. "
        f"Created {len(result['files_created'])} files and directories."
    )
    if build_system == "make":
        message += f" Use 'cd {project_path} && make' to build the project."
    elif build_system == "cmake":
        message += (
            f" Use 'cd {project_path} && mkdir build && cd build && "
            "cmake .. && make' to build the project."
        )
    else:
        message += " You will need to compile the files manually."
    if not command._is_gcc_installed():
        message += " Note: GCC doesn't appear to be installed. "
        message += "You will need a C compiler to build this project."
    return message


def create_makefile(project_path, project_name, with_tests, result):
    path = os.path.join(project_path, "Makefile")
    content = MAKEFILE_BASE.replace("__PROJECT__", project_name)
    if with_tests:
        content += MAKEFILE_TESTS
    content += MAKEFILE_END
    _write(path, content, result)


def create_cmake_files(project_path, project_name, with_tests, result):
    path = os.path.join(project_path, "CMakeLists.txt")
    content = CMAKE_BASE.replace("__PROJECT__", project_name)
    if with_tests:
        content += CMAKE_TESTS.replace("__PROJECT__", project_name)
    _write(path, content, result)


def create_readme(project_path, project_name, build_system, with_tests, result):
    path = os.path.join(project_path, "README.md")
    content = README_HEADER.replace(
        "__TITLE__",
        project_name.replace("_", " ").title(),
    )
    if build_system == "make":
        content += README_MAKE
    elif build_system == "cmake":
        content += README_CMAKE
    else:
        content += README_NONE.replace("__PROJECT__", project_name)
        content += README_MANUAL_TESTS if with_tests else "```\n"
    content += README_DEPENDENCIES
    if build_system == "make":
        content += "- GNU Make\n"
    elif build_system == "cmake":
        content += "- CMake (3.10 or higher)\n"
    content += "\n## License\n\n[Your License Here]\n"
    _write(path, content, result)


def create_gitignore(project_path, result):
    path = os.path.join(project_path, ".gitignore")
    _write(path, GITIGNORE, result)


def _write(path, content, result):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    result["files_created"].append(path)
