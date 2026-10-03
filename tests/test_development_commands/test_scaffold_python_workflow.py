"""Run real generated starters; unit checks never impersonate an operating system."""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import unittest
import uuid
import zipfile

from qzx.commands.development.scaffold_python import ScaffoldPythonCommand
from qzx.commands.development._python_scaffold_project import (
    _complete_result,
    _create_environment,
    _failed_result,
    _write_project,
)


def _remove_tree_strict(path, attempts=12):
    last_error = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 == attempts:
                break
            time.sleep(min(0.05 * (attempt + 1), 0.25))
        else:
            return
    raise last_error


def _process_group_options():
    if os.name == "nt":
        return {
            "creationflags": (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        }
    return {"start_new_session": True}


def _terminate_process_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
        if taskkill:
            try:
                subprocess.run(
                    [taskkill, "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


class PythonStarterCase(unittest.TestCase):
    def setUp(self):
        self.root = (
            Path(tempfile.gettempdir())
            / f"qzx-python-starter-{uuid.uuid4().hex}"
        )
        self.root.mkdir(mode=0o777)
        self.addCleanup(_remove_tree_strict, self.root)

    def create(self, name="starter_demo", **options):
        result = ScaffoldPythonCommand().execute(name, str(self.root), **options)
        self.assertTrue(result["success"], result)
        return result, Path(result["project_path"])

    def run_process(self, args, cwd, *, timeout=180, **overrides):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                           PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", DO_NOT_TRACK="1")
        environment.pop("PYTHONPATH", None)
        environment.update(overrides)
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_process_group_options(),
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            raise subprocess.TimeoutExpired(
                args,
                timeout,
                output=stdout,
                stderr=stderr,
            ) from exc
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)

    def run_python(self, arguments, cwd, **overrides):
        completed = self.run_process([sys.executable, "-B", *arguments], cwd, **overrides)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed


class PythonStarterWorkflowTests(PythonStarterCase):
    def test_readme_snippet_module_and_direct_script_reach_first_success(self):
        result, project = self.create()
        readme = (project / "README.md").read_text(encoding="utf-8")
        snippets = re.findall(r"```python\n(.*?)```", readme, re.S)
        self.assertEqual(len(snippets), 1)
        for arguments in (["-m", "starter_demo"], ["main.py"], ["-c", snippets[0]]):
            with self.subTest(arguments=arguments):
                completed = self.run_python(arguments, project)
                self.assertEqual(completed.stdout.strip(), "Hello, world from starter_demo!")
        self.assertEqual(result["virtual_environment"]["status"], "not_requested")
        self.assertFalse((project / "venv").exists())
        self.assertEqual(result["warnings"], [])
        self.assertIn("python -m starter_demo", result["report"])

    def test_tested_and_testless_projects_have_consistent_metadata(self):
        for with_tests in (True, False):
            with self.subTest(with_tests=with_tests):
                _, project = self.create(f"options_{int(with_tests)}", with_tests=with_tests)
                data = tomllib.loads((project / "pyproject.toml").read_text())
                self.assertEqual(data["project"]["requires-python"], ">=3.11")
                self.assertEqual(
                    data["build-system"]["requires"],
                    ["setuptools>=77.0.3", "wheel>=0.45"],
                )
                self.assertEqual(data["project"]["dependencies"], [])
                self.assertEqual("optional-dependencies" in data["project"], with_tests)
                self.assertEqual((project / "tests").exists(), with_tests)
                self.assertFalse((project / "setup.py").exists())
                self.assertFalse((project / "requirements.txt").exists())
                self.assertNotIn("authors", data["project"])
                self.assertNotIn("urls", data["project"])
                text = (project / "README.md").read_text(encoding="utf-8")
                self.assertEqual('python -m pytest' in text, with_tests)
                self.assertEqual('.[dev]' in text, with_tests)
                self.assertIn("Alejandro Sánchez", text)
                self.assertIn("not the author of your application", text)

    def test_generated_test_suite_really_runs(self):
        _, project = self.create()
        completed = self.run_python(["-m", "pytest", "-q", "-p", "no:cacheprovider"], project)
        self.assertIn("2 passed", completed.stdout)

    def test_reserved_and_normalized_names_are_runnable(self):
        cases = {
            "class": "py_class", "os": "py_os", "tests": "py_tests",
            "venv": "py_venv", "build": "py_build", "dist": "py_dist",
            "COM1": "py_com1", "NUL": "py_nul", "123 app": "py_123_app",
            "My First-App": "my_first_app", "ｆｕｌｌｗｉｄｔｈ": "fullwidth",
        }
        for requested, expected in cases.items():
            with self.subTest(requested=requested):
                result, project = self.create(requested)
                self.assertEqual(result["project_name"], expected)
                self.assertEqual(result["requested_project_name"], requested)
                self.run_python(["-m", expected], project)

    def test_invalid_names_and_flags_fail_before_writing(self):
        for name in ("", "_", "!!!", "café", None, 123):
            with self.subTest(name=name):
                result = ScaffoldPythonCommand().execute(name, str(self.root))
                self.assertFalse(result["success"])
                self.assertEqual(list(self.root.iterdir()), [])
        for field in ("with_tests", "create_venv"):
            result = ScaffoldPythonCommand().execute("safe", str(self.root), **{field: "perhaps"})
            self.assertFalse(result["success"])
            self.assertIn(field, result["message"])
            self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_project_is_preserved_and_missing_parent_is_rejected(self):
        result, project = self.create()
        before = {str(p.relative_to(project)): p.read_bytes()
                  for p in project.rglob("*") if p.is_file()}
        rejected = ScaffoldPythonCommand().execute("starter_demo", str(self.root))
        self.assertFalse(rejected["success"])
        after = {str(p.relative_to(project)): p.read_bytes()
                 for p in project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        missing = ScaffoldPythonCommand().execute("demo", str(self.root / "missing"))
        self.assertFalse(missing["success"])
        self.assertFalse((self.root / "missing").exists())
        self.assertEqual(len(result["files_created"]), len(set(result["files_created"])))

    def test_next_steps_are_executable_argv_not_shell_strings(self):
        result, project = self.create("space parent")
        self.assertEqual([step["id"] for step in result["next_steps"]],
                         ["run", "install", "test", "build"])
        first = result["next_steps"][0]
        self.assertEqual(Path(first["cwd"]), project)
        completed = self.run_process(first["argv"], first["cwd"])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Hello, world from space_parent!")
        without, _ = self.create("without", with_tests=False)
        self.assertNotIn("test", [step["id"] for step in without["next_steps"]])

    def test_default_creation_cannot_spawn_processes_or_open_network(self):
        import qzx
        source = str(Path(qzx.__file__).parents[1])
        program = """
import sys
from qzx.commands.development.scaffold_python import ScaffoldPythonCommand
def deny(event, args):
    if event == 'subprocess.Popen' or event.startswith('socket.'):
        raise RuntimeError('Unexpected side effect: ' + event)
sys.addaudithook(deny)
result = ScaffoldPythonCommand().execute('offline_demo', sys.argv[1])
assert result['success'], result
"""
        self.run_python(["-c", program, str(self.root)], self.root, PYTHONPATH=source)
        self.assertTrue((self.root / "offline_demo" / "pyproject.toml").is_file())

    def test_write_contention_preserves_foreign_file_and_partial_inventory(self):
        sentinel = self.root / "sentinel.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        result = {"project_path": str(self.root), "files_created": [str(self.root)]}
        try:
            _write_project(result, {"created.py": "# ours\n", "sentinel.txt": "replace"})
        except FileExistsError as error:
            failure = _failed_result("interrupted", error, result)
        else:
            self.fail("Exclusive file creation must reject concurrent content.")
        self.assertEqual(sentinel.read_text(), "keep me")
        self.assertTrue(failure["partial"])
        self.assertEqual(failure["files_created"], [str(self.root), str(self.root / "created.py")])
        self.assertNotIn(str(sentinel), failure["files_created"])

    def test_public_cli_emits_a_runnable_plan_with_spaced_paths(self):
        import qzx
        source = str(Path(qzx.__file__).parents[1])
        parent = self.root / "parent with spaces"
        parent.mkdir()
        completed = self.run_python(
            ["-m", "qzx", "scaffoldPython", "CLI demo", str(parent),
             "--with-tests", "false", "--json"], parent,
            PYTHONPATH=source, QZX_TELEMETRY="0", QZX_STATE_DIR=str(self.root / "state"),
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["project_name"], "cli_demo")
        self.assertFalse(result["with_tests"])
        first = result["next_steps"][0]
        started = self.run_process(first["argv"], first["cwd"])
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(started.stdout.strip(), "Hello, world from cli_demo!")


class PythonStarterIntegrationTests(PythonStarterCase):
    def test_optional_environment_is_real_and_uses_its_own_interpreter(self):
        result, project = self.create(create_venv=True)
        environment = result["virtual_environment"]
        self.assertEqual(environment["status"], "created", environment)
        self.assertTrue((Path(environment["path"]) / "pyvenv.cfg").is_file())
        self.assertEqual(result["next_steps"][0]["argv"][0], environment["python"])
        completed = self.run_process(result["next_steps"][0]["argv"], project)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Hello, world from starter_demo!")

    def test_real_environment_failure_is_reported_without_claiming_creation(self):
        result, project = self.create()
        (project / "venv").write_text("occupied", encoding="utf-8")
        state = _create_environment(project)
        self.assertEqual(state["status"], "failed", state)
        self.assertNotIn("python", state)
        result["virtual_environment"] = state
        completed = _complete_result(result)
        self.assertTrue(completed["success"])
        self.assertTrue(completed["warnings"])
        self.assertIn("optional virtual environment failed", completed["message"])
        self.assertEqual((project / "venv").read_text(), "occupied")
        self.run_python(["-m", "starter_demo"], project)

    def test_real_wheel_build_install_and_entry_point_exclude_unrelated_packages(self):
        _, project = self.create()
        intruder = project / "unrelated_package"
        intruder.mkdir()
        (intruder / "__init__.py").write_text("SHOULD_NOT_SHIP = True\n")
        wheels = self.root / "wheels"
        wheels.mkdir()
        self.run_python(
            ["-c", "from setuptools.build_meta import build_wheel; "
             "import sys; build_wheel(sys.argv[1])", str(wheels)], project,
        )
        wheel, = wheels.glob("*.whl")
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            self.assertIn("starter_demo/__main__.py", names)
            self.assertFalse(any(n.startswith(("tests/", "unrelated_package/")) for n in names))
        installed = self.root / "installed"
        self.run_python(["-m", "pip", "install", "--no-index", "--no-deps",
                         "--target", str(installed), str(wheel)], self.root)
        program = """
import sys
from pathlib import Path
from importlib.metadata import distributions
sys.path.insert(0, sys.argv[1])
import starter_demo
assert Path(starter_demo.__file__).is_relative_to(Path(sys.argv[1]))
dist, = [d for d in distributions(path=[sys.argv[1]]) if d.metadata['Name'] == 'starter_demo']
entry, = [e for e in dist.entry_points if e.group == 'console_scripts']
assert entry.name == 'starter_demo'
raise SystemExit(entry.load()())
"""
        completed = self.run_python(["-c", program, str(installed)], self.root)
        self.assertEqual(completed.stdout.strip(), "Hello, world from starter_demo!")
        self._assert_installed_wheel_launcher(wheel)

    def _assert_installed_wheel_launcher(self, wheel):
        """Verify the native launcher from a normal installation, not pip --target."""
        environment = self.root / "wheel-env"
        self.run_python(
            ["-m", "venv", str(environment)], self.root, timeout=600
        )
        binaries = environment / ("Scripts" if os.name == "nt" else "bin")
        interpreter = binaries / ("python.exe" if os.name == "nt" else "python")
        installed = self.run_process(
            [str(interpreter), "-m", "pip", "install", "--no-index",
             "--no-deps", str(wheel)], self.root,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        launcher = binaries / ("starter_demo.exe" if os.name == "nt" else "starter_demo")
        self.assertTrue(launcher.is_file(), str(launcher))
        launched = self.run_process([str(launcher)], self.root)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertEqual(launched.stdout.strip(), "Hello, world from starter_demo!")

    def test_source_archive_rebuilds_a_wheel_and_runs_without_installation(self):
        _, project = self.create(with_tests=False)
        archives = self.root / "archives"
        archives.mkdir()
        self.run_python(
            ["-c", "from setuptools.build_meta import build_sdist; "
             "import sys; build_sdist(sys.argv[1])", str(archives)], project,
        )
        archive, = archives.glob("*.tar.gz")
        extracted = self.root / "extracted"
        with tarfile.open(archive) as source:
            source.extractall(extracted, filter="data")
        package, = extracted.iterdir()
        self.assertTrue((package / "pyproject.toml").is_file())
        self.assertTrue((package / "main.py").is_file())
        self.run_python(["main.py"], package)
        self.run_python(
            ["-c", "from setuptools.build_meta import build_wheel; "
             "import sys; build_wheel(sys.argv[1])", str(archives)], package,
        )
        self.assertEqual(len(list(archives.glob("*.whl"))), 1)

    def test_editable_install_works_outside_the_project_directory(self):
        _, project = self.create()
        environment = self.root / "editable-env"
        self.run_python(
            ["-m", "venv", "--system-site-packages", str(environment)],
            self.root,
            timeout=600,
        )
        interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        completed = self.run_process(
            [str(interpreter), "-m", "pip", "install", "--no-index", "--no-deps",
             "--no-build-isolation", "-e", str(project)],
            self.root,
            timeout=600,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        outside = self.run_process([str(interpreter), "-m", "starter_demo"], self.root)
        self.assertEqual(outside.returncode, 0, outside.stderr)
        self.assertEqual(outside.stdout.strip(), "Hello, world from starter_demo!")


if __name__ == "__main__":
    unittest.main()
