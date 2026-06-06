#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
from setuptools import find_packages, setup

# Leer README desde el directorio actual
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Dependencias específicas de la plataforma
install_requires = [
    "psutil",  # Para información del sistema
]

# En Windows, agregar pyreadline3
if platform.system() == "Windows":
    install_requires.append("pyreadline3")

# Determinar dependencias condicionales
extras_require = {
    'win': ['python-magic-bin'],  # Para Windows
    'unix': ['python-magic'],      # Para Unix/Linux/Mac
}

setup(
    name="qzx",
    version="0.2.2",
    author="Alejandro Sánchez",
    author_email="alesangreat@gmail.com",
    description="QZX - Quick Zap Exchange - Command line tool for automating common tasks across platforms",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alesanGreat/QZX-Quick-Zap-Exchange",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "qzx": [
            "resources/function_words/*.json",
            "resources/programming_languages/*.json",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "qzx=qzx.cli:main",
        ],
    },
    include_package_data=True,
)
