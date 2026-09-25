#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""About command for QZX identity and voluntary ways to follow or support it."""

from qzx import __version__
from qzx.core.command_base import CommandBase
from qzx.identity import product_identity, product_manifest


def _project_links(manifest):
    """Use packaged public identity, not a second hard-coded project origin."""
    origin = manifest["urls"]["site_origin"].rstrip("/")
    return {
        "creator": manifest["product"]["author"]["profile_url"],
        "repository": manifest["urls"]["repository"],
        "documentation": manifest["urls"]["command_catalog"],
        "support": origin + "/en/donate",
        "professional_services": origin + "/en/professional-services",
    }


def _about_message(identity, links):
    return (
        "{attribution}\n\n"
        "QZX is a free and open-source command-line tool for people, "
        "automation, and AI agents. Licensed under {license}.\n\n"
        "Meet the creator: {creator}\n"
        "Follow or contribute: {repository}\n"
        "Support continued development (optional): {support}\n"
        "Discuss professional services: {professional_services}\n\n"
        "QZX has no paid plans or paid features. Donations never unlock "
        "features or purchase priority; professional work is agreed separately."
    ).format(**identity, **links)


class AboutCommand(CommandBase):
    """Display the canonical QZX creator, maintainer, and license details."""

    name = "about"
    description = "Displays QZX product, creator, maintainer, and license details"
    category = "system"
    parameters = []
    examples = [
        {
            "command": "qzx about",
            "description": "Display QZX product and attribution details",
        },
    ]

    def __init__(
        self,
        *,
        identity_provider=product_identity,
        manifest_provider=product_manifest,
    ):
        """Expose canonical identity sources without introducing side effects."""
        self._identity_provider = identity_provider
        self._manifest_provider = manifest_provider

    def execute(self):
        """Return identity and reachable next steps without opening a browser."""
        identity = self._identity_provider()
        links = _project_links(self._manifest_provider())
        return {
            "success": True,
            "message": _about_message(identity, links),
            "attribution": identity["attribution"],
            "product": {
                "name": identity["name"],
                "full_name": identity["full_name"],
                "version": __version__,
            },
            "author": {
                "name": identity["author"],
                "roles": ["creator", "maintainer"],
            },
            "license": {
                "spdx": identity["license"],
                "url": identity["license_url"],
            },
            "links": links,
        }
