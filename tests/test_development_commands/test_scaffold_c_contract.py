"""Focused build-system contracts for scaffoldC."""

from qzx.commands.development.scaffold_c import ScaffoldCCommand


class _DeterministicScaffoldC(ScaffoldCCommand):
    def _is_gcc_installed(self):
        return True


def test_scaffold_c_make_creates_makefile_and_tests(tmp_path):
    result = _DeterministicScaffoldC().execute(
        "make_app",
        str(tmp_path),
        with_tests=True,
        build_system="make",
    )

    project = tmp_path / "make_app"
    assert result["success"] is True
    assert (project / "Makefile").is_file()
    assert not (project / "CMakeLists.txt").exists()
    assert (project / "tests" / "test_add.c").is_file()
    assert "using make" in result["message"]


def test_scaffold_c_none_without_tests_skips_build_files(tmp_path):
    result = _DeterministicScaffoldC().execute(
        "plain_app",
        str(tmp_path),
        with_tests=False,
        build_system="none",
    )

    project = tmp_path / "plain_app"
    assert result["success"] is True
    assert not (project / "Makefile").exists()
    assert not (project / "CMakeLists.txt").exists()
    assert not (project / "tests").exists()
    assert "without tests without a build system" in result["message"]


def test_scaffold_c_cmake_without_tests_omits_test_target(tmp_path):
    result = _DeterministicScaffoldC().execute(
        "cmake_app",
        str(tmp_path),
        with_tests=False,
        build_system="cmake",
    )

    project = tmp_path / "cmake_app"
    cmake = (project / "CMakeLists.txt").read_text(encoding="utf-8")
    assert result["success"] is True
    assert "enable_testing()" not in cmake
    assert "add_executable(\n    cmake_app" in cmake
    assert not (project / "tests").exists()


def test_scaffold_c_invalid_build_system_creates_nothing(tmp_path):
    result = _DeterministicScaffoldC().execute(
        "invalid_app",
        str(tmp_path),
        build_system="meson",
    )

    assert result["success"] is False
    assert "Invalid build system" in result["error"]
    assert list(tmp_path.iterdir()) == []
