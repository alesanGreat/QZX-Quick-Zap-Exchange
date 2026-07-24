"""Tests for shared command-level value formatting."""

from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand
from qzx.commands.file.is_file_empty import WonderIfFileEmptyCommand
from qzx.core.command_base import CommandBase


class FormattingFixtureCommand(CommandBase):
    def execute(self):
        return {"success": True, "message": "fixture"}


def test_default_byte_units_preserve_the_historical_qzx_format():
    command = FormattingFixtureCommand()

    assert command._format_bytes(0) == "0.00 B"
    assert command._format_bytes(1024) == "1.00 KB"
    assert command._format_bytes(1024**4) == "1.00 TB"
    assert command._format_bytes(1024**5) == "1024.00 TB"


def test_commands_can_preserve_their_historical_final_unit():
    assert FindDuplicateFilesCommand()._format_bytes(1024**4) == "1024.00 GB"
    assert WonderIfFileEmptyCommand()._format_bytes(1024**5) == "1.00 PB"
