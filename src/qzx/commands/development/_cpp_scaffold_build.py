"""Build-system, README, and orchestration helpers for scaffoldCpp."""

from __future__ import annotations

import os

from qzx.commands.development._scaffold_utils import (
    normalize_project_name,
    parse_scaffold_boolean,
    prepare_scaffold_project,
)


VALID_STANDARDS = {"11", "14", "17", "20"}

MAKEFILE_BASE = """# Makefile for __PROJECT__

CXX = g++
CXXFLAGS = -Wall -Wextra -std=c++__STANDARD__ -I./include
SRC_DIR = src
INCLUDE_DIR = include
BIN_DIR = bin
OBJ_DIR = obj
TEST_DIR = tests
SRC_FILES = $(wildcard $(SRC_DIR)/*.cpp)
OBJ_FILES = $(patsubst $(SRC_DIR)/%.cpp, $(OBJ_DIR)/%.o, $(SRC_FILES))
MAIN_OBJ = $(OBJ_DIR)/main.o
LIB_OBJ_FILES = $(filter-out $(MAIN_OBJ), $(OBJ_FILES))
TARGET = $(BIN_DIR)/__PROJECT__
DIRS = $(BIN_DIR) $(OBJ_DIR)

all: directories $(TARGET)

directories:
	mkdir -p $(DIRS)

$(TARGET): $(OBJ_FILES)
	$(CXX) $(CXXFLAGS) -o $@ $^

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -rf $(BIN_DIR) $(OBJ_DIR)
	rm -f $(TEST_DIR)/*_test

run: all
	./$(TARGET)

$(OBJ_FILES): | directories
"""

MAKEFILE_TESTS = """
TEST_SRC = $(wildcard $(TEST_DIR)/*.cpp)
TEST_BINS = $(patsubst $(TEST_DIR)/%.cpp, $(TEST_DIR)/%_bin, $(filter-out $(TEST_DIR)/test_main.cpp, $(TEST_SRC)))
TEST_MAIN_OBJ = $(OBJ_DIR)/test_main.o

$(TEST_MAIN_OBJ): $(TEST_DIR)/test_main.cpp
	$(CXX) $(CXXFLAGS) -I$(TEST_DIR) -c $< -o $@

tests: $(LIB_OBJ_FILES) $(TEST_MAIN_OBJ) $(TEST_BINS)

$(TEST_DIR)/%_bin: $(TEST_DIR)/%.cpp $(LIB_OBJ_FILES) $(TEST_MAIN_OBJ)
	$(CXX) $(CXXFLAGS) -I$(TEST_DIR) -o $@ $< $(LIB_OBJ_FILES)

test: tests
	@for test in $(TEST_BINS); do ./$$test || exit 1; done
"""

MAKEFILE_END = """
.PHONY: all clean run directories tests test
"""

CMAKE_BASE = """cmake_minimum_required(VERSION 3.10)
project(__PROJECT__ CXX)

set(CMAKE_CXX_STANDARD __STANDARD__)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include_directories(include)

add_library(
    __PROJECT___lib
    src/__PROJECT__.cpp
)

add_executable(
    __PROJECT__
    src/main.cpp
)

target_link_libraries(
    __PROJECT__
    PRIVATE
    __PROJECT___lib
)

install(TARGETS __PROJECT__ DESTINATION bin)
"""

CMAKE_TESTS = """
enable_testing()
include_directories(tests)

add_executable(
    test___PROJECT__
    tests/test_main.cpp
    tests/test___PROJECT__.cpp
)

target_link_libraries(
    test___PROJECT__
    PRIVATE
    __PROJECT___lib
)

add_test(
    NAME __PROJECT___tests
    COMMAND test___PROJECT__
)
"""

CMAKE_WARNINGS = """
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
elseif(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE /W4)
endif()
"""

COMPILER_FLAGS = """# Additional compiler flags configuration

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
"""

README_HEADER = """# __TITLE__

A C++__STANDARD__ project created with QZX scaffolding tool.

## Project Structure

- `include/`: Header files
- `src/`: Source files
- `tests/`: Test files (using Catch2)
"""

README_MAKE = """
## Building the Project

```bash
make
make run
make test
make clean
```
"""

README_CMAKE = """
- `cmake/`: CMake configuration modules

## Building the Project

```bash
mkdir -p build && cd build
cmake ..
cmake --build .
ctest
cmake --install .
```
"""

README_NONE = """
## Building the Project

This project does not include a build system. You can compile it manually:

```bash
g++ -std=c++__STANDARD__ -Iinclude -o __PROJECT__ src/*.cpp
./__PROJECT__
"""

README_MANUAL_TESTS = """
g++ -std=c++__STANDARD__ -Iinclude -Itests -o test___PROJECT__ tests/*.cpp src/__PROJECT__.cpp
./test___PROJECT__
```
"""

GITIGNORE = """# Build artifacts
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
"""


