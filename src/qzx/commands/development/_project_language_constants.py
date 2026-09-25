"""Classification constants for ``projectLanguages``."""

import re


DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".angular", ".gradle", ".idea", ".mypy_cache",
    ".next", ".nox", ".nuxt", ".pytest_cache", ".ruff_cache", ".svelte-kit",
    ".tox", ".venv", ".vscode", "__pycache__", "bower_components", "build",
    "coverage", "dist", "env", "node_modules", "target", "venv", "vendor",
}
PROSE_ALIASES = {
    "adoc", "asciidoc", "markdown", "md", "mdown", "mkd", "rst", "rest",
    "text", "txt",
}
DATA_ALIASES = {
    "cfg", "csv", "ini", "json", "json5", "jsonld", "properties", "toml",
    "yaml", "yml",
}
MARKUP_ALIASES = {
    "haml", "html", "html5", "pug", "sgml", "slim", "svg", "xml", "xsl",
    "xslt",
}
STYLESHEET_ALIASES = {"css", "less", "sass", "scss", "stylus"}
SOURCE_KINDS = {"programming", "markup", "stylesheet"}
GENERATED_NAME_PATTERNS = (
    re.compile(r".*\.min\.(?:css|js|mjs|cjs)$", re.IGNORECASE),
    re.compile(r".*\.map$", re.IGNORECASE),
)
GENERATED_CONTENT_PATTERN = re.compile(
    r"(?:@generated|auto[- ]generated|automatically generated|"
    r"code generated .* do not edit|do not edit[.!]?\s*$)",
    re.IGNORECASE | re.MULTILINE,
)
