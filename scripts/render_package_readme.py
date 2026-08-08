#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Expose the package-README helpers under a focused developer-facing module."""

from __future__ import annotations

if __package__:
    from .verify_distribution_artifacts import (
        find_repository_relative_links,
        is_repository_relative_destination,
        render_package_readme,
        verify_package_index_links,
    )
else:
    from verify_distribution_artifacts import (
        find_repository_relative_links,
        is_repository_relative_destination,
        render_package_readme,
        verify_package_index_links,
    )


__all__ = [
    "find_repository_relative_links",
    "is_repository_relative_destination",
    "render_package_readme",
    "verify_package_index_links",
]
