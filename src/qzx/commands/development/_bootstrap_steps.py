"""Step builders for read-only bootstrap planning."""

import os
import sys
from pathlib import Path


def component_steps(cls, component, technology, target, entries):
    builders = {
        "structure": cls._structure_steps,
        "environment": cls._environment_steps,
        "dependencies": cls._dependency_steps,
        "configuration": cls._configuration_steps,
        "hooks": cls._hook_steps,
        "database": cls._database_steps,
        "checks": cls._check_steps,
    }
    return builders[component](technology, target, entries)


def structure_steps(cls, technology, target, _entries):
    targets = [target, *(target / name for name in cls.STRUCTURE[technology])]
    return [
        cls._step(
            f"structure-{index:02d}", "structure", "filesystem",
            f"Create directory '{path}' if the plan is approved.",
            "exists" if path.is_dir() else "would_create", target=path,
            mutates_files=not path.is_dir(),
        )
        for index, path in enumerate(targets, start=1)
    ]


def environment_steps(cls, technology, target, entries):
    entries_lower = {entry.lower() for entry in entries}
    if technology == "python":
        exists = ".venv" in entries_lower
        command = None if exists else [sys.executable, "-m", "venv", ".venv"]
    else:
        manifests = {
            "node": {"package.json"}, "typescript": {"package.json"},
            "rust": {"cargo.toml"}, "php": {"composer.json"},
            "cpp": {"cmakelists.txt", "makefile"},
        }
        exists = bool(manifests[technology] & entries_lower)
        initializers = {
            "node": ["npm", "init", "-y"], "typescript": ["npm", "init", "-y"],
            "rust": ["cargo", "init"], "php": ["composer", "init"], "cpp": None,
        }
        command = None if exists else initializers[technology]
    description = "Review the existing project environment." if exists else "Review and run the stack initializer explicitly."
    return [cls._step("environment-01", "environment", "native_command", description, "exists" if exists else "manual_review", argv=command, mutates_files=not exists)]


def _dependency_command(cls, technology, target, present):
    if not present:
        return None
    if technology == "python":
        command = [cls._venv_python(target), "-m", "pip", "install"]
        command.extend(["-r", "requirements.txt"] if "requirements.txt" in present else ["--editable", "."])
        return command
    commands = {
        "node": ["npm", "install"], "typescript": ["npm", "install"],
        "rust": ["cargo", "fetch"], "php": ["composer", "install"],
    }
    if technology in commands:
        return commands[technology]
    return ["cmake", "--build", "build"] if "cmakelists.txt" in present else ["make"]


def dependency_steps(cls, technology, target, entries):
    manifests = {
        "python": {"requirements.txt", "pyproject.toml", "setup.py"},
        "node": {"package.json"}, "typescript": {"package.json"},
        "rust": {"cargo.toml"}, "php": {"composer.json"},
        "cpp": {"cmakelists.txt", "makefile"},
    }
    present = sorted(manifests[technology] & {entry.lower() for entry in entries})
    description = f"Review dependency installation from {', '.join(present)}." if present else "Define and review a dependency manifest first."
    return [cls._step(
        "dependencies-01", "dependencies", "native_command", description,
        "manual_review", argv=_dependency_command(cls, technology, target, present),
        network=bool(present), mutates_files=bool(present),
        mutates_external_state=bool(present),
    )]


def configuration_steps(cls, _technology, target, entries):
    description = "Review .env.example and create .env manually without committing secrets." if ".env.example" in entries else "Define an environment contract before creating .env."
    return [cls._step("configuration-01", "configuration", "sensitive_file", description, "manual_review", target=target / ".env", sensitive=True, mutates_files=True)]


def hook_steps(cls, _technology, target, entries):
    description = "Review the repository's existing hook policy." if ".git" in entries else "Initialize version control before choosing a hook policy."
    return [cls._step("hooks-01", "hooks", "repository_configuration", description, "manual_review", target=target / ".git" / "hooks", mutates_files=True)]


def database_steps(cls, _technology, target, entries):
    command, evidence = None, None
    if "manage.py" in entries:
        command, evidence = [cls._venv_python(target), "manage.py", "migrate"], "manage.py"
    elif "artisan" in entries:
        command, evidence = ["php", "artisan", "migrate"], "artisan"
    elif "prisma" in {entry.lower() for entry in entries}:
        command, evidence = ["npx", "prisma", "migrate", "deploy"], "prisma"
    description = f"Review database target, backup, and migration separately before running the detected {evidence} workflow." if command else "No supported migration entry point was detected."
    return [cls._step(
        "database-01", "database", "external_state", description,
        "manual_review" if command else "not_detected", argv=command,
        network=bool(command), sensitive=bool(command), mutates_files=bool(command),
        mutates_external_state=bool(command),
    )]


def check_steps(cls, technology, target, _entries):
    commands = {
        "python": [cls._venv_python(target), "-m", "pytest"],
        "node": ["npm", "test"], "typescript": ["npm", "test"],
        "rust": ["cargo", "test"], "php": ["composer", "test"],
        "cpp": ["ctest", "--test-dir", "build"],
    }
    return [cls._step(
        "checks-01", "checks", "native_command",
        "Review and run the stack's initial checks explicitly.", "manual_review",
        argv=commands[technology], network=True, mutates_files=True,
        mutates_external_state=True,
    )]


def venv_python(target):
    relative = Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"
    return str(target / ".venv" / relative)


def step(step_id, component, kind, description, status, *, target=None, argv=None, network=False, sensitive=False, mutates_files=False, mutates_external_state=False):
    result = {
        "id": step_id, "component": component, "kind": kind,
        "description": description, "status": status, "qzx_will_execute": False,
        "network": bool(network), "sensitive": bool(sensitive),
        "mutates_files": bool(mutates_files),
        "mutates_external_state": bool(mutates_external_state),
    }
    if target is not None:
        result["target"] = str(target)
    if argv is not None:
        result["argv"] = [str(value) for value in argv]
    return result
