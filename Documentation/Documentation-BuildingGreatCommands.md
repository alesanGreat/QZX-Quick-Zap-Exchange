# Guide to Building Effective QZX Commands

## Introduction

This document provides practical guidelines and patterns for developing QZX commands that follow the "Verbose is Gold" philosophy. While [Documentation-Philosophy.md](Documentation-Philosophy.md) explains the *why* behind our approach, this document focuses on the *how* to implement it effectively.

## Basic Structure of a QZX Command

Every QZX command should follow this basic structure:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandName - Brief description of the command
"""

from Core.command_base import CommandBase

class CommandNameCommand(CommandBase):
    """
    Detailed documentation of the command class
    """
    
    name = "commandName"  # camelCase name for invocation
    aliases = ["alias1", "alias2"]  # Optional aliases
    description = "Concise description of the command's purpose"
    category = "category"  # system, file, network, etc.
    
    parameters = [
        {
            'name': 'param1',
            'description': 'Detailed description of the parameter',
            'required': True|False,
            'default': 'default_value'  # Optional if required is False
        },
        # More parameters...
    ]
    
    examples = [
        {
            'command': 'qzx commandName value1',
            'description': 'Description of what this example does'
        },
        # More examples...
    ]
    
    def execute(self, param1, param2=None):
        """
        Command implementation
        
        Args:
            param1: Description of the first parameter
            param2: Description of the second parameter and its default value
            
        Returns:
            Dictionary with structured results and status
        """
        try:
            # Main implementation
            result = {
                "success": True,
                "param1_value": param1,
                "some_result": "calculated value",
                "message": "Descriptive message of the result for humans and AI"
            }
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Technical description of the error: {str(e)}",
                "message": f"Message for humans and AI about what failed: {str(e)}"
            }
```

## Implementing the "Verbose is Gold" Philosophy

### 1. Consistent Return Structure

Each command must return a dictionary with at least these fields:

```python
result = {
    "success": True|False,  # Boolean indicator of success/failure
    "message": "Human-readable description of the result",
    # Command-specific data fields...
}
```

For handling errors:

```python
error_result = {
    "success": False,
    "error": "Technical description of the error",
    "message": "Friendly message about what failed and possible solutions"
}
```

### 2. Formatting Common Values

Follow these patterns for common values:

#### Byte Values

Always include both the numeric value and a human-readable representation:

```python
def _format_bytes(self, bytes_value):
    """Format bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024 or unit == 'TB':
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024

# Usage in result
result["disk_space"] = {
    "total_bytes": 1073741824,
    "total_formatted": "1.00 GB"
}
```

#### Percentages

Include the numeric value and context:

```python
cpu_percent = 45.7
result["cpu"] = {
    "usage_percent": cpu_percent,
    "description": f"CPU at {cpu_percent:.1f}% capacity"
}
```

#### Dates and Times

Provide multiple formats:

```python
import datetime

now = datetime.datetime.now()
result["timestamp"] = {
    "iso8601": now.isoformat(),
    "unix": int(now.timestamp()),
    "readable": now.strftime("%Y-%m-%d %H:%M:%S"),
    "relative": "5 minutes ago"  # Calculate if relevant
}
```

### 3. Descriptive Messages

Create informative messages that combine key data:

```python
# Example for a disk space command
free_gb = free_bytes / (1024**3)
total_gb = total_bytes / (1024**3)
percent_used = (total_bytes - free_bytes) / total_bytes * 100

message = (
    f"Disk {disk_name} has {free_gb:.2f} GB free out of "
    f"{total_gb:.2f} GB total ({percent_used:.1f}% used). "
)

# Add additional context as appropriate
if percent_used > 90:
    message += "Disk space is critically low. "
    message += "Consider freeing up space by removing temporary files."
elif percent_used > 75:
    message += "Disk space usage is moderately high."

