import os

from qzx.commands.development.analyze_complexity import AnalyzeComplexityCommand
from qzx.commands.file.change_permissions import ChangePermissionsCommand
from qzx.commands.system.qzx_help import qzxHelp
from qzx.commands.system.qzx_list_commands import qzxListCommands
from qzx.commands.system.get_command_count import WonderCommandsAmountCommand
from qzx.commands.system.version import QZXVersionCommand
from qzx.core.command_loader import CommandLoader


def test_command_loader_discovers_commands_on_first_lookup():
    loader = CommandLoader()

    command = loader.get_command("version")

    assert command is not None
    assert command.name == "version"
    assert loader.get_all_commands()


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
