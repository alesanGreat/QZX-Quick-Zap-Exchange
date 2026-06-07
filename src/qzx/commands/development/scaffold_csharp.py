#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramCsharp Command - Creates a basic scaffolding for a C# program
"""

import os
import subprocess
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase


class MakeScaffProgramCsharpCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a C# program.
    Creates a new C# console project with .NET SDK and xUnit tests.
    """

    name = "scaffoldCsharp"
    aliases = ["csharpScaff", "newCsharp", "createCsharp", "makeScaffProgramCsharp", "scaffoldCs"]
    description = "Creates a basic scaffolding for a C# program"
    category = "development"

    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the C# project to create',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path where to create the project (default: current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'with_tests',
            'description': 'Whether to include test scaffolding (xUnit)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'project_type',
            'description': 'Project type: console (default)',
            'required': False,
            'default': 'console'
        }
    ]

    examples = [
        {
            'command': 'qzx makeScaffProgramCsharp my_project',
            'description': 'Creates a new C# console project named "my_project" in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramCsharp my_project /path/to/dir true',
            'description': 'Creates a new C# project with xUnit tests in the specified directory'
        }
    ]

    def execute(self, project_name, path='.', with_tests='true', project_type='console'):
        """
        Creates a basic scaffolding for a C# program
        """
        try:
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')

            project_type = project_type.lower()
            if project_type not in ('console',):
                return {
                    "success": False,
                    "error": f"Unsupported project type: {project_type}",
                    "message": "Currently only 'console' is supported as project type for C# scaffolding."
                }

            project_name = self._normalize_project_name(project_name)
            if not project_name:
                return {
                    "success": False,
                    "error": "Invalid project name",
                    "message": "Project name cannot be empty and must contain valid characters (letters, numbers, underscores)."
                }

            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}",
                    "message": f"Cannot create project: the specified path '{path}' does not exist."
                }

            project_path = os.path.join(path, project_name)

            if os.path.exists(project_path):
                return {
                    "success": False,
                    "error": f"Project directory already exists: {project_path}",
                    "message": f"Cannot create project: directory '{project_path}' already exists."
                }

            result = {
                "success": True,
                "project_name": project_name,
                "project_path": project_path,
                "with_tests": with_tests,
                "project_type": project_type,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }

            os.makedirs(project_path)
            result["files_created"].append(project_path)

            self._create_solution(project_path, project_name, result)
            self._create_project_file(project_path, project_name, result)
            self._create_source_file(project_path, project_name, result)
            if with_tests:
                self._create_test_project(project_path, project_name, result)
            self._create_readme(project_path, project_name, result)
            self._create_gitignore(project_path, result)

            tests_msg = "with test scaffolding" if with_tests else "without tests"

            message = (
                f"Successfully created C# {project_type} project '{project_name}' at {project_path} "
                f"{tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'cd {project_path} && dotnet build' to build the project."
            )

            if not self._is_dotnet_installed():
                message += " Note: .NET SDK doesn't appear to be installed. "
                message += "Install from https://dotnet.microsoft.com/download to build the project."

            result["message"] = message
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating C# project: {str(e)}",
                "message": f"Failed to create C# project scaffolding: {str(e)}",
                "project_name": project_name
            }

    def _normalize_project_name(self, name):
        normalized = name.replace(' ', '_').replace('-', '_')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'cs_' + normalized
        return normalized

    def _to_class_name(self, project_name):
        """Convert snake_case project name to PascalCase class name."""
        return ''.join(word.capitalize() for word in project_name.split('_'))

    def _create_solution(self, project_path, project_name, result):
        sln_path = os.path.join(project_path, f"{project_name}.sln")
        with open(sln_path, 'w') as f:
            f.write(f'''
Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "{project_name}", "{project_name}.csproj", "{{11111111-1111-1111-1111-111111111111}}"
EndProject
''')
            if result.get("with_tests"):
                f.write(f'Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "{project_name}.Tests", "{project_name}.Tests\\{project_name}.Tests.csproj", "{{22222222-2222-2222-2222-222222222222}}"\nEndProject\n')
            f.write('''Global
	GlobalSection(SolutionConfigurationPlatforms) = preSolution
		Debug|Any CPU = Debug|Any CPU
		Release|Any CPU = Release|Any CPU
	EndGlobalSection
	GlobalSection(ProjectConfigurationPlatforms) = postSolution
		{11111111-1111-1111-1111-111111111111}.Debug|Any CPU.ActiveCfg = Debug|Any CPU
		{11111111-1111-1111-1111-111111111111}.Debug|Any CPU.Build.0 = Debug|Any CPU
		{11111111-1111-1111-1111-111111111111}.Release|Any CPU.ActiveCfg = Release|Any CPU
		{11111111-1111-1111-1111-111111111111}.Release|Any CPU.Build.0 = Release|Any CPU
''')
            if result.get("with_tests"):
                f.write('''		{22222222-2222-2222-2222-222222222222}.Debug|Any CPU.ActiveCfg = Debug|Any CPU
		{22222222-2222-2222-2222-222222222222}.Debug|Any CPU.Build.0 = Debug|Any CPU
		{22222222-2222-2222-2222-222222222222}.Release|Any CPU.ActiveCfg = Release|Any CPU
		{22222222-2222-2222-2222-222222222222}.Release|Any CPU.Build.0 = Release|Any CPU
''')
            f.write('''	EndGlobalSection
EndGlobal
''')
        result["files_created"].append(sln_path)

    def _create_project_file(self, project_path, project_name, result):
        csproj_path = os.path.join(project_path, f"{project_name}.csproj")
        with open(csproj_path, 'w') as f:
            f.write('''<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>

</Project>
''')
        result["files_created"].append(csproj_path)

    def _create_source_file(self, project_path, project_name, result):
        src_path = os.path.join(project_path, 'Program.cs')
        class_name = self._to_class_name(project_name)
        with open(src_path, 'w') as f:
            f.write(f'''namespace {class_name};

public class Program
{{
    public static string Hello() => "Hello, world from {project_name}!";

    public static void Main(string[] args)
    {{
        Console.WriteLine(Hello());
    }}
}}
''')
        result["files_created"].append(src_path)

    def _create_test_project(self, project_path, project_name, result):
        test_dir = os.path.join(project_path, f"{project_name}.Tests")
        os.makedirs(test_dir)
        result["files_created"].append(test_dir)

        csproj_path = os.path.join(test_dir, f"{project_name}.Tests.csproj")
        with open(csproj_path, 'w') as f:
            f.write(f'''<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="xunit" Version="2.6.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.4">
      <IncludeAssets>runtime; build; native; contentfiles; analyzers; buildtransitive</IncludeAssets>
      <PrivateAssets>all</PrivateAssets>
    </PackageReference>
    <PackageReference Include="coverlet.collector" Version="6.0.0">
      <IncludeAssets>runtime; build; native; contentfiles; analyzers; buildtransitive</IncludeAssets>
      <PrivateAssets>all</PrivateAssets>
    </PackageReference>
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\\{project_name}.csproj" />
  </ItemGroup>

</Project>
''')
        result["files_created"].append(csproj_path)

        test_path = os.path.join(test_dir, 'ProgramTests.cs')
        class_name = self._to_class_name(project_name)
        with open(test_path, 'w') as f:
            f.write(f'''namespace {class_name}.Tests;

using Xunit;

public class ProgramTests
{{
    [Fact]
    public void Hello_ReturnsExpectedMessage()
    {{
        Assert.Equal("Hello, world from {project_name}!", Program.Hello());
    }}

    [Fact]
    public void Hello_ContainsHello()
    {{
        Assert.Contains("Hello", Program.Hello());
    }}
}}
''')
        result["files_created"].append(test_path)

    def _create_readme(self, project_path, project_name, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A C# project created with QZX scaffolding tool.

## Build

```bash
dotnet build
```

## Run

```bash
dotnet run --project {project_name}.csproj
```

## Test

```bash
dotnet test
```
''')
        result["files_created"].append(readme_path)

    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# .NET build outputs
bin/
obj/

# Visual Studio / VS Code
.vs/
.vscode/
*.user
*.suo

# NuGet
*.nupkg
packages/

# OS specific files
.DS_Store
Thumbs.db
''')
        result["files_created"].append(gitignore_path)

    def _is_dotnet_installed(self):
        try:
            subprocess.run(
                ["dotnet", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
