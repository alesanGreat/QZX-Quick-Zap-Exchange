"""C# scaffold helpers for test-project generation and finalization."""

from __future__ import annotations

import os


TEST_PROJECT_TEMPLATE = """<Project Sdk="Microsoft.NET.Sdk">

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
"""

TEST_SOURCE_TEMPLATE = """namespace {class_name}.Tests;

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
"""


def create_test_project(project_path, project_name, result, class_name):
    """Create the xUnit project and its sample tests."""
    test_dir = os.path.join(project_path, f"{project_name}.Tests")
    os.makedirs(test_dir)
    result["files_created"].append(test_dir)

    csproj_path = os.path.join(test_dir, f"{project_name}.Tests.csproj")
    with open(csproj_path, "w", encoding="utf-8") as handle:
        handle.write(TEST_PROJECT_TEMPLATE.format(project_name=project_name))
    result["files_created"].append(csproj_path)

    test_path = os.path.join(test_dir, "ProgramTests.cs")
    with open(test_path, "w", encoding="utf-8") as handle:
        handle.write(
            TEST_SOURCE_TEMPLATE.format(
                class_name=class_name,
                project_name=project_name,
            )
        )
    result["files_created"].append(test_path)


def populate_csharp_project(
    command,
    project_name,
    project_type,
    with_tests,
    result,
):
    """Create project files through the command's compatibility hooks."""
    project_path = result["project_path"]
    command._create_solution(project_path, project_name, result)
    command._create_project_file(project_path, project_name, result)
    command._create_source_file(project_path, project_name, result)
    if with_tests:
        command._create_test_project(project_path, project_name, result)
    command._create_readme(project_path, project_name, result)
    command._create_gitignore(project_path, result)

    tests_msg = "with test scaffolding" if with_tests else "without tests"
    message = (
        f"Successfully created C# {project_type} project '{project_name}' at "
        f"{project_path} {tests_msg}. "
        f"Created {len(result['files_created'])} files and directories. "
        f"Use 'cd {project_path} && dotnet build' to build the project."
    )
    if not command._is_dotnet_installed():
        message += " Note: .NET SDK doesn't appear to be installed. "
        message += (
            "Install from https://dotnet.microsoft.com/download to build the project."
        )
    result["message"] = message
    return result
