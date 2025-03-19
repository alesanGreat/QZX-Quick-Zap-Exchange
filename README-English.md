# QZX: Quick Zap Exchange

## Universal Command Interface for AI Agents

QZX (pronounced "Qui-Zi-Ex") is a universal command interface that allows AI agents to execute system operations across any operating system without worrying about platform-specific syntax variations.

### Pronunciation Guide by Language:

- **English**: "Kwee-Zee-Ex"
- **Spanish**: "Kui-Si-Ex" (or "Kui-Zi-Ex" in Spain)
- **Italian**: "Kui-Tsi-Ex"
- **Portuguese**: "Kui-Zi-Ex"
- **Mandarin Chinese**: "Kuí-Zī-Èkè-sī" (库伊-兹-埃克斯)
- **Cantonese Chinese**: "Kwai-Ji-Ek-si"
- **German**: "Kwi-Tsi-Ex"
- **French**: "Kwi-Zi-Ex"

*Note: The pronunciation maintains the connection to the original letters Q, Z, and X while being adaptable across multiple languages.*

![QZX Logo](https://via.placeholder.com/150x150.png?text=QZX)

**Current Version: 0.01**

## What is QZX?

QZX stands for **Quick Zap Exchange** - an instant transfer of commands between different computing environments.

Just as a lightning bolt (zap!) instantly bridges the gap between sky and ground, QZX bridges the gap between different operating systems, creating a unified command experience.

## Why QZX?

AI agents face a significant challenge when working across multiple operating systems:
- Windows uses `mkdir` in CMD but `New-Item` in PowerShell
- Unix/Linux/macOS use different flags and syntax for similar operations
- Each system has unique file paths, permissions, and execution environments

QZX eliminates this complexity by providing a consistent command prefix that works identically across all systems.

## How It Works

Every QZX command follows the same pattern:

```
qzx CommandName [parameters]
```

The middleware automatically translates this universal syntax into the appropriate native command for whatever system it's running on.

## Example Commands

```bash
# Create a directory
qzx CreateDirectory "ProjectFolder"

# Create multiple directories at once
qzx CreateDirectory "src/components" "src/utils" "src/styles"

# Count lines in a file
qzx CountLinesInFile "script.py"

# Search for text
qzx FindText "search term" "target_file.txt"

# List all files in directory
qzx ListFiles "/path/to/directory"

# Get system information
qzx SystemInfo

# Run a script with parameters
qzx RunScript "myscript.py" "param1" "param2"

# Get QZX version information
qzx qzxVersion
```

For a complete list of all available commands and detailed documentation, please see [Documentation-Commands.md](Documentation-Commands.md).

## Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| CreateDirectory | Creates one or more directories | `qzx CreateDirectory "folder1" "folder2"` |
| CountLinesInFile | Counts lines in a file | `qzx CountLinesInFile "document.txt"` |
| FindText | Searches for text in a file | `qzx FindText "function" "main.py"` |
| ListFiles | Lists all files in a directory | `qzx ListFiles "."` |
| SystemInfo | Displays system information | `qzx SystemInfo` |
| RunScript | Executes a script with parameters | `qzx RunScript "automate.py" "arg1" "arg2"` |
| qzxVersion | Displays QZX version | `qzx qzxVersion` |

## Benefits for AI Agents

- **Reduced Complexity**: AI only needs to learn one command set
- **Error Prevention**: Eliminates OS-specific syntax errors
- **Universal Compatibility**: Write once, run anywhere
- **Simplified Reasoning**: AI can focus on the task rather than implementation details
- **Faster Development**: Reduces the need for platform-specific code branches

## Real-world Use Cases

### Automated Data Processing
```bash
qzx CreateDirectory "DataProcessing/$(date +%Y-%m-%d)"
qzx RunScript "process_data.py" "input.csv" "DataProcessing/$(date +%Y-%m-%d)/output.json"
```

### Development Environment Setup
```bash
# Create multiple project directories in a single command
qzx CreateDirectory "MyProject/src" "MyProject/docs" "MyProject/tests" "MyProject/config"
qzx RunScript "setup_env.py" "MyProject" "--with-dependencies"
```

### Web Development Project Setup
```bash
# Set up a typical React/Next.js project structure
qzx CreateDirectory "src/components" "src/pages" "src/hooks" "src/styles" "src/utils" "public/images"
qzx RunScript "init_project.py" "--framework=nextjs" "--typescript"
```

### System Maintenance
```bash
qzx SystemInfo > "system_report.txt"
qzx FindText "ERROR" "application.log" > "error_report.txt"
qzx RunScript "cleanup.py" "--older-than=30days"
```

## Installation

1. Ensure you have Python 3.6 or higher installed
2. Clone this repository or download the files:
   ```bash
   git clone https://github.com/yourusername/qzx.git
   cd qzx
   ```
3. Make the scripts executable (Linux/Mac):
   ```bash
   chmod +x qzx.py qzx.sh
   ```
4. Add QZX to your PATH (optional, but recommended):
   - **Linux/Mac**: Add `export PATH="$PATH:/path/to/qzx"` to your `.bashrc` or `.zshrc`
   - **Windows**: Add the QZX folder to your system PATH variable
5. Install the required dependencies (for full functionality):
   ```bash
   pip install psutil
   ```

## Usage

### On Windows:
```
qzx.bat CreateDirectory "NewFolder"
qzx.bat CreateDirectory "src\components\SearchBox" "src\components\ThemeToggle" "src\components\PatientTable"
```

### On Linux/Mac:
```
./qzx.sh CreateDirectory "NewFolder"
./qzx.sh CreateDirectory "src/components/SearchBox" "src/components/ThemeToggle" "src/components/PatientTable"
```

### Direct Python Execution:
```
python qzx.py CreateDirectory "NewFolder"
python qzx.py CreateDirectory "src/components/SearchBox" "src/components/ThemeToggle" "src/components/PatientTable"
```

## Extending QZX

QZX is designed to be easily extendable. To add a new command:

1. Open `qzx.py`
2. Add your new command method to the `QZX` class:
   ```python
   def my_new_command(self, param1, param2):
       """Description of what your command does"""
       # Your implementation here
       return f"Result: {param1}, {param2}"
   ```
3. Register your command in the `__init__` method:
   ```python
   self.commands["myNewCommand"] = self.my_new_command
   ```
4. Add documentation for your command in [Documentation-Commands.md](Documentation-Commands.md)

## Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

Please make sure to update tests as appropriate and follow the existing code style.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all the AI assistants who struggle with cross-platform command execution
- Inspired by the need for seamless cross-platform operations in AI workflows

---

*QZX - Bridging the gap between human instructions and machine execution.*
