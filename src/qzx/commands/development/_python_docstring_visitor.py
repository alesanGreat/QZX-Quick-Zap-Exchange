"""AST traversal and rendering for ``addPythonDocstrings``."""

from __future__ import annotations

import ast
import re


def _annotation_text(annotation):
    if annotation is None:
        return None
    try:
        return ast.unparse(annotation)
    except (AttributeError, ValueError):
        return "Any"


def _function_arguments(node):
    arguments = []
    positional = [*node.args.posonlyargs, *node.args.args]
    arguments.extend(
        {"name": item.arg, "annotation": _annotation_text(item.annotation)}
        for item in positional
    )
    if node.args.vararg:
        item = node.args.vararg
        arguments.append(
            {"name": f"*{item.arg}", "annotation": _annotation_text(item.annotation)}
        )
    arguments.extend(
        {"name": item.arg, "annotation": _annotation_text(item.annotation)}
        for item in node.args.kwonlyargs
    )
    if node.args.kwarg:
        item = node.args.kwarg
        arguments.append(
            {"name": f"**{item.arg}", "annotation": _annotation_text(item.annotation)}
        )
    return arguments


def _google_function(name, arguments, returns):
    lines = ['"""', name, ""]
    if arguments:
        lines.append("Args:")
        for item in arguments:
            annotation = f" ({item['annotation']})" if item["annotation"] else ""
            lines.append(f"    {item['name']}{annotation}: Description")
    if returns:
        lines.extend(["", "Returns:", f"    {returns}: Description"])
    return "\n".join([*lines, '"""'])


def _numpy_function(name, arguments, returns):
    lines = ['"""', name, ""]
    if arguments:
        lines.extend(["Parameters", "----------"])
        for item in arguments:
            annotation = f" : {item['annotation']}" if item["annotation"] else ""
            lines.extend([f"{item['name']}{annotation}", "    Description"])
    if returns:
        lines.extend(["", "Returns", "-------", returns, "    Description"])
    return "\n".join([*lines, '"""'])


def _sphinx_function(name, arguments, returns):
    lines = ['"""', name, ""]
    for item in arguments:
        lines.append(f":param {item['name']}: Description")
        if item["annotation"]:
            lines.append(f":type {item['name']}: {item['annotation']}")
    if returns:
        lines.extend([":return: Description", f":rtype: {returns}"])
    return "\n".join([*lines, '"""'])


def _class_details(node):
    bases = [_annotation_text(base) for base in node.bases]
    attributes = []
    for item in node.body:
        if isinstance(item, ast.Assign):
            attributes.extend(
                target.id for target in item.targets if isinstance(target, ast.Name)
            )
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            attributes.append(item.target.id)
    return bases, attributes


def _class_docstring(style, node):
    bases, attributes = _class_details(node)
    lines = ['"""', node.name, ""]
    if bases:
        lines.extend([f"Inherits from: {', '.join(bases)}", ""])
    if style == "google" and attributes:
        lines.append("Attributes:")
        lines.extend(f"    {name}: Description" for name in attributes)
    elif style == "numpy" and attributes:
        lines.extend(["Attributes", "----------"])
        for name in attributes:
            lines.extend([name, "    Description"])
    elif style == "sphinx":
        lines.extend(f":var {name}: Description" for name in attributes)
    return "\n".join([*lines, '"""'])


def _indented(docstring, indent):
    return "\n".join(f"{indent}{line}" for line in docstring.splitlines())


class DocstringVisitor(ast.NodeVisitor):
    """Collect source-line edits for function, method, and class docstrings."""

    def __init__(self, content, style, overwrite):
        self.content = content
        self.style = style
        self.overwrite = overwrite
        self.lines = content.splitlines()
        self.updates = []
        self.stats = {
            "functions_processed": 0,
            "functions_updated": 0,
            "classes_processed": 0,
            "classes_updated": 0,
            "methods_processed": 0,
            "methods_updated": 0,
        }
        self._class_depth = 0

    def _record(self, node, docstring):
        existing = ast.get_docstring(node) is not None
        if existing and not self.overwrite:
            return False
        indent = re.match(r"^(\s*)", self.lines[node.lineno - 1]).group(1) + "    "
        if existing:
            expression = node.body[0]
            start_line = expression.lineno
            end_line = expression.end_lineno or expression.lineno
        else:
            start_line = node.body[0].lineno - 1 if node.body else node.lineno
            end_line = start_line
        self.updates.append((start_line, end_line, docstring, indent, existing))
        return True

    def _visit_function(self, node):
        kind = "methods" if self._class_depth else "functions"
        self.stats[f"{kind}_processed"] += 1
        renderer = {
            "google": _google_function,
            "numpy": _numpy_function,
            "sphinx": _sphinx_function,
        }[self.style]
        arguments = _function_arguments(node)
        docstring = renderer(node.name, arguments, _annotation_text(node.returns))
        if self._record(node, docstring):
            self.stats[f"{kind}_updated"] += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)

    def visit_ClassDef(self, node):
        self.stats["classes_processed"] += 1
        if self._record(node, _class_docstring(self.style, node)):
            self.stats["classes_updated"] += 1
        self._class_depth += 1
        self.generic_visit(node)
        self._class_depth -= 1

    def get_ancestors(self, node):
        ancestors = []
        parent = getattr(node, "parent", None)
        while parent:
            ancestors.append(parent)
            parent = getattr(parent, "parent", None)
        return ancestors

    def get_modified_content(self):
        new_lines = self.lines.copy()
        for start, end, docstring, indent, replacing in sorted(
            self.updates, reverse=True
        ):
            rendered = _indented(docstring, indent)
            if replacing:
                new_lines[start - 1 : end] = [rendered]
            else:
                new_lines.insert(start, rendered)
        return "\n".join(new_lines)

    def get_changes_preview(self):
        changes = []
        for start, end, docstring, indent, replacing in self.updates:
            original = "\n".join(self.lines[start - 1 : end]) if replacing else ""
            changes.append(
                {
                    "start_line": start,
                    "end_line": end,
                    "original": original,
                    "new": _indented(docstring, indent),
                }
            )
        return changes
