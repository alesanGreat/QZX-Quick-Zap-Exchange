# QZX - Universal Command Interface for AI Agents

**QZX** (Quick Zap Exchange) provides a universal command interface enabling AI agents to execute system operations across Windows, Linux, and macOS with identical syntax, eliminating OS-specific command variations.

## Core Concept

QZX creates a uniform abstraction layer over OS-specific commands, allowing consistent syntax across systems:

```bash
qzx CreateDirectory "ProjectFolder"  # Instead of mkdir/New-Item/etc.
qzx FindText "ERROR" "logs/app.log"  # Instead of grep/findstr/Select-String
qzx ListProcesses "python"           # Instead of ps/tasklist/Get-Process
```

## Technical Features

- **Cross-platform Middleware**: Automatic translation of commands to native OS instructions
- **Structured JSON Responses**: Rich, detailed outputs with consistent schema for AI consumption
- **Advanced Pattern Recognition**: Wildcards and recursive operations with unified syntax
- **Performance Optimized**: Low overhead translation layer using native system calls
- **Intelligent Context Preservation**: Maintains environment context across command executions

## Advanced Use Cases

### Automated DevOps Pipeline

```bash
qzx CreateDirectory "Deployment/$(qzx GetCurrentDate)"
qzx RunScript "build.py" "--env=prod" "--optimize"
qzx FindLargeFiles "dist" "*.map" "1MB" -r > "large_source_maps.log"
qzx SystemInfo > "Deployment/$(qzx GetCurrentDate)/build_environment.json"
```

### System Monitoring & Diagnostics

```bash
# Comprehensive system health check
qzx GetSmartValues "/dev/sda" > "disk_health.json"
qzx GetCPULoad | jq '.cores[] | select(.usage > 80)'
qzx FindText "OOM|SEGV|FATAL" "/var/log/syslog" -r7 true true
```

### Cross-Platform Development Automation

```bash
# Create standardized project structure
qzx CreateDirectory {project_dirs}
qzx TouchFile "src/.gitkeep" ".github/workflows/.gitkeep"
qzx FindFiles "src" "*.{js,jsx,ts,tsx}" -r | xargs qzx CountLinesInFile
```

## Technical Implementation

QZX implements a command-translation layer with:

- Python core with OS-specific modules
- Consistent return schema for all commands
- Extensible architecture for custom command integration
- Detailed verbosity with minimal performance impact

## Command Categories

- **File System Operations**: CreateDirectory, CopyFile, MoveFile, DeleteFile, ChangePermissions
- **System Analysis**: SystemInfo, GetRAMInfo, GetCPULoad, GetDiskInfo, GetSmartValues
- **Process Management**: ListProcesses, KillProcess
- **Search & Data Analysis**: FindText, CountLinesInFile, FindFiles, FindLargeFiles
- **Development Tools**: RunScript, TouchFile, GetCurrentDate, GetCurrentTime

## "Verbose is Gold" Philosophy

QZX implements rich, structured responses specifically designed for AI consumption:

```json
{
  "success": true,
  "disk_info": {
    "model": "Samsung SSD 970 EVO",
    "size_bytes": 512110190592,
    "size_formatted": "512.11 GB",
    "smart_health": "PASSED",
    "temperature": 38,
    "temperature_formatted": "38°C"
  },
  "message": "Disk health check passed. Temperature normal at 38°C."
}
```

## Dependencies

- Python 3.6+
- psutil (optional, for extended system monitoring)
- smartmontools (optional, for S.M.A.R.T. diagnostics)

## Current Version

v0.02 - Updated with 42 verified commands