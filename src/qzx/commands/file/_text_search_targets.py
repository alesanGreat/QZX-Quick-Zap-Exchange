"""Target parsing for the findText command."""

from __future__ import annotations

import os
import shlex


def split_text_search_targets(target):
    """Preserve a real path with spaces and parse quoted multi-target input."""
    raw_target = os.fspath(target)
    if os.path.exists(raw_target):
        return [raw_target]

    lexer = shlex.shlex(raw_target, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = ""
    paths = []
    for value in lexer:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        paths.append(value)
    return paths
