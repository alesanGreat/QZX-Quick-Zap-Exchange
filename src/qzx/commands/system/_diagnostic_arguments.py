"""Read-only argument grammar helpers for runDiagnosticCommand."""

from __future__ import annotations

import re


def validate_unix_arguments(command_name, arguments):
    """Return an error string for disallowed Unix diagnostic arguments."""
    if command_name == "date":
        return _default_only(command_name, arguments)
    if command_name == "uname":
        return _validate_uname(arguments)
    if command_name == "uptime":
        return _validate_uptime(arguments)
    if command_name == "free":
        return _validate_free(arguments)
    if command_name == "netstat":
        return _validate_netstat(arguments)
    if command_name == "ss":
        return _validate_ss(arguments)
    if command_name == "cal":
        return _validate_cal(arguments)
    return None if not arguments else "This diagnostic accepts no arguments."


def _default_only(command_name, arguments):
    if not arguments:
        return None
    return "'{}' is restricted to its local default view.".format(
        command_name
    )


def _validate_uname(arguments):
    valid = all(
        re.fullmatch(r"-[asnrvmpio]+", argument)
        for argument in arguments
    )
    return None if valid else "uname accepts only combined read-only short flags."


def _validate_uptime(arguments):
    if not arguments or arguments in (["-p"], ["-s"]):
        return None
    return "uptime permits only its default view, '-p', or '-s'."


def _validate_free(arguments):
    valid = all(
        argument in {"-b", "-k", "-m", "-g", "-h", "-t", "-w"}
        for argument in arguments
    )
    return None if valid else "free accepts only unit and summary display flags."


def _validate_netstat(arguments):
    valid = (
        bool(arguments)
        and all(
            re.fullmatch(r"-[anrtul]+", argument)
            for argument in arguments
        )
        and any("n" in argument[1:] for argument in arguments)
    )
    if valid:
        return None
    return (
        "netstat requires numeric output (-n) and accepts only combined local "
        "read-only flags without process attribution."
    )


def _validate_ss(arguments):
    valid = (
        bool(arguments)
        and all(
            re.fullmatch(r"-[alntusemoi]+", argument)
            for argument in arguments
        )
        and any("n" in argument[1:] for argument in arguments)
    )
    if valid:
        return None
    return (
        "ss requires numeric output (-n) and accepts only local network-socket "
        "display flags; socket-kill, Unix-domain paths, filter expressions, "
        "name resolution, and process attribution are blocked."
    )


def _validate_cal(arguments):
    valid = (
        len(arguments) <= 2
        and all(argument.isdigit() for argument in arguments)
    )
    return (
        None
        if valid
        else "cal accepts at most numeric month and year operands."
    )
