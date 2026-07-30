#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Core - Componentes centrales del sistema QZX
"""

__all__ = ["CommandBase", "CommandLoader"]


def __getattr__(name):
    """Preserve public re-exports without importing the whole core eagerly."""
    if name == "CommandBase":
        from .command_base import CommandBase

        globals()[name] = CommandBase
        return CommandBase
    if name == "CommandLoader":
        from .command_loader import CommandLoader

        globals()[name] = CommandLoader
        return CommandLoader
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
