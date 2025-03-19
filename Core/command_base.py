#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Command Base - Base class for all QZX commands
"""

from abc import ABC, abstractmethod

class CommandBase(ABC):
    """
    Abstract base class that all commands must implement
    """
    
    # Command name (must be overridden by child classes)
    name = "base_command"
    
    # Command aliases (alternative names)
    aliases = []
    
    # Brief command description
    description = "Base command"
    
    # Command category (file, system, dev, etc.)
    category = "misc"
    
    # Parameters accepted by the command with their descriptions
    parameters = []
    
    # Usage examples
    examples = []
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Method that executes the command
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            The result of the command execution
        """
        pass
    
    def validate_parameters(self, args):
        """
        Validates if all required parameters are provided.
        
        Args:
            args: List of arguments passed to the command
            
        Returns:
            tuple: (is_valid, error_message)
                - is_valid: True if all required parameters are provided, False otherwise
                - error_message: Error message if validation fails, None otherwise
        """
        # Get required parameters
        required_params = [p for p in self.parameters if p.get('required', False)]
        
        # Check if we have enough arguments for required parameters
        if len(args) < len(required_params):
            missing_params = [p['name'] for p in required_params[len(args):]]
            error_message = f"Missing required parameter{'s' if len(missing_params) > 1 else ''}: {', '.join(missing_params)}"
            usage_example = self.examples[0]['command'] if self.examples else f"qzx {self.name} [parameters]"
            
            return False, f"Error: {error_message}\n\nUsage: {usage_example}\n\nUse 'qzx help {self.name}' for more information."
        
        return True, None
    
    def get_help(self):
        """
        Returns the command help
        
        Returns:
            str: Help text with description, parameters, and examples
        """
        help_text = [
            f"Command: {self.name}",
            f"Description: {self.description}",
            ""
        ]
        
        # Add aliases if they exist
        if self.aliases:
            help_text.append(f"Aliases: {', '.join(self.aliases)}")
            help_text.append("")
        
        # Add parameters
        if self.parameters:
            help_text.append("Parameters:")
            for param in self.parameters:
                param_name = param.get('name', 'unknown')
                description = param.get('description', '')
                required = param.get('required', False)
                default = param.get('default', None)
                
                required_text = "Required" if required else "Optional"
                default_text = f" (Default: {default})" if default is not None else ""
                
                help_text.append(f"  - {param_name}: {description} [{required_text}{default_text}]")
            help_text.append("")
        
        # Add examples
        if self.examples:
            help_text.append("Examples:")
            for example in self.examples:
                cmd = example.get('command', '')
                description = example.get('description', '')
                help_text.append(f"  {cmd}")
                if description:
                    help_text.append(f"    {description}")
            help_text.append("")
        
        return "\n".join(help_text)
    
    def format_result(self, result):
        """
        Ensures result is properly formatted with required fields
        
        Args:
            result: Result from the execute method
            
        Returns:
            dict: A properly formatted result dictionary with at least the 'message' field
        """
        # If result is already a dictionary
        if isinstance(result, dict):
            # Ensure it has a message field
            if 'message' not in result:
                if 'error' in result:
                    result['message'] = result['error']
                else:
                    # Try to create a default message
                    result['message'] = f"Command {self.name} executed successfully"
            return result
        
        # If result is a string or other type, wrap it in a dictionary
        return {
            "success": True,
            "result": result,
            "message": str(result)
        } 