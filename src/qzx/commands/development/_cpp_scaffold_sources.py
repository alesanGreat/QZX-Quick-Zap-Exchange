"""C++ scaffold source, header, and test file generation."""

from __future__ import annotations

import os


MAIN_CPP = """/**
 * @file main.cpp
 * @brief Main entry point for the __PROJECT__ program.
 */

#include <iostream>
#include <string>
#include "__PROJECT__.hpp"

/**
 * @brief Main function for the __PROJECT__ program.
 *
 * @param argc Number of command-line arguments
 * @param argv Array of command-line argument strings
 * @return int Exit status code
 */
int main(int argc, char** argv) {
    std::cout << "Hello, world from __PROJECT__!" << std::endl;
    
    int result = add(5, 7);
    std::cout << "5 + 7 = " << result << std::endl;
    
    Vector2D vec1{1.0, 2.0};
    Vector2D vec2{3.0, 4.0};
    Vector2D sum = vec1 + vec2;
    
    std::cout << "Vector sum: (" << sum.x << ", " << sum.y << ")" << std::endl;
    
    return 0;
}
"""

IMPLEMENTATION_CPP = """/**
 * @file __PROJECT__.cpp
 * @brief Implementation of __PROJECT__ functionality.
 */

#include "__PROJECT__.hpp"

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

/**
 * @brief Add two Vector2D objects.
 *
 * @param lhs Left-hand side vector
 * @param rhs Right-hand side vector
 * @return Vector2D The sum of the two vectors
 */
Vector2D Vector2D::operator+(const Vector2D& rhs) const {
    return Vector2D{x + rhs.x, y + rhs.y};
}
"""

HEADER_HPP = """/**
 * @file __PROJECT__.hpp
 * @brief Header file for __PROJECT__ functionality.
 */

#ifndef __PROJECT_UPPER___HPP
#define __PROJECT_UPPER___HPP

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
class Vector2D {
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
};

#endif /* __PROJECT_UPPER___HPP */
"""

TEST_MAIN_CPP = """/**
 * @file test_main.cpp
 * @brief Test runner for Catch2 tests.
 */

#define CATCH_CONFIG_MAIN
#include "catch2/catch.hpp"
"""

TEST_CPP = """/**
 * @file test___PROJECT__.cpp
 * @brief Tests for __PROJECT__ functionality.
 */

#include "catch2/catch.hpp"
#include "__PROJECT__.hpp"

TEST_CASE("Basic addition works", "[add]") {
    REQUIRE(add(2, 3) == 5);
    REQUIRE(add(-1, 1) == 0);
    REQUIRE(add(0, 0) == 0);
    REQUIRE(add(100, 200) == 300);
}

TEST_CASE("Vector2D addition works", "[vector2d]") {
    Vector2D v1{1.0, 2.0};
    Vector2D v2{3.0, 4.0};
    
    Vector2D sum = v1 + v2;
    
    REQUIRE(sum.x == 4.0);
    REQUIRE(sum.y == 6.0);
}
"""

CATCH_HPP = """/**
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

#define CATCH_INTERNAL_UNIQUE_NAME(name) \
    name##__LINE__

inline int main(int argc, char* argv[]) {
    std::cout << "Catch2 test framework (placeholder)" << std::endl;
    std::cout << "Compiles successfully but does not actually run tests." << std::endl;
    std::cout << "Replace with full Catch2 header in a real project." << std::endl;
    return 0;
}

#endif // CATCH_HPP_INCLUDED
"""


def _project_text(template, project_name):
    return (
        template.replace("__PROJECT_UPPER__", project_name.upper())
        .replace("__PROJECT__", project_name)
    )


def create_src_directory(project_path, project_name, result):
    src_dir = os.path.join(project_path, "src")
    os.makedirs(src_dir)
    result["files_created"].append(src_dir)
    _write_project_file(
        os.path.join(src_dir, "main.cpp"),
        MAIN_CPP,
        project_name,
        result,
    )
    _write_project_file(
        os.path.join(src_dir, f"{project_name}.cpp"),
        IMPLEMENTATION_CPP,
        project_name,
        result,
    )


def create_include_directory(project_path, project_name, result):
    include_dir = os.path.join(project_path, "include")
    os.makedirs(include_dir)
    result["files_created"].append(include_dir)
    _write_project_file(
        os.path.join(include_dir, f"{project_name}.hpp"),
        HEADER_HPP,
        project_name,
        result,
    )


def create_tests_directory(project_path, project_name, result):
    tests_dir = os.path.join(project_path, "tests")
    os.makedirs(tests_dir)
    result["files_created"].append(tests_dir)
    _write(os.path.join(tests_dir, "test_main.cpp"), TEST_MAIN_CPP, result)
    _write_project_file(
        os.path.join(tests_dir, f"test_{project_name}.cpp"),
        TEST_CPP,
        project_name,
        result,
    )
    catch_dir = os.path.join(tests_dir, "catch2")
    os.makedirs(catch_dir)
    result["files_created"].append(catch_dir)
    _write(os.path.join(catch_dir, "catch.hpp"), CATCH_HPP, result)


def _write_project_file(path, template, project_name, result):
    _write(path, _project_text(template, project_name), result)


def _write(path, content, result):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    result["files_created"].append(path)
