# Guide to Building Effective QZX Commands

## Introduction

This document provides practical guidelines and patterns for developing QZX commands that follow the "Verbose is Gold" philosophy. While [philosophy.md](../philosophy.md) explains the *why* behind our approach, this document focuses on the *how* to implement it effectively.

## Repository integration

- Derive every public command from `CommandBase` and place its module under
  `src/qzx/commands/<category>/`.
- `CommandLoader` discovers command modules dynamically. Do not add a parallel
  manual registry.
- Keep `name`, aliases, description, category, parameters, examples, docstrings,
  and success/error responses aligned with the implementation.
- Every public command must have one explicit record in
  `WebsiteQZX/content/command-policies.json`. The schema records mutation,
  native execution, network, privilege and external-data facts as booleans;
  absence never means “safe”. Generation fails when a discovered command is
  missing, an obsolete command remains, a field has the wrong type, external
  data is marked without network use, or a high-risk implementation is
  described as read-only.
- Every policy review is bound to the command's transitive implementation
  digest in `WebsiteQZX/content/command-policy-reviews.json`. Changing the
  command, shared invocation path, or a local runtime dependency makes that
  review stale and blocks generation. After reviewing the current
  implementation, record the decision explicitly with:

  ```powershell
  python scripts\utils\record_command_reviews.py --scope policy --command commandName --note "What was reviewed" --apply
  ```

- The canonical English command summary comes from the class. Each published
  localized summary has a matching source digest in
  `WebsiteQZX/content/command-translation-reviews.json`; changing the English
  summary blocks generation until the translation is reviewed and recorded
  with the same utility using `--scope translation`.
- The website build regenerates all documentation projections before
  compiling, so adding a command never requires creating a PHP page by hand.
  From the repository root, run:

  ```powershell
  python scripts\utils\generate_documentation.py
  ```

- The unified entry updates product/release projections, the command catalog,
  the Markdown reference and `public/llms.txt` rendered from
  `content/llms_template.txt`. It avoids rewriting unchanged outputs. Validate
  freshness without changing files with:

  ```powershell
  python scripts\utils\generate_documentation.py --check
  ```

  The lower-level generators remain directly executable for focused debugging,
  but CI, `pnpm run build` and the production deployer enforce the unified
  projection set. A deploy using `--skip-build` remains blocked when any output
  is stale.
- `llms_template.txt` accepts only the bracketed uppercase keys declared by its
  generator, such as `[DOCUMENTED_COMMAND_COUNT]`. Unknown, missing or unused
  placeholders fail closed; edit the template prose, never `public/llms.txt`.
- Result contracts are derived conservatively from the explicit top-level
  dictionaries returned by `execute()`. A command may override `result_schema`
  when dynamic construction needs a narrower, intentional JSON Schema. The
  generator always adds the shared `success` and `message` requirements.
  Captured stdout is validated against this implementation-backed contract; it
  is an example, never the source of the schema.
- Captured stdout under
  `WebsiteQZX/content/command-evidence.json` carries the implementation digest
  of its command. If the command or a transitive local runtime dependency
  changes, generation fails until that command is executed again and its
  evidence is recaptured. Never update the digest merely to silence the check.
  Reproduce the maintained safe fixtures with:

  ```powershell
  python scripts\utils\capture_command_evidence.py --apply
  ```

  Commands without a capture expose a truthful workflow status:
  deterministic local candidate, isolated mutation, platform matrix,
  privileged/manual, or external/manual. Do not execute network, privileged,
  or dangerous evidence automatically merely to raise a coverage number.
- Run focused behavioral tests plus the applicable loader and generated-
  documentation checks. Inspect the generated changes instead of assuming that
  successful generation means the catalog is correct.
- Discovery must be read-only and deterministic. Never install a dependency,
  contact a service, or terminate the process while importing a command module.
  Optional libraries belong in package extras and must produce a structured
  `missing_dependency` result when absent.

## Public invocation contract

`CommandBase.invoke()` is the only public CLI dispatch path. It accepts both
positional values and metadata-backed named options:

```text
qzx commandName value
qzx commandName --param1 value
qzx commandName --param1=value --json
```

