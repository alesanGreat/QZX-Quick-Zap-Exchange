"""Static dependency inventory for ``diagnoseProject``."""

import ast
import re
import tomllib

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


def read_document(path, parser, parse_errors):
    if not path.is_file():
        return None
    try:
        return parser(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, *parse_errors) as exc:
        return {"_qzx_parse_error": str(exc)}


def _manifest_records(command, root, pyproject, package_json, composer_json):
    manifests = []
    if (root / "pyproject.toml").is_file():
        manifests.append(command._parse_pyproject_dependencies(pyproject))
    if (root / "setup.py").is_file():
        manifests.append(command._parse_setup_dependencies(root / "setup.py"))
    for path in sorted(root.glob("requirements*.txt")):
        if path.is_file():
            manifests.append(command._parse_requirements_dependencies(path))
    if (root / "package.json").is_file():
        manifests.append(command._parse_mapping_dependency_groups(
            "package.json", "node", package_json,
            {"runtime": "dependencies", "development": "devDependencies", "optional": "optionalDependencies", "peer": "peerDependencies"},
        ))
    if (root / "composer.json").is_file():
        manifests.append(command._parse_mapping_dependency_groups(
            "composer.json", "php", composer_json,
            {"runtime": "require", "development": "require-dev"},
        ))
    return manifests


def inspect_dependencies(command, root, pyproject, package_json, composer_json):
    manifests = _manifest_records(command, root, pyproject, package_json, composer_json)
    if (root / "Cargo.toml").is_file():
        cargo = command._read_document(root / "Cargo.toml", tomllib.loads, (tomllib.TOMLDecodeError,))
        manifests.append(command._parse_mapping_dependency_groups(
            "Cargo.toml", "rust", cargo,
            {"runtime": "dependencies", "development": "dev-dependencies", "build": "build-dependencies"},
        ))
    if (root / "go.mod").is_file():
        manifests.append(command._parse_go_mod(root / "go.mod"))
    unique, errors, declarations = {}, [], 0
    for manifest in manifests:
        declarations += manifest.get("declaration_count", 0)
        for package in manifest.get("packages", []):
            unique.setdefault(canonicalize_name(package), package)
        if manifest["status"] == "error":
            errors.append({"manifest": manifest["path"], "error": manifest["error"]})
    return {
        "manifest_count": len(manifests),
        "manifests_found": [item["path"] for item in manifests],
        "total_declaration_count": declarations,
        "unique_declared_package_count": len(unique),
        "unique_packages": sorted(unique.values(), key=str.casefold),
        "parse_errors": errors,
        "manifests": manifests,
        "counting_note": "Declaration totals include repeated packages across manifests and dependency groups; unique_declared_package_count deduplicates normalized package names.",
    }


def _poetry_groups(data, groups):
    poetry = data.get("tool", {}).get("poetry", {})
    if not isinstance(poetry, dict):
        return
    runtime = poetry.get("dependencies", {})
    if isinstance(runtime, dict):
        groups.setdefault("runtime", []).extend(name for name in runtime if name.casefold() != "python")
    development = poetry.get("dev-dependencies", {})
    if isinstance(development, dict):
        groups.setdefault("development", []).extend(development)
    for name, group in poetry.get("group", {}).items() if isinstance(poetry.get("group", {}), dict) else []:
        dependencies = group.get("dependencies", {}) if isinstance(group, dict) else {}
        if isinstance(dependencies, dict):
            scope = "development" if name.casefold() in {"dev", "test", "lint"} else "optional"
            groups.setdefault(scope, []).extend(dependencies)


def parse_pyproject_dependencies(command, data):
    if not isinstance(data, dict) or "_qzx_parse_error" in data:
        error = data.get("_qzx_parse_error", "Invalid TOML document") if isinstance(data, dict) else "Invalid TOML document"
        return command._dependency_record("pyproject.toml", "python", error=error)
    groups = {}
    project = data.get("project", {})
    if isinstance(project, dict):
        groups["runtime"] = project.get("dependencies", [])
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            groups["optional"] = [item for values in optional.values() if isinstance(values, list) for item in values]
    build_system = data.get("build-system", {})
    if isinstance(build_system, dict):
        groups["build"] = build_system.get("requires", [])
    _poetry_groups(data, groups)
    return command._dependency_record("pyproject.toml", "python", groups)


