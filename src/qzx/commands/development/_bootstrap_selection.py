"""Input and technology selection for bootstrap planning."""


def root_entries(target):
    if not target.exists():
        return set(), None
    try:
        return {entry.name for entry in target.iterdir()}, None
    except OSError as exc:
        return set(), f"{type(exc).__name__}: {exc}"


def detect_technologies(entries):
    by_lower = {entry.lower(): entry for entry in entries}
    evidence_sets = {
        "rust": ("cargo.toml",),
        "php": ("composer.json",),
        "cpp": ("cmakelists.txt", "makefile"),
        "python": ("pyproject.toml", "requirements.txt", "setup.py"),
    }
    candidates = []
    for technology, names in evidence_sets.items():
        evidence = sorted(by_lower[name] for name in names if name in by_lower)
        if evidence:
            candidates.append({"technology": technology, "evidence": evidence})
    if "package.json" in by_lower:
        technology = "typescript" if "tsconfig.json" in by_lower else "node"
        names = ["package.json", "tsconfig.json"] if technology == "typescript" else ["package.json"]
        candidates.append({"technology": technology, "evidence": sorted(by_lower[name] for name in names)})
    return sorted(candidates, key=lambda item: item["technology"])


def select_technology(cls, value, entries):
    candidates = cls._detect_technologies(entries)
    if value is not None and str(value).strip():
        technology = str(value).strip().lower()
        if technology not in cls.SUPPORTED_TECHNOLOGIES:
            return None, (
                "unsupported_technology",
                f"Technology '{technology}' is not supported.",
                "Choose one exact supported technology; QZX made no guess.",
            )
        evidence = next((item["evidence"] for item in candidates if item["technology"] == technology), [])
        return technology, {"method": "explicit", "evidence": evidence, "observed_candidates": candidates}
    if not candidates:
        return None, (
            "technology_required",
            "No supported technology manifest was found.",
            "Pass --tech explicitly. QZX does not silently default an empty or unknown project to Python.",
        )
    if len(candidates) > 1:
        detected = ", ".join(item["technology"] for item in candidates)
        return None, (
            "ambiguous_technology",
            f"Multiple technology stacks were detected: {detected}.",
            "Pass --tech explicitly after reviewing the mixed repository.",
        )
    selected = candidates[0]
    return selected["technology"], {
        "method": "manifest",
        "evidence": selected["evidence"],
        "observed_candidates": candidates,
    }


def select_components(cls, value):
    if value is None:
        return list(cls.COMPONENTS), None
    if isinstance(value, str):
        raw = [item.strip().lower() for item in value.split(",")]
    else:
        try:
            raw = [str(item).strip().lower() for item in value]
        except TypeError:
            return None, "components must be text or a sequence of names."
    requested = list(dict.fromkeys(item for item in raw if item))
    if requested == ["all"]:
        return list(cls.COMPONENTS), None
    if not requested:
        return None, "At least one bootstrap component is required."
    if "all" in requested:
        return None, "'all' cannot be combined with named components."
    unknown = sorted(set(requested) - set(cls.COMPONENTS))
    if unknown:
        return None, f"Unknown bootstrap components: {', '.join(unknown)}."
    return [item for item in cls.COMPONENTS if item in requested], None


def failure(error_code, error, message, target, **details):
    payload = {
        "path": str(target), "read_only": True, "files_written": 0,
        "commands_run": 0, "network_requests": 0,
    }
    payload.update(details)
    return {"success": False, "error_code": error_code, "error": error, "message": message, "details": payload}