Declare `type` (`str`, `int`, `float`, or `bool`) in parameter metadata whenever
the default does not express it unambiguously. Mark a final repeated parameter
with `is_variadic: True`. Every published example must start with `qzx`, name a
registered command or alias, and parse successfully.

The CLI writes one JSON document to stdout in `--json` mode; incidental progress
belongs on stderr. Exit status is `0` for success, `2` for usage errors, `127`
for an unknown command, and `1` for other failures.

The default terminal presentation is generated from that same structured
result. Put the natural-language summary in `message`; expose a complete
command-specific text view in `output`, `content`, or `report` when a generic
field-by-field presentation would be less useful. Do not print dictionaries or
serialized JSON for human users. Progress may be printed while a command runs:
the CLI preserves it on the terminal and redirects it to stderr in `--json`
mode, including output emitted by child processes. The interactive `terminal`
command uses the same presenters for commands launched inside its session.
Never make the structured data poorer merely to simplify the human
presentation.

High-risk commands set the historically named
`requires_explicit_approval = True`. Preview and read-only modes do not create
archives. Before an actual mutation, `CommandBase.invoke()` creates a
fail-closed safety backup; a backup error prevents command execution. A
filesystem command must also set `backup_target_parameter` to the parameter
whose file or directory will be protected. Commands without a filesystem
target cannot create a meaningful recovery archive and require an explicit
bypass flag before execution.

The conspicuous flag `--dangerously-bypass-approvals-and-sandbox`, or its short
alias `--yolo`, executes without that safety backup. Setting
`QZX_SAFETY=YOLO` provides the same bypass globally for every high-risk command
in the process; matching is case-insensitive and ignores surrounding
whitespace. For commands with `dry_run`, either bypass also selects live
execution; for commands with `apply`, it sets `apply=true`. For dangerous
operations without a restorable path, a bypass is the required explicit
authorization. These controls affect QZX only: they do not disable
operating-system permissions, container isolation, or external service
protections. Remove `QZX_SAFETY` from the environment after its narrowly
intended use.

Safety-backup configuration:

- Destination: `QZX_BACKUPS_PATH`, defaulting to `~/QZX-Backups`.
- Format: `QZX_BACKUPS_FORMAT=ZIP|TAR.GZ|TAR`; the default is `ZIP`.
- Compression: `QZX_BACKUPS_COMPRESSION=store|fastest|fast|normal|maximum` or
  a numeric level from `0` to `9`. Aliases `none` and `uncompressed` map to
  `store`; `default` and `balanced` map to `normal`; `max`, `best`, and
  `optimal` map to `maximum`. The default is `fastest`; plain `TAR` is always
  stored without compression.

Archive names use
`QZX-Backup-YYMMDDHHMMSS-[last 30 sanitized absolute-path characters]-[QZX command]`
plus `.zip`, `.tar.gz`, or `.tar`. The structured result exposes the archive
path, protected source, format, effective compression, and byte size under
`meta.safety_backup`. Every archive contains
`__qzx_backup_manifest__.json`; if the target does not exist yet, the archive
still records that pre-operation state in its manifest.

Archives can contain the same sensitive information as their source. Protect
`QZX_BACKUPS_PATH`, monitor disk consumption, and remove archives only under an
explicit retention policy; QZX does not silently expire them.

## Basic Structure of a QZX Command

Every QZX command should follow this basic structure:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandName - Brief description of the command
"""

from qzx.core.command_base import CommandBase

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
            'type': 'str',
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

All commands inherit the standard formatter from `CommandBase`; do not copy it
into individual command classes:

```python
# Usage in result
result["disk_space"] = {
    "total_bytes": 1073741824,
    "total_formatted": self._format_bytes(1073741824),
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

## Scaffold command helpers

Language-specific scaffold commands keep their templates and toolchain logic
in their own modules, but share the mechanics that must behave consistently:

- `_scaffold_utils.normalize_project_name()` applies each ecosystem's
  separator, casing and leading-character rules.
- `_scaffold_utils.prepare_scaffold_project()` validates the destination,
  creates the project root and initializes the standard structured result.

Do not replace the language modules with a generic template engine merely to
reduce line count. Share stable mechanics; keep ecosystem-specific generation
explicit.

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
