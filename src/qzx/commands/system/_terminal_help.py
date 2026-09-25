"""Interactive terminal help rendering from command metadata."""


def render_terminal_help(terminal, arg):
    """Render general, cd-specific, or command-specific terminal help."""
    if not arg:
        _render_general_help(terminal)
        return
    command_name = arg.lower()
    if command_name == "cd":
        _render_cd_help()
        return
    _render_command_help(terminal, command_name, arg)


def _render_general_help(terminal):
    print("\nAvailable QZX commands:")
    print("=" * 70)
    commands_by_category = {}
    for entry in terminal.command_loader.get_indexed_commands():
        commands_by_category.setdefault(entry["category"], []).append(
            (entry["name"], entry["description"])
        )
    for category, commands in sorted(commands_by_category.items()):
        print(f"\n{category.upper()}:")
        for command_name, description in sorted(commands):
            print(f"  {command_name.ljust(20)} - {description}")
    print("\nTERMINAL COMMANDS:")
    print(f"  {'cd'.ljust(20)} - Change current working directory")
    print(f"  {'exit/quit'.ljust(20)} - Exit the QZX Terminal")
    print("\nFor detailed help on a specific command, type: help <command>")
    print("=" * 70)


def _render_cd_help():
    print("\nCommand: cd")
    print("Description: Change the current working directory")
    print("\nUsage: cd [directory]")
    print("  - Without arguments: changes to the user's home directory")
    print(
        "  - With argument: changes to the specified directory "
        "(absolute or relative)"
    )
    print("\nExamples:")
    print("  cd")
    print("    Changes to the user's home directory")
    print("  cd ..")
    print("    Goes up one level in the directory structure")
    print("  cd /path/to/directory")
    print("    Changes to a specific path")


def _render_command_help(terminal, command_name, original_arg):
    instance = terminal._command_instance(command_name)
    if instance is None:
        print(f"No help available for unknown command: {original_arg}")
        return

    print(f"\nCommand: {command_name}")
    print(f"Description: {instance.description}")
    print("\nParameters:")
    if instance.parameters:
        for parameter in instance.parameters:
            _render_parameter(parameter)
    else:
        print("  This command accepts no parameters")

    if instance.examples:
        print("\nExamples:")
        for example in instance.examples:
            print(f"  {example['command']}")
            print(f"    {example['description']}")
    print()


def _render_parameter(parameter):
    required = "Required" if parameter.get("required", False) else "Optional"
    default = (
        f" (Default: {parameter.get('default')})"
        if "default" in parameter
        else ""
    )
    print(
        f"  {parameter['name'].ljust(15)} - {parameter['description']} "
        f"[{required}{default}]"
    )