def scaffold_cpp_project(
    command,
    project_name,
    path=".",
    with_tests=True,
    build_system="cmake",
    cpp_standard="17",
):
    try:
        with_tests = parse_scaffold_boolean(with_tests, "with_tests")
        build_system = build_system.lower()
        failure = _configuration_failure(build_system, cpp_standard)
        if failure is not None:
            return failure
        cpp_standard = str(cpp_standard)
        project_name = normalize_project_name(
            project_name,
            replacement_characters=(" ",),
            leading_prefix="cpp_",
        )
        result = prepare_scaffold_project(
            project_name,
            path,
            {
                "with_tests": with_tests,
                "build_system": build_system,
                "cpp_standard": cpp_standard,
            },
        )
        if not result["success"]:
            return result
        return populate_cpp_project(
            command,
            project_name,
            build_system,
            with_tests,
            cpp_standard,
            result,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error creating C++ project: {str(exc)}",
            "message": f"Failed to create C++ project scaffolding: {str(exc)}",
            "project_name": project_name,
        }


def _configuration_failure(build_system, cpp_standard):
    if build_system not in {"make", "cmake", "none"}:
        return {
            "success": False,
            "error": f"Invalid build system: {build_system}",
            "message": (
                "Build system must be one of: make, cmake, none. "
                f"Got: {build_system}"
            ),
        }
    if str(cpp_standard) not in VALID_STANDARDS:
        return {
            "success": False,
            "error": f"Invalid C++ standard: {cpp_standard}",
            "message": (
                "C++ standard must be one of: 11, 14, 17, 20. "
                f"Got: {cpp_standard}"
            ),
        }
    return None


def populate_cpp_project(
    command,
    project_name,
    build_system,
    with_tests,
    cpp_standard,
    result,
):
    project_path = result["project_path"]
    command._create_src_directory(project_path, project_name, result)
    command._create_include_directory(project_path, project_name, result)
    if with_tests:
        command._create_tests_directory(project_path, project_name, result)
    if build_system == "make":
        command._create_makefile(
            project_path,
            project_name,
            with_tests,
            cpp_standard,
            result,
        )
    elif build_system == "cmake":
        command._create_cmake_files(
            project_path,
            project_name,
            with_tests,
            cpp_standard,
            result,
        )
    command._create_readme(
        project_path,
        project_name,
        build_system,
        with_tests,
        cpp_standard,
        result,
    )
    command._create_gitignore(project_path, result)
    result["message"] = success_message(
        command,
        project_name,
        project_path,
        build_system,
        with_tests,
        cpp_standard,
        result,
    )
    return result


def success_message(
    command,
    project_name,
    project_path,
    build_system,
    with_tests,
    cpp_standard,
    result,
):
    tests_msg = "with test scaffolding" if with_tests else "without tests"
    build_msg = (
        f"using {build_system}"
        if build_system != "none"
        else "without a build system"
    )
    message = (
        f"Successfully created C++ project '{project_name}' at {project_path} "
        f"{tests_msg} {build_msg} with C++{cpp_standard}. "
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
    if not command._is_cpp_compiler_installed():
        message += " Note: A C++ compiler doesn't appear to be installed. "
        message += "You will need a C++ compiler to build this project."
    return message


def create_makefile(
    project_path,
    project_name,
    with_tests,
    cpp_standard,
    result,
):
    path = os.path.join(project_path, "Makefile")
    content = _render(MAKEFILE_BASE, project_name, cpp_standard)
    if with_tests:
        content += MAKEFILE_TESTS
    content += MAKEFILE_END
    _write(path, content, result)


def create_cmake_files(
    project_path,
    project_name,
    with_tests,
    cpp_standard,
    result,
):
    path = os.path.join(project_path, "CMakeLists.txt")
    content = _render(CMAKE_BASE, project_name, cpp_standard)
    if with_tests:
        content += _render(CMAKE_TESTS, project_name, cpp_standard)
    content += CMAKE_WARNINGS
    _write(path, content, result)

    cmake_dir = os.path.join(project_path, "cmake")
    os.makedirs(cmake_dir)
    result["files_created"].append(cmake_dir)
    _write(
        os.path.join(cmake_dir, "CompilerFlags.cmake"),
        COMPILER_FLAGS,
        result,
    )


def create_readme(
    project_path,
    project_name,
    build_system,
    with_tests,
    cpp_standard,
    result,
):
    path = os.path.join(project_path, "README.md")
    content = README_HEADER.replace(
        "__TITLE__",
        project_name.replace("_", " ").title(),
    ).replace("__STANDARD__", cpp_standard)
    if build_system == "make":
        content += README_MAKE
    elif build_system == "cmake":
        content += README_CMAKE
    else:
        content += _render(README_NONE, project_name, cpp_standard)
        content += (
            _render(README_MANUAL_TESTS, project_name, cpp_standard)
            if with_tests
            else "```\n"
        )
    content += (
        f"\n## Dependencies\n\n"
        f"- C++{cpp_standard} compatible compiler (g++, clang++, MSVC, etc.)\n"
    )
    if build_system == "make":
        content += "- GNU Make\n"
    elif build_system == "cmake":
        content += "- CMake (3.10 or higher)\n"
    if with_tests:
        content += (
            "- Catch2 (included as a single header in "
            "`tests/catch2/catch.hpp`)\n"
        )
    content += "\n## License\n\n[Your License Here]\n"
    _write(path, content, result)


def create_gitignore(project_path, result):
    _write(os.path.join(project_path, ".gitignore"), GITIGNORE, result)


def _render(template, project_name, cpp_standard):
    return (
        template.replace("__PROJECT__", project_name)
        .replace("__STANDARD__", cpp_standard)
    )


def _write(path, content, result):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    result["files_created"].append(path)