def _setup_assignments(tree):
    assignments, setup_call = {}, None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    try:
                        assignments[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            function = node.value.func
            if (isinstance(function, ast.Name) and function.id == "setup") or (isinstance(function, ast.Attribute) and function.attr == "setup"):
                setup_call = node.value
    return assignments, setup_call


def parse_setup_dependencies(command, path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assignments, setup_call = _setup_assignments(tree)
        groups = {}
        if setup_call is not None:
            keywords = {item.arg: item.value for item in setup_call.keywords}
            runtime = command._literal_or_assignment(keywords.get("install_requires"), assignments)
            optional = command._literal_or_assignment(keywords.get("extras_require"), assignments)
            if isinstance(runtime, (list, tuple, set)):
                groups["runtime"] = list(runtime)
            if isinstance(optional, dict):
                groups["optional"] = [item for values in optional.values() if isinstance(values, (list, tuple, set)) for item in values]
        return command._dependency_record("setup.py", "python", groups)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return command._dependency_record("setup.py", "python", error=str(exc))


def literal_or_assignment(node, assignments):
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return assignments.get(node.id)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def parse_requirements_dependencies(command, path):
    try:
        requirements = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(("-r", "--requirement", "-c", "--constraint")):
                continue
            requirements.append(stripped)
        return command._dependency_record(path.name, "python", {"runtime": requirements})
    except (OSError, UnicodeError) as exc:
        return command._dependency_record(path.name, "python", error=str(exc))


def parse_mapping_dependency_groups(command, path, ecosystem, data, group_keys):
    if not isinstance(data, dict) or "_qzx_parse_error" in data:
        error = data.get("_qzx_parse_error", "Invalid dependency manifest") if isinstance(data, dict) else "Invalid dependency manifest"
        return command._dependency_record(path, ecosystem, error=error)
    groups = {}
    for scope, key in group_keys.items():
        values = data.get(key, {})
        if isinstance(values, dict):
            groups[scope] = list(values)
    return command._dependency_record(path, ecosystem, groups)


def parse_go_mod(command, path):
    try:
        modules, in_block = [], False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.split("//", 1)[0].strip()
            if stripped == "require (":
                in_block = True
                continue
            if in_block and stripped == ")":
                in_block = False
                continue
            if stripped.startswith("require "):
                stripped = stripped.removeprefix("require ").strip()
            elif not in_block:
                continue
            if stripped:
                modules.append(stripped.split()[0])
        return command._dependency_record("go.mod", "go", {"runtime": modules})
    except (OSError, UnicodeError) as exc:
        return command._dependency_record("go.mod", "go", error=str(exc))


def dependency_record(command, path, ecosystem, groups=None, error=None):
    if error is not None:
        return {"path": path, "ecosystem": ecosystem, "status": "error", "declaration_count": 0, "group_counts": {}, "packages": [], "error": error}
    normalized, packages = {}, {}
    for scope, values in (groups or {}).items():
        if not isinstance(values, (list, tuple, set)):
            continue
        names = []
        for value in values:
            name = command._dependency_name(value, ecosystem)
            if name:
                names.append(name)
                packages.setdefault(canonicalize_name(name), name)
        normalized[scope] = names
    counts = {scope: len(values) for scope, values in normalized.items() if values}
    return {"path": path, "ecosystem": ecosystem, "status": "parsed", "declaration_count": sum(counts.values()), "group_counts": counts, "packages": sorted(packages.values(), key=str.casefold)}


def dependency_name(value, ecosystem):
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if ecosystem in {"node", "php", "go", "rust"}:
        package = candidate.split()[0]
        if re.fullmatch(r"@?[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", package):
            return package
    try:
        return Requirement(candidate).name
    except InvalidRequirement:
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate)
        return match.group(0) if match else None
