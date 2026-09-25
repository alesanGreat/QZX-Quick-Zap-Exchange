"""Regression tests for the starters' explicit, implementation-backed contracts."""

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from qzx.commands.development._scaffold_result_schema import starter_result_schema
from qzx.commands.development.scaffold_javascript import ScaffoldJavaScriptCommand
from qzx.commands.development.scaffold_python import ScaffoldPythonCommand
from qzx.commands.development.scaffold_typescript import ScaffoldTypeScriptCommand

_COMMANDS = (ScaffoldPythonCommand, ScaffoldJavaScriptCommand, ScaffoldTypeScriptCommand)


@contextmanager
def _inheritable_temp_parent():
    path = Path(tempfile.gettempdir()) / f"qzx-schema-{uuid.uuid4().hex}"
    path.mkdir(mode=0o777)
    try:
        yield str(path)
    finally:
        if path.exists():
            shutil.rmtree(path)


class StarterResultContractTests(unittest.TestCase):
    def assert_declared_fields(self, factory, result):
        schema = factory.result_schema
        self.assertEqual(schema["type"], "object")
        self.assertTrue(set(schema["required"]).issubset(result))
        self.assertTrue(set(result).issubset(schema["properties"]), set(result))
        json.dumps(schema)
        json.dumps(result)

    def test_success_fields_and_executable_step_shapes_are_declared(self):
        for factory in _COMMANDS:
            with self.subTest(command=factory.name), _inheritable_temp_parent() as parent:
                result = factory().execute("Starter Demo", parent, with_tests=False)
                self.assertTrue(result["success"], result)
                self.assert_declared_fields(factory, result)
                self.assertTrue(Path(result["project_path"]).is_dir())
                if factory is ScaffoldPythonCommand:
                    step = factory.result_schema["properties"]["next_steps"]["items"]
                    for action in result["next_steps"]:
                        self.assertTrue(set(step["required"]).issubset(action))
                        self.assertIn(action["id"], step["properties"]["id"]["enum"])
                        self.assertTrue(all(isinstance(arg, str) for arg in action["argv"]))

    def test_invalid_options_and_existing_targets_fit_the_failure_contract(self):
        for factory in _COMMANDS:
            with self.subTest(command=factory.name), _inheritable_temp_parent() as parent:
                failed = factory().execute("starter", parent, with_tests="invalid")
                self.assertFalse(failed["success"])
                self.assert_declared_fields(factory, failed)
                self.assertFalse(list(Path(parent).iterdir()))
                created = factory().execute("starter", parent, with_tests=False)
                existing = factory().execute("starter", parent, with_tests=False)
                self.assertTrue(created["success"])
                self.assertFalse(existing["success"])
                self.assert_declared_fields(factory, existing)

    def test_schema_instances_do_not_share_mutable_nested_definitions(self):
        first = starter_result_schema(python=True)
        second = starter_result_schema(python=True)
        first["properties"]["next_steps"]["items"]["required"].clear()
        self.assertIn("argv", second["properties"]["next_steps"]["items"]["required"])
        first["properties"]["files_created"]["items"]["type"] = "integer"
        self.assertEqual(second["properties"]["files_created"]["items"]["type"], "string")
        self.assertNotIn("next_steps", starter_result_schema()["properties"])


if __name__ == "__main__":
    unittest.main()
