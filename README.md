# QZX — Quick Zap Exchange

> **Unix says: "silence is gold."**
> For humans reading a terminal, that's elegant.
> For AI agents, silence is a dead end.

When an AI agent runs a command and gets no output, it doesn't know what happened. Did it succeed? Did it fail silently? It has to run *another* command to verify. Then maybe another. Every silent operation costs tokens, roundtrips, and reasoning cycles — and still leaves room for doubt.

**QZX is built on the opposite principle: verbose is gold.**

Every QZX command returns structured JSON with an explicit `success` field, a human-readable message, and rich contextual data — on every platform, every time, without flags or special modes.

---

## The Problem in Concrete Terms

To get basic system information, an AI agent without QZX needs to:

**On Linux:** `uname -a` + `cat /proc/cpuinfo` + `free -h` + `df -h` — then parse four different text formats.

**On Windows:** `systeminfo` + `wmic cpu get name` + `wmic memorychip get capacity` + `wmic logicaldisk get size,freespace` — then parse four different text formats again, differently.

**On macOS:** `sw_vers` + `sysctl -n machdep.cpu.brand_string` + `vm_stat` + `df -h` — four more, formatted differently from both.

**With QZX, on any platform:**

```bash
qzx SystemInfo
```

```json
{
  "success": true,
  "os": "Linux",
  "os_version": "Ubuntu 22.04.3 LTS",
  "cpu": "Intel Core i7-12700K",
  "cpu_cores": 12,
  "ram_total": "32.0 GB",
  "ram_available": "18.4 GB",
  "disk_total": "512.11 GB",
  "disk_free": "234.7 GB",
  "message": "System information retrieved successfully."
}
```

One command. One schema. Zero ambiguity. Same on Windows, Linux, and macOS.

---

## Install

```bash
pip install qzx
```

Requires Python 3.6+. No mandatory dependencies — `psutil` and `smartmontools` are optional for extended monitoring.

---

## Core Philosophy

| Unix tradition | QZX for agents |
|---|---|
| Silence means success | Explicit `success: true/false` always |
| Parse text output | Consume structured JSON |
| Learn per-OS syntax | One syntax everywhere |
| Chain verification commands | Get full context in one call |

QZX does not replace the shell. It adds a reliable, AI-friendly layer on top of it — one that treats the agent as a first-class consumer of output, not an afterthought.

---

## Every Command Returns Two Outputs

QZX never forces you to choose between human-readable and machine-readable output.

**stdout** — readable, descriptive, good for logs and terminals.
**JSON** — structured, consistent schema, good for agents and scripts.

Both. Always. No flags needed.

---

## Command Reference

### System Analysis

```bash
qzx SystemInfo              # OS, CPU, RAM, disk — all at once
qzx GetRAMInfo              # Detailed memory breakdown
qzx GetCPULoad              # Per-core usage
qzx GetDiskInfo             # All mounted volumes
qzx GetSmartValues "/dev/sda"  # Disk health and temperature
```

### File System Operations

```bash
qzx CreateDirectory "path/to/folder"
qzx CopyFile "source.txt" "destination.txt"
qzx MoveFile "old/path" "new/path"
qzx DeleteFile "target.txt"
qzx ChangePermissions "script.sh" "755"
qzx TouchFile "file.txt"
qzx ListFiles "."
```

### Search & Analysis

```bash
qzx FindText "ERROR" "logs/app.log"
qzx FindFiles "src" "*.py" -r
qzx FindLargeFiles "dist" "*.map" "1MB" -r
qzx CountLinesInFile "main.py"
```

### Process Management

```bash
qzx ListProcesses "python"
qzx KillProcess "12345"
```

### Development Tools

```bash
qzx RunScript "build.py" "--env=prod"
qzx GetCurrentDate
qzx GetCurrentTime
qzx qzxVersion
```

42 verified commands. All tested. All returning structured JSON.

---

## Real Agent Workflows

### Autonomous DevOps Pipeline

```bash
qzx SystemInfo > "build_environment.json"
qzx CreateDirectory "Deployment/$(qzx GetCurrentDate)"
qzx RunScript "build.py" "--env=prod" "--optimize"
qzx FindLargeFiles "dist" "*.map" "1MB" -r > "large_files.log"
```

The agent knows at every step whether the operation succeeded — without a single verification roundtrip.

### System Health Check

```bash
qzx GetSmartValues "/dev/sda" > "disk_health.json"
qzx GetCPULoad | jq '.cores[] | select(.usage > 80)'
qzx FindText "OOM|SEGV|FATAL" "/var/log/syslog" -r
```

### Cross-Platform Project Setup

```bash
qzx CreateDirectory "src/components" "src/utils" "src/styles" "tests"
qzx TouchFile "src/.gitkeep" ".github/workflows/.gitkeep"
qzx RunScript "setup_env.py" "--with-dependencies"
```

Identical commands. Any OS. Agent doesn't need to know which one.

---

## Extending QZX

Adding a command takes minutes:

```python
from qzx.core.command_base import CommandBase

class MyCommand(CommandBase):
    name = "myCommand"
    description = "What it does"
    category = "development"

    def execute(self, param1, param2):
        return {
            "success": True,
            "result": f"{param1}, {param2}",
            "message": "Operation completed successfully."
        }
```

Drop it in `src/qzx/commands/` under the right category. The loader discovers it automatically.

---

## Status

**v0.02 — Alpha**

Alpha means the API may still evolve. It does not mean untested — all 42 commands have unit tests passing in green across platforms. Use in production at your own judgment; the foundations are solid.

---

## Contributing

```bash
git clone https://github.com/alesanGreat/QZX-Quick-Zap-Exchange.git
cd QZX-Quick-Zap-Exchange
pip install -e .
```

Fork → branch → PR. Tests required for new commands.

---

## License

MIT — use it, build on it, integrate it.

---

*QZX — because an agent that can't trust its own tool output isn't autonomous. It's just expensive.*