"""Rust scaffold file generation and result assembly."""

from __future__ import annotations

import os
import subprocess


BINARY_SOURCE = """fn main() {
    println!(\"Hello, world from Rust!\");
}
"""

LIBRARY_SOURCE = """/// A sample library function.
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
"""

INTEGRATION_TEST = """// Integration tests go here
#[cfg(test)]
mod integration_tests {
    // Import items from your library
    // use your_library_name::*;

    #[test]
    fn test_sample_integration() {
        assert_eq!(2 + 2, 4);
    }
}
"""

GITIGNORE = """/target
**/*.rs.bk
Cargo.lock
"""

README_TEMPLATE = """# {project_name}

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
"""


def normalize_rust_project_name(name):
    """Normalize a project name to the existing Rust scaffold convention."""
    normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if normalized and not (normalized[0].isalpha() or normalized[0] == "_"):
        normalized = "r_" + normalized
    return normalized.lower()


def create_src_directory(project_path, is_binary, result):
    """Create src plus the binary or library entry point."""
    src_dir = os.path.join(project_path, "src")
    os.makedirs(src_dir)
    result["files_created"].append(src_dir)
    filename = "main.rs" if is_binary else "lib.rs"
    source = BINARY_SOURCE if is_binary else LIBRARY_SOURCE
    source_path = os.path.join(src_dir, filename)
    with open(source_path, "w", encoding="utf-8") as handle:
        handle.write(source)
    result["files_created"].append(source_path)


def create_tests_directory(project_path, result):
    """Create the Rust integration-test fixture."""
    tests_dir = os.path.join(project_path, "tests")
    os.makedirs(tests_dir)
    result["files_created"].append(tests_dir)
    test_path = os.path.join(tests_dir, "integration_test.rs")
    with open(test_path, "w", encoding="utf-8") as handle:
        handle.write(INTEGRATION_TEST)
    result["files_created"].append(test_path)


def create_cargo_toml(project_path, project_name, is_binary, result):
    """Create Cargo.toml using the existing package contract."""
    cargo_path = os.path.join(project_path, "Cargo.toml")
    content = (
        "[package]\n"
        f'name = "{project_name}"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
        'authors = ["QZX Scaffold Generator"]\n\n'
        "# See more keys and their definitions at "
        "https://doc.rust-lang.org/cargo/reference/manifest.html\n\n"
        "[dependencies]\n"
    )
    if not is_binary:
        content += f'\n[lib]\nname = "{project_name}"\npath = "src/lib.rs"\n'
    with open(cargo_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    result["files_created"].append(cargo_path)


def create_gitignore(project_path, result):
    """Create the Rust .gitignore."""
    gitignore_path = os.path.join(project_path, ".gitignore")
    with open(gitignore_path, "w", encoding="utf-8") as handle:
        handle.write(GITIGNORE)
    result["files_created"].append(gitignore_path)


def create_readme(project_path, project_name, is_binary, result):
    """Create the Rust scaffold README."""
    readme_path = os.path.join(project_path, "README.md")
    project_type = "Binary application" if is_binary else "Library"
    content = README_TEMPLATE.format(
        project_name=project_name,
        project_type=project_type,
    )
    with open(readme_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    result["files_created"].append(readme_path)


def cargo_installed():
    """Return whether Cargo can be launched."""
    try:
        subprocess.run(
            ["cargo", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return True
    except FileNotFoundError:
        return False


def build_success_message(
    project_name,
    project_path,
    binary,
    with_tests,
    result,
    cargo_probe,
):
    """Build the existing success message for scaffoldRust."""
    project_type = "binary application" if binary else "library"
    tests_msg = "with test scaffolding" if with_tests else "without tests"
    message = (
        f"Successfully created Rust {project_type} '{project_name}' at "
        f"{project_path} {tests_msg}. "
        f"Created {len(result['files_created'])} files and directories. "
        f"Use 'cd {project_path} && cargo build' to build the project."
    )
    if not cargo_probe():
        message += " Note: Rust and Cargo don't appear to be installed. "
        message += (
            "Install from https://www.rust-lang.org/tools/install to build the project."
        )
    return message


def populate_rust_project(command, project_name, binary, with_tests, result):
    """Create project files through the command's compatibility hooks."""
    project_path = result["project_path"]
    command._create_src_directory(project_path, binary, result)
    if with_tests:
        command._create_tests_directory(project_path, result)
    command._create_cargo_toml(project_path, project_name, binary, result)
    command._create_gitignore(project_path, result)
    command._create_readme(project_path, project_name, binary, result)
    result["message"] = command._build_success_message(
        project_name,
        project_path,
        binary,
        with_tests,
        result,
    )
    return result
