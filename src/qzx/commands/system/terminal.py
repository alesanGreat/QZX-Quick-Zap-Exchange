#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Terminal Command - Interactive prompt for executing QZX commands
"""

import os
import sys
import cmd
import contextlib
import platform
import shlex

# Use appropriate readline implementation based on platform
try:
    if platform.system() == 'Windows':
        try:
            import pyreadline3 as readline
        except ImportError:
            readline = None
    else:
        # Unix/Linux/Mac
        import readline
except ImportError:
    readline = None


from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

# Import the TerminalWelcome for welcome screen
from qzx.commands.system.terminal_welcome import TerminalWelcome

class TerminalCommand(CommandBase):
    """
    Interactive terminal/shell for QZX commands
    """
    
    name = "terminal"
    description = "Launches an interactive terminal/shell for QZX commands"
    category = "system"
    
    parameters = [
        {
            'name': 'prompt',
            'description': 'Custom prompt for the terminal (default: "QZX> ")',
            'required': False,
            'default': 'QZX> '
        },
        {
            'name': 'history_file',
            'description': 'Optional path to a persistent history file (disabled by default)',
            'required': False,
            'default': None
        },
        {
            'name': 'show_path',
            'description': 'Show path in the prompt (default: true)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx terminal',
            'description': 'Launch the QZX interactive terminal with default settings'
        },
        {
            'command': 'qzx terminal "Agent> "',
            'description': 'Launch the QZX interactive terminal with an agent prompt'
        },
        {
            'command': 'qzx terminal "MyQZX> "',
            'description': 'Launch the QZX terminal with a custom prompt'
        },
        {
            'command': 'qzx terminal "QZX> " --history_file ~/.qzx_history --show_path false',
            'description': 'Opt in to persistent history and hide the path'
        }
    ]
    
    def __init__(self, terminal_factory=None):
        super().__init__()
        self._terminal_factory = terminal_factory

    def execute(
        self,
        prompt="QZX> ",
        history_file=None,
        show_path=True,
    ):
        """Launch an interactive terminal with metadata-backed arguments."""
        if not isinstance(prompt, str):
            return {
                "success": False,
                "error_code": "invalid_prompt",
                "error": "prompt must be a string.",
                "message": "Provide a text prompt for the QZX terminal.",
            }
        if history_file is not None and not isinstance(
            history_file,
            (str, os.PathLike),
        ):
            return {
                "success": False,
                "error_code": "invalid_history_file",
                "error": "history_file must be a filesystem path or null.",
                "message": (
                    "Provide a history path, or omit history_file to keep "
                    "the interactive session ephemeral."
                ),
            }
        if isinstance(show_path, str):
            parsed_show_path = self._parse_bool(show_path)
            if parsed_show_path is None:
                return {
                    "success": False,
                    "error_code": "invalid_show_path",
                    "error": (
                        "show_path must be true or false; received "
                        f"'{show_path}'."
                    ),
                    "message": "Choose whether the terminal prompt shows the path.",
                }
            show_path = parsed_show_path
        elif not isinstance(show_path, bool):
            return {
                "success": False,
                "error_code": "invalid_show_path",
                "error": "show_path must be a boolean.",
                "message": "Choose whether the terminal prompt shows the path.",
            }

        normalized_history = (
            os.fspath(history_file)
            if history_file is not None
            else None
        )
        terminal_factory = self._terminal_factory or QZXTerminal
        try:
            terminal = terminal_factory(
                prompt,
                normalized_history,
                show_path,
            )
            terminal.start()
            return {
                "success": True,
                "message": "QZX terminal session ended.",
                "details": {
                    "prompt": prompt,
                    "history_enabled": normalized_history is not None,
                    "history_file": normalized_history,
                    "show_path": show_path,
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "error_code": "terminal_start_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "The interactive QZX terminal could not be started.",
                "details": {
                    "history_enabled": normalized_history is not None,
                    "show_path": show_path,
                },
            }



class QZXTerminal(cmd.Cmd):
    """
    Interactive terminal for QZX commands using the cmd module
    """
    
    def __init__(self, prompt='QZX> ', history_file=None, show_path=True):
        """
        Initialize the QZX Terminal
        
        Args:
            prompt (str): Command prompt
            history_file (str): Path to history file
            show_path (bool): Whether to show the current path in prompt
        """
        super().__init__()
        self.base_prompt = prompt
        self.show_path = show_path
        self.history_file = os.path.expanduser(history_file) if history_file else None
        self.command_loader = CommandLoader()
        self.commands = {
            name: None
            for name in self.command_loader.get_known_command_names()
        }
        
        # Store initial directory
        self.initial_directory = os.getcwd()
        
        # Set the prompt with path if needed
        self._update_prompt()
        
        # Load command history (only if readline is available)
        if readline and self.history_file:
            self._load_history()
        
        # Create welcome screen generator
        self.welcome_generator = TerminalWelcome(interactive=True)
        
        # Get the welcome message
        self.intro = self.welcome_generator.get_welcome_message()
    
    def _update_prompt(self):
        """Update the prompt to include the current directory if needed"""
        if self.show_path:
            # Get current directory name (not full path)
            dir_name = os.path.basename(os.getcwd())
            # Set prompt with directory
            self.prompt = f"[{dir_name}] {self.base_prompt}"
        else:
            # Use the base prompt
            self.prompt = self.base_prompt
    
    def _load_history(self):
        """Load command history from file (if readline is available)"""
        try:
            if readline and self.history_file and os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
        except Exception as e:
            print(f"Error loading history: {e}")
    
    def _save_history(self):
        """Save command history to file (if readline is available)"""
        try:
            if readline and self.history_file:
                readline.write_history_file(self.history_file)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def start(self):
        """Start the terminal loop"""
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            if readline and self.history_file:
                self._save_history()
            print("\nExiting QZX Terminal. Goodbye!")
    
    def emptyline(self):
        """Do nothing on empty line"""
        pass

    def precmd(self, line):
        """Normalize a UTF-8 BOM added by some piped Windows shell inputs."""
        return line.lstrip("\ufeff")
    
    def do_exit(self, arg):
        """Exit the QZX Terminal"""
        return True
    
    def do_quit(self, arg):
        """Exit the QZX Terminal"""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Handle Ctrl+D to exit"""
        print()  # Print a newline
        return True
    
    def default(self, line):
        """Execute QZX command"""
        try:
            parts = shlex.split(line, posix=(os.name != "nt"))
        except ValueError as exc:
            print(f"Invalid command line: {exc}")
            return
        if not parts:
            return
        
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Handle special case for help command
        if command == "help":
            if args:
                self.do_help(args[0])
            else:
                self.do_help("")
            return
        
        # Handle special case for cd command (change directory)
        if command.lower() == "cd":
            if not args:
                # No arguments, go to home directory
                os.chdir(os.path.expanduser("~"))
                print(f"Changed to home directory: {os.getcwd()}")
            else:
                # Change to specified directory
                try:
                    os.chdir(args[0])
                    print(f"Changed to directory: {os.getcwd()}")
                except Exception as e:
                    print(f"Error changing directory: {str(e)}")
            
            # Update the prompt to reflect the new directory
            self._update_prompt()
            return
        
        # Execute the command using QZX command system
        try:
            cmd_instance = self._command_instance(command)
            if cmd_instance:
                from qzx.cli import (
                    _capture_process_stdout,
                    _parse_cli_request,
                    _print_json,
                    _render_human,
                )

                json_output, _command_name, args = _parse_cli_request(
                    [command, *args]
                )

                # Use the same parser, approval gates, and result contract as
                # the regular CLI.
                stdout_context = (
                    _capture_process_stdout()
                    if json_output
                    else contextlib.nullcontext()
                )
                with stdout_context as captured_stdout:
                    result = cmd_instance.invoke(args)

                if json_output:
                    progress_output = (
                        captured_stdout.getvalue()
                        if captured_stdout
                        else ""
                    )
                    if progress_output:
                        print(progress_output, file=sys.stderr, end="")
                    _print_json(result)
                else:
                    print(_render_human(result))
                
                # Update prompt in case directory changed
                self._update_prompt()
            else:
                print(f"Unknown command: {command}")
        except Exception as e:
            print(f"Error executing command '{command}': {str(e)}")

    def _command_instance(self, command_name):
        """Resolve one interactive command without importing the full catalog."""
        command_class = self.commands.get(command_name.lower())
        if command_class is not None:
            return command_class()
        command_loader = getattr(self, "command_loader", None)
        if command_loader is None:
            return None
        return command_loader.get_command(command_name)
    
    def do_help(self, arg):
        """Show help for commands"""
        if not arg:
            # Show general help
            print("\nAvailable QZX commands:")
            print("=" * 70)
            
            # Group indexed canonical commands by category without importing
            # every implementation module.
            commands_by_category = {}
            for entry in self.command_loader.get_indexed_commands():
                category = entry["category"]
                if category not in commands_by_category:
                    commands_by_category[category] = []

                commands_by_category[category].append(
                    (entry["name"], entry["description"])
                )
            
            # Print commands by category
            for category, cmds in sorted(commands_by_category.items()):
                print(f"\n{category.upper()}:")
                
                # Print sorted commands
                for cmd_name, desc in sorted(cmds):
                    print(f"  {cmd_name.ljust(20)} - {desc}")
            
            # Show terminal-specific commands
            print("\nTERMINAL COMMANDS:")
            print(f"  {'cd'.ljust(20)} - Change current working directory")
            print(f"  {'exit/quit'.ljust(20)} - Exit the QZX Terminal")
            
            print("\nFor detailed help on a specific command, type: help <command>")
            print("=" * 70)
        else:
            # Show help for specific command
            cmd_name = arg.lower()
            
            # Special case for cd command
            if cmd_name == "cd":
                print("\nCommand: cd")
                print("Description: Change the current working directory")
                print("\nUsage: cd [directory]")
                print("  - Without arguments: changes to the user's home directory")
                print("  - With argument: changes to the specified directory (absolute or relative)")
                print("\nExamples:")
                print("  cd")
                print("    Changes to the user's home directory")
                print("  cd ..")
                print("    Goes up one level in the directory structure")
                print("  cd /path/to/directory")
                print("    Changes to a specific path")
                return
            
            # Regular command help
            cmd_instance = self._command_instance(cmd_name)

            if cmd_instance:
                print(f"\nCommand: {cmd_name}")
                print(f"Description: {cmd_instance.description}")
                
                print("\nParameters:")
                
                if cmd_instance.parameters:
                    for param in cmd_instance.parameters:
                        required = "Required" if param.get('required', False) else "Optional"
                        default = f" (Default: {param.get('default')})" if 'default' in param else ""
                        print(f"  {param['name'].ljust(15)} - {param['description']} [{required}{default}]")
                else:
                    print("  This command accepts no parameters")
                
                if cmd_instance.examples:
                    print("\nExamples:")
                    for example in cmd_instance.examples:
                        print(f"  {example['command']}")
                        print(f"    {example['description']}")
                
                print()
            else:
                print(f"No help available for unknown command: {arg}")
