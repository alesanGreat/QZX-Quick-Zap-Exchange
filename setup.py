#!/usr/bin/env python
# -*- coding: utf-8 -*-

import importlib.util
import json
from pathlib import Path

from setuptools import find_packages, setup


PROJECT_ROOT = Path(__file__).resolve().parent
PRODUCT_MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
with PRODUCT_MANIFEST_PATH.open("r", encoding="utf-8") as manifest_file:
    PRODUCT_MANIFEST = json.load(manifest_file)

DEVELOPMENT_CHANNEL = PRODUCT_MANIFEST["channels"]["development"]
PRODUCT_URLS = PRODUCT_MANIFEST["urls"]

TEST_ENVIRONMENT_SYNC_PATH = PROJECT_ROOT / "scripts" / "sync_test_environments.py"
test_environment_spec = importlib.util.spec_from_file_location(
    "qzx_test_environment_sync",
    TEST_ENVIRONMENT_SYNC_PATH,
)
if test_environment_spec is None or test_environment_spec.loader is None:
    raise RuntimeError("Unable to load the QZX test-environment synchronizer.")
test_environment_sync = importlib.util.module_from_spec(test_environment_spec)
test_environment_spec.loader.exec_module(test_environment_sync)
test_environment_manifest = test_environment_sync.load_manifest()
test_environment_sync.validate_manifest(
    test_environment_manifest,
    validate_workflows=False,
)
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = test_environment_sync.render_readme_content(
        fh.read(),
        test_environment_manifest,
    )

# Dependencias específicas de la plataforma
install_requires = [
    "psutil",  # Para información del sistema
    "chardet",  # Detección de codificación en isFileBinary
    "colorama",  # Colores portables en findText
    "pyreadline3; platform_system == 'Windows'",
]

# Determinar dependencias condicionales
extras_require = {
    'win': ['python-magic-bin'],  # Para Windows
    'unix': ['python-magic'],      # Para Unix/Linux/Mac
    'filetype': [
        "python-magic-bin; platform_system == 'Windows'",
        "python-magic; platform_system != 'Windows'",
    ],
    'ai': ['requests', 'python-dotenv'],
}

setup(
    name="qzx",
    version=DEVELOPMENT_CHANNEL["version"],
    author="Alejandro Sánchez",
    author_email="qzx@yumbale.com",
    maintainer="Alejandro Sánchez",
    maintainer_email="qzx@yumbale.com",
    license_expression="Apache-2.0",
    license_files=["LICENSE", "NOTICE"],
    description="Predictable cross-platform commands and structured JSON for AI agents and automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=PRODUCT_URLS["site_origin"] + "/",
    project_urls={
        "Documentation": PRODUCT_URLS["documentation_en"],
        "Spanish Documentation": PRODUCT_URLS["documentation_es"],
        "Command Catalog": PRODUCT_URLS["command_catalog"],
        "Compatibility": PRODUCT_URLS["compatibility"],
        "Security": PRODUCT_URLS["security"],
        "Telemetry Policy": PRODUCT_URLS["telemetry_policy"],
        "Source": PRODUCT_URLS["repository"],
        "Issues": PRODUCT_URLS["issues"],
        "Changelog": PRODUCT_URLS["changelog"],
        "Funding": PRODUCT_URLS["site_origin"] + "/en/donate",
    },
    keywords=[
        "ai-agents",
        "automation",
        "cli",
        "cross-platform",
        "devops",
        "structured-json",
        "system-administration",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "qzx": [
            "resources/product-manifest.json",
            "resources/test-environments.json",
            "resources/function_words/*.json",
            "resources/programming_languages/*.json",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    python_requires=DEVELOPMENT_CHANNEL["requires_python"],
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "qzx=qzx.cli:main",
        ],
    },
    include_package_data=True,
)
