"""Explicit real Node/npm integration; may download npm development dependencies.

Run directly with standard CPython, Node.js and npm installed:
    python -B tests/integration/real_scaffold_node_integration.py -v
This diagnostic is not a replacement for the repository's release gates.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from qzx.commands.development.scaffold_javascript import ScaffoldJavaScriptCommand
from qzx.commands.development.scaffold_typescript import ScaffoldTypeScriptCommand


class NodeStarterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="qzx-node-starter-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name).resolve()
        checkout = Path(__file__).resolve().parents[2]
        self.assertFalse(self.parent.is_relative_to(checkout))
        self.node = shutil.which("node")
        self.assertIsNotNone(self.node, "Real Node.js is required; no silent skip.")
        npm_cli = Path(self.node).parent / "node_modules/npm/bin/npm-cli.js"
        if npm_cli.is_file():
            self.npm = [self.node, str(npm_cli)]
        else:
            npm = shutil.which("npm")
            self.assertIsNotNone(npm, "Real npm is required; no silent skip.")
            self.npm = ([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", npm]
                        if os.name == "nt" else [npm])

    def run_process(self, arguments, project, expected=0):
        completed = subprocess.run(
            arguments, cwd=project, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=0x08004000 if os.name == "nt" else 0,
            env=dict(os.environ, CI="1", npm_config_audit="false",
                     npm_config_fund="false", npm_config_update_notifier="false"),
        )
        evidence = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, expected, evidence)
        return completed

    def create(self, typescript, with_tests):
        factory = ScaffoldTypeScriptCommand if typescript else ScaffoldJavaScriptCommand
        result = factory().execute("Starter Demo", str(self.parent), with_tests=with_tests)
        self.assertTrue(result["success"], result)
        project = Path(result["project_path"])
        package = json.loads((project / "package.json").read_text())
        self.assertEqual(package["type"], "commonjs")
        self.assertEqual("jest" in package.get("devDependencies", {}), with_tests)
        self.assertFalse((project / "node_modules").exists())
        return project

    def assert_runnable_and_reusable(self, project, typescript):
        module = "dist/index.js" if typescript else "index.js"
        expected = "Hello, world from starter-demo!"
        direct = self.run_process([self.node, module], project)
        self.assertEqual(direct.stdout.strip(), expected)
        readme = (project / "README.md").read_text(encoding="utf-8")
        example, = re.findall(r"```js\n(.*?)```", readme, re.S)
        imported = self.run_process([self.node, "-e", example], project)
        self.assertEqual(json.loads(imported.stdout), {"greeting": expected, "sum": 5})
        self.assertEqual(len(imported.stdout.splitlines()), 1)
        self.assertEqual(imported.stderr, "")
        started = self.run_process(self.npm + ["--silent", "start"], project)
        self.assertEqual(started.stdout.strip(), expected)
        self.assertIn("Alejandro Sánchez", readme)
        self.assertIn("not the author of your application", readme)
        self.assertIn("/en/donate", readme)
        self.assertIn("/en/professional-services", readme)

    def install_tools(self, project):
        self.run_process(
            self.npm + ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
            project,
        )
        self.assertTrue((project / "package-lock.json").is_file())

    def assert_tests_fail_when_not_requested(self, project):
        result = subprocess.run(
            self.npm + ["--silent", "test"], cwd=project, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no test specified", result.stdout + result.stderr)

    def test_javascript_immediate_run_pure_import_without_installation(self):
        project = self.create(typescript=False, with_tests=False)
        self.assert_runnable_and_reusable(project, typescript=False)
        self.assertFalse((project / "node_modules").exists())
        self.assert_tests_fail_when_not_requested(project)

    def test_javascript_generated_jest_suite_and_readme(self):
        project = self.create(typescript=False, with_tests=True)
        self.assert_runnable_and_reusable(project, typescript=False)
        self.install_tools(project)
        self.run_process(self.npm + ["test", "--", "--runInBand"], project)

    def test_typescript_build_and_pure_import_without_test_scaffolding(self):
        project = self.create(typescript=True, with_tests=False)
        self.install_tools(project)
        self.run_process(self.npm + ["run", "build"], project)
        self.assertTrue((project / "dist/index.d.ts").is_file())
        self.assert_runnable_and_reusable(project, typescript=True)
        self.assert_tests_fail_when_not_requested(project)

    def test_typescript_build_development_mode_and_real_jest_suite(self):
        project = self.create(typescript=True, with_tests=True)
        self.install_tools(project)
        self.run_process(self.npm + ["run", "build"], project)
        self.assert_runnable_and_reusable(project, typescript=True)
        development = self.run_process(self.npm + ["--silent", "run", "dev"], project)
        self.assertEqual(development.stdout.strip(), "Hello, world from starter-demo!")
        self.run_process(self.npm + ["test", "--", "--runInBand"], project)

    def test_existing_files_cannot_be_overwritten_by_template_writers(self):
        for factory in (ScaffoldJavaScriptCommand, ScaffoldTypeScriptCommand):
            with self.subTest(command=factory.name):
                occupied = self.parent / "README.md"
                occupied.write_text("Owned by another writer", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    factory()._create_readme(str(self.parent), "starter", False, {})
                self.assertEqual(occupied.read_text(), "Owned by another writer")


if __name__ == "__main__":
    unittest.main()
