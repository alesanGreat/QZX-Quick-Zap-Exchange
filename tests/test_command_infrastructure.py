import os
from copy import deepcopy

import pytest

from qzx.commands.development.analyze_complexity import AnalyzeComplexityCommand
from qzx.commands.file.change_permissions import ChangePermissionsCommand
from qzx.commands.system.help import HelpCommand
from qzx.commands.system.list_commands import ListCommandsCommand
from qzx.commands.system.version import VersionCommand
from qzx.core.command_loader import CommandLoader
from qzx.core.command_index import (
    CommandIndexError,
    load_command_index,
    validate_command_index_document,
)
from qzx.core.command_lifecycle import CommandLifecycleError


def test_command_loader_discovers_commands_on_first_lookup():
    loader = CommandLoader()

    command = loader.get_command("version")

    assert command is not None
    assert command.name == "version"
    assert loader._discovered is False
    assert set(loader.command_modules) == {
        "qzx.commands.system.version",
    }
    assert loader.get_all_commands()
    assert loader._discovered is True


def test_canonical_lookup_is_lazy_for_mixed_case_command_names():
    loader = CommandLoader()

    command = loader.get_command("GETcurrentDATETIME")

    assert command is not None
    assert command.name == "getCurrentDateTime"
    assert loader._discovered is False
    assert set(loader.command_modules) == {
        "qzx.commands.system.get_current_date_time",
    }


def test_unknown_lookup_does_not_scan_catalog():
    unknown_loader = CommandLoader()

    unknown = unknown_loader.get_command("commandThatDoesNotExist")

    assert unknown is None
    assert unknown_loader._discovered is False
    assert unknown_loader.command_modules == {}


def test_command_list_uses_index_without_importing_implementations():
    command = ListCommandsCommand()

    result = command.execute()

    assert result["success"] is True
    assert result["summary"]["commands"] >= 80
    assert command.command_loader.command_modules == {}
    assert command.command_loader._discovered is False


def test_command_index_rejects_undeclared_fields():
    document = deepcopy(load_command_index())
    document["commands"][0]["legacy_aliases"] = ["oldName"]

    with pytest.raises(CommandIndexError, match="must contain exactly"):
        validate_command_index_document(document)


def test_command_index_rejects_duplicate_canonical_records():
    document = deepcopy(load_command_index())
    document["commands"].insert(1, deepcopy(document["commands"][0]))

    with pytest.raises(CommandIndexError, match="duplicate canonical"):
        validate_command_index_document(document)


def test_lifecycle_inventory_error_preserves_module_import_cause():
    loader = CommandLoader()
    loader.load_errors = {
        "qzx.commands.network.get_network_config": {
            "type": "ImportError",
            "message": "resolver backend unavailable",
            "missing_dependency": None,
        }
    }

    error = loader._lifecycle_error_with_load_context(
        CommandLifecycleError("obsolete: getNetworkConfig")
    )

    assert "obsolete: getNetworkConfig" in str(error)
    assert "qzx.commands.network.get_network_config [ImportError]" in str(error)
    assert "resolver backend unavailable" in str(error)


def test_help_and_command_list_use_lazy_discovery():
    help_result = HelpCommand().execute("version")
    list_result = ListCommandsCommand().execute("findFiles")

    assert help_result["success"] is True
    assert help_result["details"]["name"] == "version"
    assert list_result["success"] is True
    assert "findFiles" in list_result["message"]


def test_help_reports_requested_and_canonical_names():
    result = HelpCommand().execute("PROJECTLANGUAGES")

    assert result["success"] is True
    assert result["command"] == "PROJECTLANGUAGES"
    assert result["details"]["requested_name"] == "PROJECTLANGUAGES"
    assert result["details"]["canonical_name"] == "projectLanguages"


def test_public_command_inventory_is_canonical_only():
    result = ListCommandsCommand().execute()

    assert result["success"] is True
    assert result["summary"]["commands"] >= 80
    assert all("aliases" not in entry for entry in load_command_index()["commands"])


def test_command_list_structured_entries_are_deterministically_sorted():
    result = ListCommandsCommand().execute()

    for commands in result["commands"].values():
        names = [command["name"] for command in commands]
        assert names == sorted(names, key=str.lower)


def test_retired_commands_and_old_names_are_not_available():
    loader = CommandLoader()

    assert loader.get_command("systemInfo").name == "systemInfo"
    for retired_name in (
        "bootstrapProject",
        "cleanDevCaches",
        "commandsBridge",
        "compressZip",
        "createDocTemplatePython",
        "decompressZip",
        "findLargeFiles",
        "generateContent",
        "getEnvironmentInfo",
        "releaseProject",
        "WonderMyEnvironment",
    ):
        assert loader.get_command(retired_name) is None


def test_command_counts_are_consistent():
    loader = CommandLoader()
    canonical_count = len(set(loader.get_all_commands().values()))
    version_result = VersionCommand().execute()
    list_result = ListCommandsCommand().execute()

    assert version_result["qzx_info"]["command_count"] == canonical_count
    assert list_result["summary"]["commands"] == canonical_count


def test_boolean_parameter_defaults_are_typed_not_stringly_typed():
    """Published true/false defaults must use the strict shared parser."""
    loader = CommandLoader()
    string_boolean_defaults = []

    for command in set(loader.get_all_commands().values()):
        for parameter in command.parameters:
            default = parameter.get("default")
            if isinstance(default, str) and default.lower() in {
                "true",
                "false",
            }:
                string_boolean_defaults.append(
                    "{}.{}".format(command.name, parameter.get("name"))
                )

    assert string_boolean_defaults == []


def test_analyze_complexity_processes_directories(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("def sample():\n    return 1\n", encoding="utf-8")

    result = AnalyzeComplexityCommand().execute(
        str(tmp_path),
        recursive=False,
        detail_level="summary",
    )

    assert result["success"] is True
    assert "sample.py" in result["report"]
    assert result["details"]["files_analyzed"] == 1


def test_analyze_complexity_rejects_unknown_detail_level(tmp_path):
    result = AnalyzeComplexityCommand().execute(
        str(tmp_path),
        detail_level="json",
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_detail_level"


def test_change_permissions_processes_directory_recursively(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    source = nested / "sample.txt"
    source.write_text("content", encoding="utf-8")

    result = ChangePermissionsCommand().execute(str(tmp_path), "700", "-r")

    assert result["success"] is True
    assert result["items_modified"] == 3
    if os.name != "nt":
        assert source.stat().st_mode & 0o777 == 0o700
