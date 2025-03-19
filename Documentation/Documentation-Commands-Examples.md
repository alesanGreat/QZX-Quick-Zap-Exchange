# QZX Command Documentation

This documentation details all the commands available in the QZX (Quick Zap Exchange) tool.

## Command Index

1. [CreateDirectory](#createdirectory) - Create directories
2. [CountLinesInFile](#countlinesinfile) - Count lines in files, supporting wildcards and recursive searching
3. [FindText](#findtext) - Search text in files, supporting wildcards and recursive searching
4. [ListFiles](#listfiles) - List files in a directory
5. [SystemInfo](#systeminfo) - Get system information
6. [RunScript](#runscript) - Execute scripts with parameters
7. [qzxVersion](#qzxversion) - Show QZX version
8. [GetRAMInfo](#getraminfo) - Get RAM memory information
9. [GetDiskInfo](#getdiskinfo) - Get disk space information
10. [GetCurrentDate](#getcurrentdate) - Get current date in YYYY-MM-DD format
11. [GetCurrentTime](#getcurrenttime) - Get current time in HH-MM-SS-milliseconds format
12. [GetCPULoad](#getcpuload) - Get current CPU load information
13. [GetSmartValues](#getsmartvalues) - Get S.M.A.R.T. health data from disks
14. [GetDiskName](#getdiskname) - Get disk names and model information
15. [GetCurrentUser](#getcurrentuser) - Get current logged in user information
16. [IsAdmin](#isadmin) - Check if current user has administrative privileges
17. [ReadFile](#readfile) - Display file contents (like 'cat')
18. [CopyFile](#copyfile) - Copy files and directories (like 'cp')
19. [MoveFile](#movefile) - Move or rename files and directories (like 'mv')
20. [DeleteFile](#deletefile) - Delete files and directories (like 'rm')
21. [TouchFile](#touchfile) - Create empty files or update timestamps (like 'touch')
22. [ChangePermissions](#changepermissions) - Change file permissions (like 'chmod')
23. [FindFiles](#findfiles) - Find files by pattern (like 'find')
24. [ListProcesses](#listprocesses) - List running processes (like 'ps')
25. [KillProcess](#killprocess) - Terminate processes (like 'kill')
26. [DownloadFile](#downloadfile) - Download files from the internet (like 'wget/curl')
27. [FindLargeFiles](#findlargefiles) - Search for files with specific extensions that exceed a given size

---

## CreateDirectory

**Description:** Creates one or more directories at the specified paths.

**Syntax:**
```
qzx CreateDirectory "path/to/directory1" "path/to/directory2" ...
```

**Parameters:**
- One or more directory paths (as space-separated strings)

**Examples:**
```bash
# Create a single directory
qzx CreateDirectory "MyProject"

# Create multiple directories
qzx CreateDirectory "src/components" "src/utils" "src/styles"

# Create nested structure
qzx CreateDirectory "project/src/components/Button"
```

**Output:**
```
Created 3 of 3 directories
✓ Directory created: src/components
✓ Directory created: src/utils
✓ Directory created: src/styles
```

---

## CountLinesInFile

**Description:** Counts the number of lines in files, supporting wildcards and recursive searching.

**Syntax:**
```
qzx CountLinesInFile "file_path" [recursive] [ignore_empty]
```

**Parameters:**
- **file_path**: Path to the file(s) to count lines in. Supports wildcards like "*.py"
- **recursive** (optional): Specify recursion level:
  - No recursion by default (only files in the current directory)
  - `-r` or `--recursive`: Count lines in all matching files in the directory tree
  - `-rN` or `--recursiveN`: Count lines in files up to N levels deep (e.g., `-r2`)
- **ignore_empty** (optional): Set to 'true' to ignore empty lines (default: false)

**Examples:**
```bash
# Count lines in a single file
qzx CountLinesInFile "script.py"

# Count lines in a specific component
qzx CountLinesInFile "src/components/Button.jsx"

# Count lines in all Python files recursively
qzx CountLinesInFile "*.py" -r

# Count non-empty lines in all JavaScript files up to 2 levels deep
qzx CountLinesInFile "src/*.js" -r2 true
```

**Output:**
```
File script.py has 120 lines
```

---

## FindText

**Description:** Searches for a term in files and displays the lines containing the term. Supports wildcards and recursive searching.

**Syntax:**
```
qzx FindText "pattern" "target" [recursive] [regex] [case_sensitive] [file_pattern] [other_options]
```

**Parameters:**
- **pattern**: Text pattern to search for (supports regular expressions if regex=true)
- **target**: File or directory to search in (can be multiple space-separated paths)
- **recursive** (optional): Specify recursion level:
  - No recursion by default (only search in the specified file/directory)
  - `-r` or `--recursive`: Search recursively with unlimited depth
  - `-rN` or `--recursiveN`: Search up to N levels deep (e.g., `-r2`)
- **regex** (optional): Whether to use regular expressions (true/false)
- **case_sensitive** (optional): Whether the search is case-sensitive (true/false, default: true)
- **file_pattern** (optional): Only search in files matching this pattern (e.g., "*.js")

**Examples:**
```bash
# Search in a single file
qzx FindText "function" "main.js"

# Search in log files
qzx FindText "ERROR" "logs/application.log"

# Search for 'TODO' in all Python files recursively
qzx FindText "TODO" "src" -r false true "*.py"

# Search for function definitions in JS files up to 2 levels deep using regex
qzx FindText "function\\s+\\w+" "src" -r2 true true "*.js"
```

---

## ListFiles

**Description:** Lists all files and directories in a specified path, with support for pattern matching and recursive searching.

**Syntax:**
```
qzx ListFiles [directory_path] [pattern] [recursive]
```

**Parameters:**
- **directory_path** (Optional): Path to the directory. If not specified, the current directory is used.
- **pattern** (Optional): File pattern to filter by (e.g., "*.txt", "doc*.pdf"). Default is "*" (all files).
- **recursive** (Optional): Specify recursion level:
  - No recursion by default (only lists files in the specified directory)
  - `-r` or `--recursive`: List files in the directory and all subdirectories recursively
  - `-rN` or `--recursiveN`: List files in the directory up to N levels deep (e.g., `-r2`)

**Examples:**
```bash
# List all files in current directory
qzx ListFiles

# List all files in a specific directory
qzx ListFiles "src/components"

# List only Python files in current directory
qzx ListFiles . "*.py"

# List all JavaScript files recursively
qzx ListFiles "src" "*.js" -r

# List all images up to 2 levels deep in the images directory
qzx ListFiles "images" "*.{jpg,png,gif}" -r2
```

**Output:**
```
Contents of C:\Projects\MyApp\src\components:
[File] Button.jsx (2340 bytes)
[File] Navbar.jsx (5670 bytes)
[Directory] Forms (-)
[Directory] Layout (-)
```

---

## SystemInfo

**Description:** Displays detailed information about the operating system.

**Syntax:**
```
qzx SystemInfo
```

**Parameters:**
- None

**Examples:**
```bash
qzx SystemInfo
```

**Output:**
```
System Information:
OS: Windows
OS Version: 10.0.19044
Machine: AMD64
Processor: Intel64 Family 6 Model 142 Stepping 12, GenuineIntel
Python Version: 3.10.2
User: JohnDoe
Home Directory: C:\Users\JohnDoe
```

---

## RunScript

**Description:** Executes a script with optional parameters.

**Syntax:**
```
qzx RunScript "path/to/script" ["param1" "param2" ...]
```

**Parameters:**
- Path to the script
- (Optional) Parameters to pass to the script

**Examples:**
```bash
qzx RunScript "build.py"
qzx RunScript "process_data.py" "input.csv" "output.json"
qzx RunScript "deploy.sh" "--environment=prod" "--verbose"
```

**Output:**
```
Script execution complete:
Processing data...
Converting CSV to JSON...
Processed 2500 records.
Output saved to output.json
```

---

## qzxVersion

**Description:** Shows the current version of QZX.

**Syntax:**
```
qzx qzxVersion
```

**Parameters:**
- None

**Examples:**
```bash
qzx qzxVersion
```

**Output:**
```
QZX Version 0.01
```

---

## GetRAMInfo

**Description:** Displays detailed information about the system's RAM memory.

**Syntax:**
```
qzx GetRAMInfo
```

**Parameters:**
- None

**Requirements:**
- Requires the `psutil` module installed (`pip install psutil`)

**Examples:**
```bash
qzx GetRAMInfo
```

**Output:**
```
RAM Information:
Total: 16.00 GB
Available: 8.42 GB
Used: 7.58 GB (47.4%)
Free: 2.32 GB
```

---

## GetDiskInfo

**Description:** Displays information about the available disk space.

**Syntax:**
```
qzx GetDiskInfo ["path/to/directory"]
```

**Parameters:**
- (Optional) Path to the directory or drive. If not specified, all mounted drives are shown.

**Requirements:**
- For complete information, requires the `psutil` module installed (`pip install psutil`)

**Examples:**
```bash
# Get information for all drives
qzx GetDiskInfo

# Get information for a specific drive
qzx GetDiskInfo "C:\"

# Get information for a specific directory
qzx GetDiskInfo "D:\Projects"
```

**Output:**
```
Disk Space Information:

Disk: C:
Mountpoint: C:\
File System: NTFS
Total: 256.00 GB
Used: 128.45 GB (50.2%)
Free: 127.55 GB

Disk: D:
Mountpoint: D:\
File System: NTFS
Total: 1.00 TB
Used: 357.45 GB (34.9%)
Free: 666.55 GB
```

---

## GetCurrentDate

**Description:** Returns the current date in YYYY-MM-DD format.

**Syntax:**
```
qzx GetCurrentDate
```

**Parameters:**
- None

**Examples:**
```bash
qzx GetCurrentDate
```

**Output:**
```
2023-12-15
```

**Usage in scripts:**
```bash
# Create a log file with today's date
qzx CreateDirectory "logs"
TODAY=$(qzx GetCurrentDate)
qzx RunScript "generate_report.py" > "logs/report_${TODAY}.log"
```

---

## GetCurrentTime

**Description:** Returns the current time in HH-MM-SS-milliseconds format.

**Syntax:**
```
qzx GetCurrentTime
```

**Parameters:**
- None

**Examples:**
```bash
qzx GetCurrentTime
```

**Output:**
```
14-32-07-345
```

**Usage in scripts:**
```bash
# Create a timestamped backup
TODAY=$(qzx GetCurrentDate)
CURRENT_TIME=$(qzx GetCurrentTime)
qzx RunScript "backup.py" "data/" "backups/backup_${TODAY}_${CURRENT_TIME}.zip"
```

---

## GetCPULoad

**Description:** Returns detailed information about the current CPU usage, including per-core load and frequency information.

**Syntax:**
```
qzx GetCPULoad
```

**Parameters:**
- None

**Requirements:**
- Requires the `psutil` module installed (`pip install psutil`)

**Examples:**
```bash
qzx GetCPULoad
```

**Output:**
```
CPU Load Information:
Overall CPU Usage: 23.5%

Per-Core Usage:
Core 1: 15.2%
Core 2: 30.8%
Core 3: 18.5%
Core 4: 29.4%

Current Frequency: 3200.00 MHz
Minimum Frequency: 800.00 MHz
Maximum Frequency: 3800.00 MHz
```

**Usage in scripts:**
```bash
# Monitor CPU load and log if it's too high
CPU_LOAD=$(qzx GetCPULoad)
echo "$(qzx GetCurrentDate) $(qzx GetCurrentTime) - ${CPU_LOAD}" >> cpu_monitoring.log

# Or check if load is over a threshold
LOAD_LINE=$(qzx GetCPULoad | grep "Overall CPU Usage")
LOAD_VALUE=$(echo $LOAD_LINE | cut -d":" -f2 | cut -d"%" -f1 | tr -d " ")
if (( $(echo "$LOAD_VALUE > 80" | bc -l) )); then
    echo "High CPU Alert: $LOAD_VALUE%" >> alerts.log
fi
```

---

## GetSmartValues

**Description:** Retrieves S.M.A.R.T. (Self-Monitoring, Analysis, and Reporting Technology) health data from disk drives.

**Syntax:**
```
qzx GetSmartValues ["disk_path"]
```

**Parameters:**
- (Optional) Path to the specific disk device to check. If not specified, all detected disks will be checked.

**Requirements:**
- Requires `smartmontools` (smartctl) to be installed on the system
- On Windows: Install with `choco install smartmontools` or download from the official website
- On Linux: Install with `apt install smartmontools` or equivalent
- On macOS: Install with `brew install smartmontools`

**Examples:**
```bash
# Check all disks
qzx GetSmartValues

# Check a specific disk on Windows
qzx GetSmartValues "\\.\PhysicalDrive0"

# Check a specific disk on Linux
qzx GetSmartValues "/dev/sda"

# Check a specific disk on macOS
qzx GetSmartValues "/dev/disk0"
```

**Output:**
```
S.M.A.R.T. Disk Health Information:

--- Disk: /dev/sda ---
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)
Copyright (C) 2002-20, Bruce Allen, Christian Franke, www.smartmontools.org

Model Family:     Samsung SSD 850 PRO
Device Model:     Samsung SSD 850 PRO 512GB
Serial Number:    S2BANX0J500047Z
Firmware Version: EXM02B6Q
User Capacity:    512,110,190,592 bytes [512 GB]
Sector Size:      512 bytes logical/physical
Rotation Rate:    Solid State Device
SMART support is: Available - device has SMART capability.
SMART overall-health self-assessment test result: PASSED

SMART Attributes Data Structure:
Attribute    Current  Worst   Threshold  Value  Flags
  5 Reallocated_Sector_Ct   100   100   010      0  Pre-fail
  9 Power_On_Hours          099   099   000      5  Old_age
 12 Power_Cycle_Count       099   099   000     20  Old_age
177 Wear_Leveling_Count     099   099   000      1  Pre-fail
179 Used_Rsvd_Blk_Cnt_Tot   100   100   010      0  Pre-fail
181 Program_Fail_Cnt_Total  100   100   010      0  Old_age
182 Erase_Fail_Count_Total  100   100   010      0  Old_age
183 Runtime_Bad_Block       100   100   010      0  Pre-fail
187 Uncorrectable_Error_Cnt 100   100   000      0  Old_age
190 Airflow_Temperature_Cel 069   060   000     31  Old_age
195 ECC_Error_Rate          200   200   000      0  Old_age
241 Total_LBAs_Written      099   099   000     12  Old_age
```

**Usage in scripts:**
```bash
# Run a daily SMART check and log results
TODAY=$(qzx GetCurrentDate)
qzx GetSmartValues > "logs/smart_check_${TODAY}.log"

# Check for any failed SMART tests
SMART_OUTPUT=$(qzx GetSmartValues)
if echo "$SMART_OUTPUT" | grep -q "FAILED"; then
    echo "ALERT: SMART test failed on $(qzx GetCurrentDate)" | mail -s "Disk Failure Warning" admin@example.com
fi
```

---

## GetDiskName

**Description:** Retrieves disk name, model, and detailed information about disk drives attached to the system.

**Syntax:**
```
qzx GetDiskName ["disk_path"]
```

**Parameters:**
- (Optional) Path to the specific disk to get information about. If not specified, information for all disks will be shown.

**Requirements:**
- Full functionality requires the `psutil` module (`pip install psutil`)
- Uses OS-specific commands in the background (`wmic` on Windows, `lsblk` on Linux, `diskutil` on macOS)

**Examples:**
```bash
# List all disks
qzx GetDiskName

# Get information for a specific disk on Windows
qzx GetDiskName "C:"
qzx GetDiskName "\\.\PhysicalDrive0"

# Get information for a specific disk on Linux
qzx GetDiskName "/dev/sda"

# Get information for a specific disk on macOS
qzx GetDiskName "/dev/disk0"
```

**Output:**
```
Disk Name Information:
Logical Drives:
DeviceID  VolumeName    FileSystem  Size         FreeSpace
C:        Windows       NTFS        512105426944 128105426944
D:        Data          NTFS        1024209715200 512105426944
E:        Backup        NTFS        2048419430400 1536314572800

Physical Disks:
DeviceID              Model                   Size          MediaType   InterfaceType
\\.\PHYSICALDRIVE0    Samsung SSD 970 EVO     512110190592  Fixed       SCSI
\\.\PHYSICALDRIVE1    WDC WD10EZEX-08WN4A0    1000202273280 Fixed       SCSI
\\.\PHYSICALDRIVE2    Seagate Backup Plus     2000398934016 Fixed       USB
```

**Usage in scripts:**
```bash
# List all disk models for inventory
qzx GetDiskName > system_inventory.txt

# Check if a specific disk model exists
DISK_INFO=$(qzx GetDiskName)
if echo "$DISK_INFO" | grep -q "Samsung SSD"; then
    echo "Samsung SSD found in the system"
fi
```

---

## GetCurrentUser

**Description:** Returns information about the currently logged in user.

**Syntax:**
```
qzx GetCurrentUser
```

**Parameters:**
- None

**Examples:**
```bash
qzx GetCurrentUser
```

**Output:**
```
Current User Information:
Username: johndoe
Home Directory: C:\Users\johndoe
User ID: johndoe
Running Processes: 32

User Environment Variables:
USERNAME: johndoe
USERPROFILE: C:\Users\johndoe
HOME: C:\Users\johndoe

Shell: C:\Windows\system32\cmd.exe
```

**Usage in scripts:**
```bash
# Log the current user for auditing
echo "$(qzx GetCurrentDate) $(qzx GetCurrentTime) - User: $(qzx GetCurrentUser | grep Username | cut -d':' -f2 | tr -d ' ')" >> user_audit.log

# Create user-specific backup folder
USER=$(qzx GetCurrentUser | grep Username | cut -d':' -f2 | tr -d ' ')
qzx CreateDirectory "backups/${USER}"
```

---

## IsAdmin

**Description:** Checks if the current user has administrative privileges. The check is OS-specific and provides detailed information about the user's permission level.

**Syntax:**
```
qzx IsAdmin
```

**Parameters:**
- None

**Examples:**
```bash
qzx IsAdmin
```

**Output on Windows (non-admin):**
```
Administrative Privileges Check:
Is Administrator: No
User is a member of administrators group but not running with elevated privileges
Tip: Try running as administrator to gain full privileges
```

**Output on Windows (admin):**
```
Administrative Privileges Check:
Is Administrator: Yes
User has full administrative rights
```

**Output on Linux:**
```
Administrative Privileges Check:
Is Root: No
Has Passwordless Sudo: Yes
Member of admin groups: sudo, wheel
```

**Usage in scripts:**
```bash
# Check for admin rights before executing privileged operations
ADMIN_CHECK=$(qzx IsAdmin)
if echo "$ADMIN_CHECK" | grep -q "Is Administrator: Yes" || echo "$ADMIN_CHECK" | grep -q "Is Root: Yes"; then
    echo "Running with administrative privileges. Proceeding with system changes..."
    qzx RunScript "system_backup.py" --full
else
    echo "Error: This script requires administrative privileges."
    echo "Please run as administrator/root and try again."
    exit 1
fi
```

**Security considerations:**
- This command is useful for checking permissions before attempting operations that require elevated privileges
- Can help prevent permission-related errors in scripts
- Should be used before running maintenance tasks, system updates, or any operation that modifies system files
- On Windows, shows if a user has potential admin rights (member of administrators group) but is not running with elevation
- On Linux/macOS, differentiates between actual root access and sudo capabilities

---

## ReadFile

**Description:** Displays the content of a file, similar to the 'cat' command in Unix.

**Syntax:**
```
qzx ReadFile "file_path" [max_lines]
```

**Parameters:**
- **file_path**: Path to the file to read
- **max_lines** (optional): Maximum number of lines to read

**Examples:**
```bash
# Display entire file
qzx ReadFile "logs/app.log"

# Display only the first 20 lines
qzx ReadFile "config.json" 20
```

**Output:**
```
Content of logs/app.log:
----------------------------------------
2023-12-15 09:32:45 INFO Application started
2023-12-15 09:33:12 DEBUG Loading user preferences
2023-12-15 09:33:15 INFO User authentication successful
2023-12-15 09:34:01 ERROR Failed to connect to database
...
```

**Usage in scripts:**
```bash
# Check if a configuration file contains specific settings
CONFIG=$(qzx ReadFile "config.json")
if echo "$CONFIG" | grep -q "debug_mode: true"; then
    echo "Warning: Debug mode is enabled in production!"
fi
```

---

## CopyFile

**Description:** Copies files or directories, similar to the 'cp' command in Unix.

**Syntax:**
```
qzx CopyFile "source" "destination" [force]
```

**Parameters:**
- **source**: Source file or directory to copy
- **destination**: Destination path
- **force** (optional): Set to 'True' to overwrite existing files (default: False)

**Examples:**
```bash
# Copy a single file
qzx CopyFile "document.txt" "backup/document.txt"

# Copy a file and overwrite if exists
qzx CopyFile "settings.json" "backup/settings.json" True

# Copy a directory recursively
qzx CopyFile "project_src" "project_backup"
```

**Output:**
```
File 'document.txt' copied to 'backup/document.txt'
```

**Usage in scripts:**
```bash
# Create a timestamped backup of a configuration file
TODAY=$(qzx GetCurrentDate)
qzx CopyFile "config.ini" "backups/config_${TODAY}.ini"
```

---

## MoveFile

**Description:** Moves or renames files and directories, similar to the 'mv' command in Unix.

**Syntax:**
```
qzx MoveFile "source" "destination" [force]
```

**Parameters:**
- **source**: Source file or directory to move
- **destination**: Destination path
- **force** (optional): Set to 'True' to overwrite existing files (default: False)

**Examples:**
```bash
# Move a file
qzx MoveFile "report.docx" "archive/report.docx"

# Rename a file
qzx MoveFile "temp.txt" "final.txt"

# Move a directory
qzx MoveFile "old_project" "completed_projects/project_alpha"
```

**Output:**
```
'report.docx' moved to 'archive/report.docx'
```

**Usage in scripts:**
```bash
# Archive log files older than a certain date
qzx FindFiles "logs" "*.log" | while read log_file; do
    qzx MoveFile "$log_file" "archive/logs/"
done
```

---

## DeleteFile

**Description:** Deletes files or directories, similar to the 'rm' command in Unix.

**Syntax:**
```
qzx DeleteFile "path" [recursive]
```

**Parameters:**
- **path**: Path to the file or directory to delete
- **recursive** (optional): Specify recursion level: 
  - No recursion by default (only deletes empty directories)
  - `-r` or `--recursive`: Delete directory and all its contents recursively
  - `-rN` or `--recursiveN`: Delete directory and contents up to N levels deep (e.g., `-r2`)

**Examples:**
```bash
# Delete a single file
qzx DeleteFile "temp.txt"

# Delete an empty directory
qzx DeleteFile "empty_folder"

# Delete a directory and all its contents
qzx DeleteFile "temp_folder" -r

# Delete a directory with contents up to 2 levels deep
qzx DeleteFile "project_folder" -r2
```

**Output:**
```
File 'temp.txt' deleted
```

**Warning:**
This command permanently deletes files and directories. Use with caution, especially with the recursive option.

**Usage in scripts:**
```bash
# Clean up temporary files
qzx FindFiles "." "*.tmp" | while read tmp_file; do
    qzx DeleteFile "$tmp_file"
done
```

---

## TouchFile

**Description:** Creates empty files or updates timestamps of existing files, similar to the 'touch' command in Unix.

**Syntax:**
```
qzx TouchFile "file_path" [create_parents]
```

**Parameters:**
- **file_path**: Path to the file to touch
- **create_parents** (optional): Set to 'True' to create parent directories if they don't exist (default: False)

**Examples:**
```bash
# Create an empty file
qzx TouchFile "newfile.txt"

# Update timestamp of existing file
qzx TouchFile "config.ini"

# Create file with full directory path (if it doesn't exist)
qzx TouchFile "logs/2023/12/app.log" True
```

**Output:**
```
Created empty file 'newfile.txt'
```

**Usage in scripts:**
```bash
# Create placeholder files for a project structure
for dir in "src" "docs" "tests"; do
    qzx CreateDirectory "$dir"
    qzx TouchFile "$dir/.gitkeep"
done
```

---

## ChangePermissions

**Description:** Changes file or directory permissions, similar to the 'chmod' command in Unix.

**Syntax:**
```
qzx ChangePermissions "path" "mode"
```

**Parameters:**
- **path**: Path to the file or directory
- **mode**: Permission mode in octal format (e.g., '755' or '0o755')

**Examples:**
```bash
# Make a script executable
qzx ChangePermissions "script.sh" "755"

# Set read-only permissions
qzx ChangePermissions "important.conf" "444"

# Set full permissions for owner, read/execute for others
qzx ChangePermissions "run.py" "755"
```

**Output:**
```
Changed permissions of 'script.sh' to 0o755
```

**Note:**
- On Windows, this command has limited functionality compared to Unix systems
- The permission model is different on Windows, so not all Unix permissions have direct equivalents

**Usage in scripts:**
```bash
# Make all shell scripts executable
qzx FindFiles "scripts" "*.sh" | while read script; do
    qzx ChangePermissions "$script" "755"
done
```

---

## FindFiles

**Description:** Finds files and directories matching a pattern, similar to the 'find' command in Unix.

**Syntax:**
```
qzx FindFiles [search_path] [pattern] [recursive] [type_filter] [other_options]
```

**Parameters:**
- **search_path** (optional): Directory to start searching from (default: current directory)
- **pattern** (optional): File name pattern using glob syntax (default: "*")
- **recursive** (optional): Specify recursion level:
  - `-r` or `--recursive`: Search recursively with unlimited depth (default)
  - `-rN` or `--recursiveN`: Search up to N levels deep (e.g., `-r2`)
  - Without this parameter: Only search in the specified directory
- **type_filter** (optional): Type of items to find ('f' for files, 'd' for directories)
- Plus many other advanced filtering options (size, date, content, etc.)

**Examples:**
```bash
# Find all Python files in the current directory and subdirectories
qzx FindFiles "." "*.py" -r

# Find all log files in the logs directory, only 1 level deep
qzx FindFiles "logs" "*.log" -r1

# Find only directories containing 'data' in their name (non-recursive)
qzx FindFiles "projects" "*data*" "" "d"

# Find only files with .jpg extension with unlimited recursion
qzx FindFiles "photos" "*.jpg" -r "f"

# Advanced search with multiple criteria
qzx FindFiles "src" "*.js" -r2 "f" --min-size 1KB --max-size 100KB --newer-than 2023-01-01
```

**Usage in scripts:**
```bash
# Count lines in all Python files
for py_file in $(qzx FindFiles "src" "*.py" -r | grep -v "Found"); do
    LINES=$(qzx CountLinesInFile "$py_file" | grep -o '[0-9]\+ lines' | grep -o '[0-9]\+')
```

---

## ListProcesses

**Description:** Lists running processes, similar to the 'ps' command in Unix.

**Syntax:**
```
qzx ListProcesses [filter_str]
```

**Parameters:**
- **filter_str** (optional): String to filter process names

**Requirements:**
- Requires the `psutil` module installed (`pip install psutil`)

**Examples:**
```bash
# List all running processes
qzx ListProcesses

# List only Python processes
qzx ListProcesses "python"

# List browser processes
qzx ListProcesses "chrome"
```

**Output:**
```
Process List:
PID      CPU%     MEM%     NAME
--------------------------------------------------
1234     2.1      1.5      python.exe
5678     15.3     8.2      chrome.exe
9012     0.5      1.1      notepad.exe

Total processes: 78
```

**Usage in scripts:**
```bash
# Check if a specific application is running
APP_CHECK=$(qzx ListProcesses "myapp")
if echo "$APP_CHECK" | grep -q "myapp"; then
    echo "MyApp is running"
else
    echo "MyApp is not running, starting it now..."
    qzx RunScript "start_myapp.py"
fi
```

---

## KillProcess

**Description:** Terminates a process by its PID, similar to the 'kill' command in Unix.

**Syntax:**
```
qzx KillProcess "pid" [force]
```

**Parameters:**
- **pid**: Process ID to terminate
- **force** (optional): Set to 'True' to force termination (like kill -9) (default: False)

**Requirements:**
- Requires the `psutil` module installed (`pip install psutil`)

**Examples:**
```bash
# Terminate a process gracefully
qzx KillProcess 1234

# Force-kill a process
qzx KillProcess 5678 True
```

**Output:**
```
Process 1234 (notepad.exe) terminated
```

**Usage in scripts:**
```bash
# Kill all Python processes
for pid in $(qzx ListProcesses "python" | grep -o '^\s*[0-9]\+' | tr -d ' '); do
    qzx KillProcess "$pid"
done
```

**Warning:**
Using force=True can cause data loss if the process was in the middle of writing to disk. Use with caution.

---

## DownloadFile

**Description:** Downloads a file from the internet, similar to 'wget' or 'curl' in Unix.

**Syntax:**
```
qzx DownloadFile "url" "destination_path" [show_progress]
```

**Parameters:**
- **url**: URL of the file to download
- **destination_path**: Path where to save the downloaded file
- **show_progress** (optional): Set to 'False' to hide download progress (default: True)

**Examples:**
```bash
# Download a file with progress bar
qzx DownloadFile "https://example.com/file.zip" "downloads/file.zip"

# Download without showing progress
qzx DownloadFile "https://example.com/data.json" "data/config.json" False
```

**Output:**
```
Downloading: 45.2% (2048.0 KB)
Downloaded https://example.com/file.zip to downloads/file.zip (4.5 MB)
```

**Usage in scripts:**
```bash
# Download and extract a package
URL="https://example.com/software.zip"
qzx DownloadFile "$URL" "temp/software.zip"
qzx RunScript "extract.py" "temp/software.zip" "software/"
qzx DeleteFile "temp/software.zip"
```

---

## FindLargeFiles

**Description:** Searches for files with specific extensions that exceed a given size. Supports wildcards and recursive searching.

**Syntax:**
```
qzx FindLargeFiles [directory] [extension] [min_size] [recursive] [sort_by]
```

**Parameters:**
- **directory**: Base directory to start the search from
- **extension**: File extension to filter by (e.g., "*.pas", "*.txt"). Supports wildcards.
- **min_size**: Minimum file size in bytes. Can use formats like "10MB", "1.5GB", "500KB".
- **recursive** (optional): Specify recursion level:
  - No recursion by default (only search in the specified directory)
  - `-r` or `--recursive`: Search recursively with unlimited depth
  - `-rN` or `--recursiveN`: Search up to N levels deep (e.g., `-r2`)
- **sort_by** (optional): Sort results by: "name", "size", or "date" (default: "size")

**Examples:**
```bash
# Find all .log files in current directory larger than 1MB
qzx FindLargeFiles . "*.log" 1000000

# Find all .mp4 files in the src directory and all subdirectories larger than 5MB
qzx FindLargeFiles src "*.mp4" 5000000 -r

# Find all .js files in the project directory up to 2 levels deep larger than 5KB, sorted by name
qzx FindLargeFiles project "*.js" 5000 -r2 name
```

**Output:**
```
Found 3 files matching "*.log" larger than 1MB in current directory:

logs/system.log (3.2 MB) - Modified: 2024-04-15 14:32:45
logs/errors.log (1.5 MB) - Modified: 2024-04-15 10:15:23
logs/access.log (1.1 MB) - Modified: 2024-04-14 22:08:17
```

---

## Usage Tips

### Character Escaping
- In Windows CMD, use double quotes: `qzx FindText "text" "file.txt"`
- In PowerShell, you may need to escape quotes: `qzx FindText \"text\" \"file.txt\"`
- In Bash/Linux, you can use single or double quotes: `qzx FindText 'text' 'file.txt'`

### Paths with Spaces
- Always use quotes for paths containing spaces:
  ```bash
  qzx CreateDirectory "My Project Folder"
  ```

### Output Redirection
- You can redirect output to a file:
  ```bash
  qzx SystemInfo > system_info.txt
  qzx GetDiskInfo > disk_report.txt
  ```

### Installing Dependencies
To use all QZX functionalities, install the dependencies:
```bash
# For basic functionalities
pip install psutil

# For S.M.A.R.T. disk health monitoring
# Windows: choco install smartmontools
# Linux: apt install smartmontools
# macOS: brew install smartmontools
```

### Date and Time Commands
The date and time commands are useful for:
- Creating timestamped logs and backups
- Naming files with date/time information
- Tracking execution times in scripts
- Creating date-based directory structures

### System Monitoring
The system monitoring commands (GetCPULoad, GetRAMInfo, GetDiskInfo) can be used to:
- Create monitoring dashboards
- Set up automated alerts for system issues
- Generate system health reports
- Track performance over time 