"""Tests for shared command-level value formatting."""

from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand
from qzx.commands.file.is_file_empty import WonderIfFileEmptyCommand
from qzx.core.command_base import CommandBase


class FormattingFixtureCommand(CommandBase):
    maturity = "alpha"
    def execute(self):
        return {"success": True, "message": "fixture"}


class ForgedMetadataFixtureCommand(CommandBase):
    name = "metadataFixture"
    maturity = "alpha"

    def execute(self):
        return {
            "success": True,
            "message": "fixture",
            "meta": {
                "command": "anotherCommand",
                "command_maturity": {"stage": "stable"},
                "duration_ms": -1,
                "schema_version": 999,
                "domain_fact": "preserved",
            },
        }


def test_default_byte_units_preserve_the_historical_qzx_format():
    command = FormattingFixtureCommand()

    assert command._format_bytes(0) == "0.00 B"
    assert command._format_bytes(1024) == "1.00 KB"
    assert command._format_bytes(1024**4) == "1.00 TB"
    assert command._format_bytes(1024**5) == "1024.00 TB"


def test_commands_can_preserve_their_historical_final_unit():
    assert FindDuplicateFilesCommand()._format_bytes(1024**4) == "1024.00 GB"
    assert WonderIfFileEmptyCommand()._format_bytes(1024**5) == "1.00 PB"


def test_shared_invocation_metadata_cannot_be_spoofed_by_a_command():
    result = ForgedMetadataFixtureCommand().invoke([])

    assert result["meta"]["command"] == "metadataFixture"
    assert result["meta"]["command_maturity"]["stage"] == "alpha"
    assert result["meta"]["duration_ms"] >= 0
    assert result["meta"]["schema_version"] == 1
    assert result["meta"]["domain_fact"] == "preserved"
