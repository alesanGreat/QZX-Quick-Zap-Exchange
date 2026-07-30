import os
from copy import deepcopy

import pytest

from qzx.commands.development.analyze_complexity import AnalyzeComplexityCommand
from qzx.commands.file.change_permissions import ChangePermissionsCommand
from qzx.commands.system.qzx_help import qzxHelp
from qzx.commands.system.qzx_list_commands import qzxListCommands
from qzx.commands.system.get_command_count import WonderCommandsAmountCommand
from qzx.commands.system.version import QZXVersionCommand
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

    command = loader.get_command("GETcurrentDATE")

    assert command is not None
    assert command.name == "getCurrentDate"
    assert loader._discovered is False
    assert set(loader.command_modules) == {
        "qzx.commands.system.get_current_date",
    }


def test_alias_lookup_is_lazy_and_unknown_lookup_does_not_scan_catalog():
    alias_loader = CommandLoader()
    unknown_loader = CommandLoader()

    alias = alias_loader.get_command("qzxVersion")
    unknown = unknown_loader.get_command("commandThatDoesNotExist")

    assert alias.name == "version"
    assert alias_loader._discovered is False
    assert set(alias_loader.command_modules) == {
        "qzx.commands.system.version",
    }
    assert unknown is None
    assert unknown_loader._discovered is False
    assert unknown_loader.command_modules == {}


def test_command_list_uses_index_without_importing_implementations():
    command = qzxListCommands()

    result = command.execute()

    assert result["success"] is True
    assert result["summary"]["canonical_commands"] >= 90
    assert command.command_loader.command_modules == {}
    assert command.command_loader._discovered is False


def test_command_index_rejects_alias_collisions():
    document = deepcopy(load_command_index())
    document["commands"][1]["aliases"].append(
        document["commands"][0]["name"]
    )

    with pytest.raises(CommandIndexError, match="collides"):
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
    help_result = qzxHelp().execute("version")
    list_result = qzxListCommands().execute("findFiles")

    assert help_result["success"] is True
    assert help_result["details"]["name"] == "version"
    assert list_result["success"] is True
    assert "findFiles" in list_result["message"]


def test_help_identifies_alias_and_canonical_name_in_structured_details():
    result = qzxHelp().execute("auditLanguages")

    assert result["success"] is True
    assert result["command"] == "auditLanguages"
    assert result["details"]["requested_name"] == "auditLanguages"
    assert result["details"]["canonical_name"] == "projectLanguages"
    assert result["details"]["is_alias"] is True
    assert "auditLanguages" in result["details"]["aliases"]


def test_command_list_summarizes_canonical_commands_and_aliases():
    result = qzxListCommands().execute("auditLanguages")

    assert result["success"] is True
    assert result["summary"] == {
        "canonical_commands": 0,
        "aliases": 1,
        "listed_entries": 1,
        "categories": 0,
        "filter": "auditLanguages",
    }
    assert result["maturity_summary"] == {}
    assert result["commands"]["alias"][0]["canonical_name"] == "projectLanguages"
    assert "Commands: 0 canonical, 1 aliases" in result["message"]


def test_command_list_structured_entries_are_deterministically_sorted():
    result = qzxListCommands().execute()

    for commands in result["commands"].values():
        names = [command["name"] for command in commands]
        assert names == sorted(names, key=str.lower)


def test_aliases_do_not_override_canonical_commands():
    loader = CommandLoader()

    assert loader.get_command("systemInfo").name == "systemInfo"
    assert loader.get_command("WonderMyEnvironment").name == "getEnvironmentInfo"
    for alias in ("term", "shell", "console", "repl"):
        assert loader.get_command(alias).name == "terminal"


def test_command_counts_are_consistent():
    loader = CommandLoader()
    canonical_count = len(set(loader.get_all_commands().values()))
    version_result = QZXVersionCommand().execute()
    count_result = WonderCommandsAmountCommand().execute()

    assert version_result["qzx_info"]["command_count"] == canonical_count
    assert count_result["command_count"] == canonical_count
    assert count_result["total_count"] == (
        count_result["command_count"] + count_result["alias_count"]
    )


def test_analyze_complexity_processes_directories(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("def sample():\n    return 1\n", encoding="utf-8")

    result = AnalyzeComplexityCommand().execute(
        str(tmp_path),
        recursive=False,
        format="summary",
    )

    assert result["success"] is True
    assert "sample.py" in result["report"]
    assert result["details"]["files_analyzed"] == 1


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