result["message"] = message
```

### 4. Enriched Context

Include relevant contextual information:

```python
# For a command that operates on a file
result["file_info"] = {
    "path": file_path,
    "size": file_size,
    "size_formatted": self._format_bytes(file_size),
    "permissions": file_permissions,
    "owner": file_owner,
    "created": file_creation_time,
    "modified": file_modified_time
}

# For system context
result["system_context"] = {
    "os": platform.system(),
    "platform": sys.platform,
    "user": os.getlogin()
}
```

### 5. Practical Examples

#### Simple Command: Echo

```python
def execute(self, message):
    """Returns the provided message"""
    try:
        timestamp = datetime.datetime.now()
        
        result = {
            "success": True,
            "original_message": message,
            "length": len(message),
            "timestamp": timestamp.isoformat(),
            "message": f"Message received ({len(message)} characters): {message}"
        }
        
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing echo command: {str(e)}",
            "message": f"Could not process echo command: {str(e)}"
        }
```

#### Complex Command: System Information

```python
def execute(self):
    """Retrieves detailed system information"""
    try:
        # Collect information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Prepare detailed result
        result = {
            "success": True,
            "os": {
                "name": platform.system(),
                "version": platform.version(),
                "platform": sys.platform
            },
            "hardware": {
                "cpu": {
                    "cores": psutil.cpu_count(logical=False),
                    "threads": psutil.cpu_count(logical=True),
                    "usage_percent": psutil.cpu_percent()
                },
                "memory": {
                    "total": memory.total,
                    "total_formatted": self._format_bytes(memory.total),
                    "available": memory.available,
                    "available_formatted": self._format_bytes(memory.available),
                    "percent_used": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "total_formatted": self._format_bytes(disk.total),
                    "free": disk.free,
                    "free_formatted": self._format_bytes(disk.free),
                    "percent_used": disk.percent
                }
            }
        }
        
        # Create descriptive message
        message = (
            f"System {result['os']['name']} {result['os']['version']}. "
            f"CPU: {result['hardware']['cpu']['cores']} physical cores, "
            f"{result['hardware']['cpu']['usage_percent']}% in use. "
            f"Memory: {result['hardware']['memory']['available_formatted']} available out of "
            f"{result['hardware']['memory']['total_formatted']} "
            f"({result['hardware']['memory']['percent_used']}% in use). "
            f"Disk: {result['hardware']['disk']['free_formatted']} free out of "
            f"{result['hardware']['disk']['total_formatted']} "
            f"({result['hardware']['disk']['percent_used']}% in use)."
        )
        
        result["message"] = message
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error getting system information: {str(e)}",
            "message": f"Could not gather system information: {str(e)}"
        }
```

## Advanced Patterns

### 1. Parameter Validation

Always validate parameters with descriptive error messages:

```python
def execute(self, path, recursive=False):
    """Lists files in a directory"""
    try:
        # Parameter validation
        if not path:
            return {
                "success": False,
                "error": "No path specified",
                "message": "Cannot list files: no path was provided."
            }
        
        # Convert 'recursive' if it comes as a string
        if isinstance(recursive, str):
            recursive = recursive.lower() in ('true', 'yes', 'y', '1', 't')
        
        # Check if the path is a valid directory
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"Path does not exist: {path}",
                "message": f"Cannot list files: path '{path}' does not exist."
            }
        
        if not os.path.isdir(path):
            return {
                "success": False,
                "error": f"Path is not a directory: {path}",
                "message": f"Cannot list files: '{path}' is not a directory."
            }
        
        # Rest of implementation...
    except Exception as e:
        # Exception handling...
```

### 2. Permissions and Restrictions Handling

Clearly report permission issues:

```python
def execute(self, file_path):
    """Reads the contents of a file"""
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "message": f"Cannot read: file '{file_path}' does not exist."
            }
        
        # Check read permissions
        if not os.access(file_path, os.R_OK):
            return {
                "success": False,
                "error": f"Permission denied: {file_path}",
                "message": f"Cannot read: permission denied for '{file_path}'. Check file permissions."
            }
        
        # Rest of implementation...
    except Exception as e:
        # Exception handling...
