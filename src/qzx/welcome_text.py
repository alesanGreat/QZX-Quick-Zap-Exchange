"""Small, dependency-free text projection shared by both welcome paths."""


def basic_welcome_message(version):
    """Return the canonical welcome text without probing the host system."""
    return """
=================================================================
Welcome Professor!

QZX - Quick Zap Exchange - Version {}
I am at your service. Ready to assist with your tasks.
=================================================================

-----------------------------------------------------------------
Type 'list' to see available commands
Type 'help <command>' to get help on a specific command
Type 'getSystemInfo' to see system information
Type 'exit' or press Ctrl+D to exit
=================================================================
""".format(version)
