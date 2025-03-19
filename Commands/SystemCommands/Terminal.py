#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Terminal/Shell Command - Interactive shell for executing QZX commands
"""

import os
import sys
import cmd
import platform

# Use appropriate readline implementation based on platform
try:
    if platform.system() == 'Windows':
        try:
            import pyreadline3 as readline
        except ImportError:
            # Fallback if pyreadline3 is not installed
            print("Warning: pyreadline3 module not found. Command history and editing will be limited.")
            print("Install it with: pip install pyreadline3")
            readline = None
    else:
        # Unix/Linux/Mac
        import readline
except ImportError:
    print("Warning: readline module not found. Command history and editing will be limited.")
    readline = None

from Core.command_base import CommandBase
from Core.command_loader import CommandLoader

# Import the TerminalWelcome for welcome screen
from Commands.SystemCommands.TerminalWelcome import TerminalWelcome

class QZXTerminalCommand(CommandBase):
    """
    Interactive terminal/shell for QZX commands
    """
    
    name = "Terminal"
    aliases = ["terminal", "TERMINAL", "Shell", "shell", "SHELL", "Console", "console", "CONSOLE", "REPL", "repl"]
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
            'description': 'Path to history file (default: ~/.qzx_history)',
            'required': False,
            'default': os.path.expanduser('~/.qzx_history')
        },
        {
            'name': 'show_path',
            'description': 'Show path in the prompt (default: true)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx Terminal',
            'description': 'Launch the QZX interactive terminal with default settings'
        },
        {
            'command': 'qzx Shell',
            'description': 'Launch the QZX interactive terminal using the Shell alias'
        },
        {
            'command': 'qzx Terminal "MyQZX> "',
            'description': 'Launch the QZX terminal with a custom prompt'
        },
        {
            'command': 'qzx Terminal "QZX> " ~/.qzx_history false',
            'description': 'Launch the QZX terminal without showing path in prompt'
        }
    ]
    
    def execute(self, *args, **kwargs):
        """
        Launch an interactive terminal for QZX commands
        
        Args:
            prompt (str, optional): Custom prompt for the terminal
            history_file (str, optional): Path to history file
            show_path (str, optional): Whether to show path in prompt ('true' or 'false')
            
        Returns:
            Dictionary with the result of the operation
        """
        # Debug output - to see what's happening
        print(f"Terminal.execute called with args: {args}, kwargs: {kwargs}")
        
        try:
            # Parse arguments
            prompt = 'QZX> '
            history_file = None
            show_path = 'true'
            
            # Handle positional arguments
            if len(args) > 0 and args[0]:
                prompt = args[0]
            if len(args) > 1 and args[1]:
                history_file = args[1]
            if len(args) > 2 and args[2]:
                show_path = args[2]
                
            # Handle keyword arguments (override positional)
            if 'prompt' in kwargs and kwargs['prompt']:
                prompt = kwargs['prompt']
            if 'history_file' in kwargs and kwargs['history_file']:
                history_file = kwargs['history_file']
            if 'show_path' in kwargs and kwargs['show_path']:
                show_path = kwargs['show_path']
            
            # Set default history file
            if not history_file:
                history_file = os.path.expanduser('~/.qzx_history')
            
            # Convert show_path to boolean
            if isinstance(show_path, str):
                show_path = show_path.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Debug output
            print(f"Starting Terminal with prompt='{prompt}', history_file='{history_file}', show_path='{show_path}'")
            
            # Initialize the QZXTerminal
            terminal = QZXTerminal(prompt, history_file, show_path)
            
            # Start the terminal
            terminal.start()
            
            return {
                "success": True,
                "message": "QZX Terminal session ended"
            }
            
        except Exception as e:
            print(f"Error in Terminal.execute: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Error in QZX Terminal: {str(e)}"
            }


class QZXTerminal(cmd.Cmd):
    """
    Interactive terminal for QZX commands using the cmd module
    """
    
    def __init__(self, prompt='QZX> ', history_file='~/.qzx_history', show_path=True):
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
        self.history_file = os.path.expanduser(history_file)
        self.command_loader = CommandLoader()
        self.commands = self.command_loader.discover_commands()
        
        # Store initial directory
        self.initial_directory = os.getcwd()
        
        # Set the prompt with path if needed
        self._update_prompt()
        
        # Load command history (only if readline is available)
        if readline:
            self._load_history()
        
        # Create welcome screen generator
        self.welcome_generator = TerminalWelcome()
        
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
            if readline and os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
        except Exception as e:
            print(f"Error loading history: {e}")
    
    def _save_history(self):
        """Save command history to file (if readline is available)"""
        try:
            if readline:
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
            if readline:
                self._save_history()
            print("\nExiting QZX Terminal. Goodbye!")
    
    def emptyline(self):
        """Do nothing on empty line"""
        pass
    
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
        parts = line.split()
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
            cmd_obj = self.commands.get(command.lower())
            if cmd_obj:
                # Instantiate the command
                cmd_instance = cmd_obj()
                
                # Mark that this command is running inside terminal
                cmd_instance.in_terminal = True
                
                # Parse arguments (simplified version)
                parsed_args = {}
                for i, param in enumerate(cmd_instance.parameters):
                    if i < len(args):
                        param_name = param['name']
                        parsed_args[param_name] = args[i]
                
                # Execute the command
                result = cmd_instance.execute(**parsed_args)
                
                # Display the result
                if isinstance(result, dict):
                    if result.get("success") is False:
                        print(f"Error: {result.get('error', 'Unknown error')}")
                    else:
                        # First check for formatted output for terminal
                        output = result.get("output", "")
                        if output:
                            print(output)
                        else:
                            # Otherwise show regular message
                            message = result.get("message", "")
                            if message:
                                print(message)
                else:
                    print(result)
                
                # Update prompt in case directory changed
                self._update_prompt()
            else:
                print(f"Unknown command: {command}")
        except Exception as e:
            print(f"Error executing command '{command}': {str(e)}")
    
    def do_help(self, arg):
        """Show help for commands"""
        if not arg:
            # Show general help
            print("\nAvailable QZX commands:")
            print("=" * 70)
            
            # Group commands by category
            commands_by_category = {}
            for cmd_name, cmd_class in self.commands.items():
                cmd_instance = cmd_class()
                category = cmd_instance.category
                if category not in commands_by_category:
                    commands_by_category[category] = []
                
                commands_by_category[category].append((cmd_name, cmd_instance.description))
            
            # Print commands by category
            for category, cmds in sorted(commands_by_category.items()):
                print(f"\n{category.upper()}:")
                
                # Get unique commands (avoid duplicates from aliases)
                unique_cmds = {}
                for cmd_name, desc in cmds:
                    if desc not in unique_cmds.values():
                        unique_cmds[cmd_name] = desc
                
                # Print sorted commands
                for cmd_name, desc in sorted(unique_cmds.items()):
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
            cmd_class = self.commands.get(cmd_name)
            
            if cmd_class:
                cmd_instance = cmd_class()
                print(f"\nCommand: {cmd_name}")
                print(f"Description: {cmd_instance.description}")
                
                # Show aliases if present
                if hasattr(cmd_instance, 'aliases') and cmd_instance.aliases:
                    print(f"Aliases: {', '.join(cmd_instance.aliases)}")
                
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