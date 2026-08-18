"""Small, dependency-free text projection shared by both welcome paths."""


def basic_welcome_message(version, *, interactive=False):
    """Return the canonical welcome text without probing the host system."""
    if interactive:
        next_steps = """Type 'listCommands' to see available commands
Type 'help <command>' to get help on a specific command
Type 'getSystemInfo' to see system information
Type 'exit' or press Ctrl+D to exit"""
    else:
        next_steps = """Run 'qzx listCommands' to see available commands
Run 'qzx help <command>' to get help on a specific command
Run 'qzx getSystemInfo' to see system information
Run 'qzx terminal' to start an interactive QZX session"""

    return """
=================================================================
Welcome Professor!

QZX - Quick Zap Exchange - Version {}
I am at your service. Ready to assist with your tasks.
=================================================================

-----------------------------------------------------------------
{}
=================================================================
""".format(version, next_steps)
