"""Build the command catalog returned by listCommands."""


def collect_command_catalog(command_loader):
    """Collect indexed commands without importing implementation modules."""
    categories = {}
    for entry in command_loader.get_indexed_commands():
        maturity = command_loader.get_command_maturity(entry["name"])
        categories.setdefault(entry["category"], []).append(
            {
                "name": entry["name"],
                "description": entry["description"],
                "maturity": maturity,
            }
        )
    for commands in categories.values():
        commands.sort(key=lambda command: command["name"].lower())
    return categories


def filter_command_catalog(categories, filter_text):
    """Return only categories containing commands matching the requested text."""
    if not filter_text:
        return categories

    normalized_filter = filter_text.lower()
    filtered_categories = {}
    for category, commands in categories.items():
        filtered_commands = [
            item
            for item in commands
            if normalized_filter in item["name"].lower()
            or normalized_filter in item["description"].lower()
            or normalized_filter in item["maturity"]["stage"]
            or normalized_filter in item["maturity"]["label"].lower()
        ]
        if filtered_commands:
            filtered_categories[category] = filtered_commands
    return filtered_categories


def summarize_maturity(categories):
    """Count visible commands by maturity sequence."""
    maturity_details = {}
    for commands in categories.values():
        for item in commands:
            stage = item["maturity"]["stage"]
            details = maturity_details.setdefault(
                stage,
                {
                    "count": 0,
                    "label": item["maturity"]["label"],
                    "sequence": item["maturity"]["sequence"],
                },
            )
            details["count"] += 1
    ordered = sorted(maturity_details.items(), key=lambda entry: entry[1]["sequence"])
    return {stage: details["count"] for stage, details in ordered}


def build_command_catalog_result(command_loader, filter_text=None):
    """Build the stable public result contract for listCommands."""
    categories = filter_command_catalog(
        collect_command_catalog(command_loader),
        filter_text,
    )
    command_count = sum(len(commands) for commands in categories.values())
    category_count = sum(1 for commands in categories.values() if commands)
    title = (
        f"Available Commands (filtered by '{filter_text}')"
        if filter_text
        else "Available Commands"
    )
    return {
        "success": True,
        "message": f"{title}\nCommands: {command_count}",
        "summary": {
            "commands": command_count,
            "categories": category_count,
            "filter": filter_text,
        },
        "maturity_summary": summarize_maturity(categories),
        "commands": categories,
    }
