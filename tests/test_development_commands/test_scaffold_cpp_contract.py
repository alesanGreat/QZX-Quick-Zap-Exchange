"""Focused build-system contracts for scaffoldCpp."""

from qzx.commands.development.scaffold_cpp import ScaffoldCppCommand


class _DeterministicScaffoldCpp(ScaffoldCppCommand):
    def _is_cpp_compiler_installed(self):
        return True


def test_scaffold_cpp_make_creates_makefile_and_tests(tmp_path):
    result = _DeterministicScaffoldCpp().execute(
        "make_cpp",
        str(tmp_path),
        with_tests=True,
        build_system="make",
        cpp_standard="20",
    )

    project = tmp_path / "make_cpp"
    assert result["success"] is True
    assert (project / "Makefile").is_file()
    assert not (project / "CMakeLists.txt").exists()
    assert (project / "tests" / "test_make_cpp.cpp").is_file()
    assert "using make with C++20" in result["message"]


def test_scaffold_cpp_none_without_tests_skips_build_files(tmp_path):
    result = _DeterministicScaffoldCpp().execute(
        "plain_cpp",
        str(tmp_path),
        with_tests=False,
        build_system="none",
        cpp_standard="17",
    )

    project = tmp_path / "plain_cpp"
    assert result["success"] is True
    assert not (project / "Makefile").exists()
    assert not (project / "CMakeLists.txt").exists()
    assert not (project / "tests").exists()
    assert "without tests without a build system with C++17" in result["message"]


def test_scaffold_cpp_cmake_without_tests_omits_test_target(tmp_path):
    result = _DeterministicScaffoldCpp().execute(
        "cmake_cpp",
        str(tmp_path),
        with_tests=False,
        build_system="cmake",
        cpp_standard="14",
    )

    project = tmp_path / "cmake_cpp"
    cmake = (project / "CMakeLists.txt").read_text(encoding="utf-8")
    assert result["success"] is True
    assert "set(CMAKE_CXX_STANDARD 14)" in cmake
    assert "enable_testing()" not in cmake
    assert not (project / "tests").exists()


def test_scaffold_cpp_invalid_build_system_creates_nothing(tmp_path):
    result = _DeterministicScaffoldCpp().execute(
        "invalid_cpp",
        str(tmp_path),
        build_system="meson",
    )

    assert result["success"] is False
    assert "Invalid build system" in result["error"]
    assert list(tmp_path.iterdir()) == []


def test_scaffold_cpp_invalid_standard_creates_nothing(tmp_path):
    result = _DeterministicScaffoldCpp().execute(
        "invalid_standard",
        str(tmp_path),
        cpp_standard="23",
    )

    assert result["success"] is False
    assert "Invalid C++ standard" in result["error"]
    assert list(tmp_path.iterdir()) == []
