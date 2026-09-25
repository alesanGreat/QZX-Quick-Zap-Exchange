"""C scaffold source, header, and test file generation."""

from __future__ import annotations

import os


MAIN_C = """/**
 * @file main.c
 * @brief Main entry point for the __PROJECT__ program.
 */

#include <stdio.h>
#include <stdlib.h>
#include "__PROJECT__.h"

/**
 * @brief Main function for the __PROJECT__ program.
 *
 * @param argc Number of command-line arguments
 * @param argv Array of command-line argument strings
 * @return int Exit status code
 */
int main(int argc, char **argv) {
    printf("Hello, world from __PROJECT__!\\n");
    
    int result = add(5, 7);
    printf("5 + 7 = %d\\n", result);
    
    return EXIT_SUCCESS;
}
"""

IMPLEMENTATION_C = """/**
 * @file __PROJECT__.c
 * @brief Implementation of __PROJECT__ functionality.
 */

#include "__PROJECT__.h"

/**
 * @brief Add two integers together.
 *
 * @param a First integer
 * @param b Second integer
 * @return int The sum of a and b
 */
int add(int a, int b) {
    return a + b;
}
"""

HEADER_H = """/**
 * @file __PROJECT__.h
 * @brief Header file for __PROJECT__ functionality.
 */

#ifndef __PROJECT_UPPER___H
#define __PROJECT_UPPER___H

#ifdef __cplusplus
extern "C" {
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
}
#endif

#endif /* __PROJECT_UPPER___H */
"""

TEST_C = """/**
 * @file test_add.c
 * @brief Test for the add function.
 */

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "__PROJECT__.h"

/**
 * @brief Test the add function.
 */
void test_add() {
    assert(add(2, 3) == 5);
    assert(add(-1, 1) == 0);
    assert(add(0, 0) == 0);
    assert(add(100, 200) == 300);
    printf("All add tests passed!\\n");
}

/**
 * @brief Main function for the test suite.
 *
 * @return int Exit status code
 */
int main(void) {
    printf("Running tests for __PROJECT__\\n");
    test_add();
    printf("All tests passed!\\n");
    return EXIT_SUCCESS;
}
"""


def _project_text(template, project_name):
    return (
        template.replace("__PROJECT_UPPER__", project_name.upper())
        .replace("__PROJECT__", project_name)
    )


def create_src_directory(project_path, project_name, result):
    """Create src/main.c and the project implementation file."""
    src_dir = os.path.join(project_path, "src")
    os.makedirs(src_dir)
    result["files_created"].append(src_dir)
    _write_project_file(
        os.path.join(src_dir, "main.c"),
        MAIN_C,
        project_name,
        result,
    )
    _write_project_file(
        os.path.join(src_dir, f"{project_name}.c"),
        IMPLEMENTATION_C,
        project_name,
        result,
    )


def create_include_directory(project_path, project_name, result):
    """Create include/<project>.h."""
    include_dir = os.path.join(project_path, "include")
    os.makedirs(include_dir)
    result["files_created"].append(include_dir)
    _write_project_file(
        os.path.join(include_dir, f"{project_name}.h"),
        HEADER_H,
        project_name,
        result,
    )


def create_tests_directory(project_path, project_name, result):
    """Create the simple C test suite."""
    tests_dir = os.path.join(project_path, "tests")
    os.makedirs(tests_dir)
    result["files_created"].append(tests_dir)
    _write_project_file(
        os.path.join(tests_dir, "test_add.c"),
        TEST_C,
        project_name,
        result,
    )


def _write_project_file(path, template, project_name, result):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_project_text(template, project_name))
    result["files_created"].append(path)
