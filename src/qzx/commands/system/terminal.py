#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Terminal Command - Interactive prompt for executing QZX commands
"""

import os
import cmd
import platform

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


from qzx.commands.system._terminal_dispatch import dispatch_terminal_line
from qzx.commands.system._terminal_help import render_terminal_help
from qzx.commands.system._terminal_session import launch_terminal
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
        return launch_terminal(
            self,
            QZXTerminal,
            prompt,
            history_file,
            show_path,
        )



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
        """Execute one interactive QZX terminal line."""
        return dispatch_terminal_line(self, line)

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
        """Show help for terminal and QZX commands."""
        return render_terminal_help(self, arg)
