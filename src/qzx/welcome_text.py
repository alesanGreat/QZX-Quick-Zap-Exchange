"""Dependency-free onboarding projection shared by every QZX welcome path."""

from qzx._build_info import (
    COMMAND_CATALOG_URL,
    ONBOARDING,
    SECURITY_GUIDE_URL,
)


WELCOME_BORDER = "=" * 65


def _command_text(step: dict[str, object], *, interactive: bool) -> str:
    """Render one canonical onboarding command for CLI or terminal mode."""
    arguments = [str(argument) for argument in step["arguments"]]
    if bool(step["machine_output"]) and not interactive:
        arguments.append("--json")
    command = " ".join([str(step["command"]), *arguments])
    return command if interactive else f"qzx {command}"


def onboarding_plan(
    *,
    interactive: bool = False,
    language: str = "en",
) -> list[dict[str, str]]:
    """Return the packaged, machine-readable path to a first QZX success."""
    if language not in {"en", "es"}:
        raise ValueError("Onboarding language must be 'en' or 'es'.")
    default_risk = str(ONBOARDING["default_risk"])
    return [
        {
            "stage": str(step["stage"]),
            "command": _command_text(step, interactive=interactive),
            "purpose": str(step["purpose"][language]),
            "risk": default_risk,
        }
        for step in ONBOARDING["steps"]
    ]


def safety_guidance() -> dict[str, str]:
    """Return the safety facts exposed with the structured welcome result."""
    return {
        "execution_model": "QZX runs with the current user's permissions.",
        "guidance": (
            "Read command help before changing files, processes, or remote "
            "systems."
        ),
        "documentation_url": SECURITY_GUIDE_URL,
    }


def welcome_summary(version: str, *, detailed: bool = False) -> str:
    """Return the short human summary shared by fast and regular startup."""
    if detailed:
        return (
            "QZX is ready. The explicitly requested system snapshot was collected. "
            f"Version {version}."
        )
    return (
        "QZX is ready. Start with the read-only first-success path below. "
        f"Version {version}."
    )


def basic_welcome_message(version: str, *, interactive: bool = False) -> str:
    """Return the canonical welcome text without probing the host system."""
    plan = onboarding_plan(interactive=interactive)
    lines = [
        WELCOME_BORDER,
        "Welcome to QZX - Quick Zap Exchange",
        f"Version {version}",
        "Predictable commands for AI agents, automation, and people.",
        WELCOME_BORDER,
        "",
        "FIRST SUCCESS (read-only)",
        f"  {plan[0]['command']}",
        f"  {plan[0]['purpose']}",
        "",
        "EXPLORE",
        f"  {plan[1]['command']}",
        f"  {plan[1]['purpose']}",
        f"  {plan[2]['command']}",
        f"  {plan[2]['purpose']}",
        "",
        "SAFETY",
        "  Read command help before changing files, processes, or remote systems.",
        "  QZX runs with your current user permissions.",
        f"  {SECURITY_GUIDE_URL}",
        "",
        "DOCUMENTATION",
        f"  {COMMAND_CATALOG_URL}",
    ]
    if interactive:
        lines.extend(
            [
                "",
                "EXIT",
                "  Type 'exit' or press Ctrl+D.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "INTERACTIVE MODE",
                "  qzx terminal",
            ]
        )
    lines.append(WELCOME_BORDER)
    return "\n".join(lines) + "\n"
