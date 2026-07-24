#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Canonical QZX product identity exposed by the installed package."""

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def product_manifest():
    """Return the packaged product manifest."""
    manifest = resources.files("qzx.resources").joinpath("product-manifest.json")
    with manifest.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def product_identity():
    """Return stable public identity fields used across CLI presentations."""
    product = product_manifest()["product"]
    return {
        "name": product["name"],
        "full_name": product["full_name"],
        "author": product["author"]["name"],
        "attribution": product["attribution"],
        "license": product["license"],
        "license_url": product["license_url"],
    }


def product_attribution():
    """Return the exact public creator and maintainer attribution."""
    return product_identity()["attribution"]