```

### 3. Conditional Response Formatting

Adapt the response format based on context:

```python
def execute(self, query, format="default"):
    """Searches for information with customizable format"""
    try:
        # Search process...
        results = [...]  # Results obtained
        
        # Base result formatting
        formatted_results = {
            "success": True,
            "count": len(results),
            "items": results
        }
        
        # Adapt based on requested format
        if format == "simple":
            # Simplified version
            formatted_results["display"] = [item["name"] for item in results]
            message = f"Found {len(results)} results."
            
        elif format == "detailed":
            # Detailed version
            formatted_results["display"] = [
                f"{item['name']}: {item['description']} ({item['type']})"
                for item in results
            ]
            message = f"Search completed. Found {len(results)} results with full details."
            
        else:  # default
            # Intermediate format
            formatted_results["display"] = [
                f"{item['name']} ({item['type']})"
                for item in results
            ]
            message = f"Found {len(results)} results for '{query}'."
        
        formatted_results["message"] = message
        return formatted_results
        
    except Exception as e:
        # Exception handling...
```

### 4. Integrated Documentation

Leverage documentation as an opportunity to be detailed:

```python
class SearchCommand(CommandBase):
    """
    Searches for files in the system that match a pattern.
    
    This command allows for flexible file searches using different criteria
    such as name, size, or modification date. It supports regular expressions
    and wildcards for greater flexibility.
    
    Notes:
    - Searches in large directories may take time
    - On Windows systems, searches that include system paths
      may require elevated permissions
    - For content searches, use the 'grep' command instead
    """
    
    # Rest of implementation...
```

## Category-Specific Considerations

### System Commands

- Always include context about platform and operating system
- Use appropriate units for memory, CPU, etc.
- Consider security and permission implications

### Network Commands

- Provide both IP addresses and DNS names when possible
- Include performance metrics (latency, throughput)
- Handle timeouts and connectivity errors appropriately

### File Commands

- Include complete metadata (permissions, sizes, dates)
- Use absolute and relative paths as context dictates
- Implement security checks for destructive operations

### Database Commands

- Provide counts and statistics for result sets
- Include query execution times
- Handle empty results informatively

## Command Review Checklist

- [ ] Complete documentation of class and `execute` method
- [ ] At least one usage example
- [ ] Parameters with clear, descriptive names
- [ ] Validation of all input parameters
- [ ] Proper exception handling
- [ ] Descriptive message in the result
- [ ] Boolean `success` field always present
- [ ] Data hierarchically structured when complex
- [ ] Human-readable format for technical values (bytes, timestamps)
- [ ] Descriptive and actionable error in case of failure

## Additional Best Practices

1. **Message Strategy**:
   - Include what action was performed or attempted
   - Mention relevant values (filenames, etc.)
   - Add context when useful
   - For errors, suggest possible solutions

2. **Performance Considerations**:
   - For commands that may be slow, consider including execution time
   - Implement limits and pagination for large result sets
   - Include warnings when an operation might be expensive

3. **Interoperability**:
   - Use standard formats when possible (ISO for dates, etc.)
   - Consider compatibility with common tools
   - Maintain consistency with operating system conventions

4. **Accessibility**:
   - Use clear descriptions not just technical ones
   - Avoid unnecessary jargon
   - Include references to additional documentation when relevant

## Conclusion

Building effective QZX commands involves balancing informational richness with clear, consistent structure. By following these patterns and practices, you'll create commands that:

1. Are intuitive for both human users and AI agents
2. Provide complete and contextual information
3. Fail in predictable and helpful ways
4. Integrate smoothly with the rest of the QZX ecosystem

Always remember: in QZX, "Verbose is Gold." Additional structured information always adds value, especially in an environment where AI can leverage that richness to provide better results and experiences. 