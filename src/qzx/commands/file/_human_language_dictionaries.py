"""Human-language dictionary loading for getHumanLanguageStats."""

from __future__ import annotations

import json
import os


def load_function_words(command, directory):
    """Load function-word dictionaries and preserve warning semantics."""
    if not os.path.isdir(directory):
        command.dictionary_warnings.append(
            "Human-language dictionaries were not found at "
            f"'{directory}'; character-based fallback analysis will be used."
        )
        return {}

    function_words = {}
    files_found = 0
    for filename in os.listdir(directory):
        if not filename.endswith(".json"):
            continue
        files_found += 1
        language = os.path.splitext(filename)[0].lower()
        words = _load_dictionary_file(command, directory, filename)
        if words:
            function_words[language] = words

    if not function_words:
        _warn_empty_dictionary_set(command, directory, files_found)
    return function_words


def _load_dictionary_file(command, directory, filename):
    path = os.path.join(directory, filename)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            command.dictionary_warnings.append(
                f"Human-language dictionary '{filename}' contains invalid JSON: {exc}"
            )
            return set()
        return _words_from_data(command, filename, data)
    except Exception as exc:
        command.dictionary_warnings.append(
            f"Human-language dictionary '{filename}' could not be loaded: "
            f"{type(exc).__name__}: {exc}"
        )
        return set()


def _words_from_data(command, filename, data):
    if isinstance(data, list):
        return {word.lower() for word in data if isinstance(word, str)}
    if not isinstance(data, dict):
        command.dictionary_warnings.append(
            f"Human-language dictionary '{filename}' contains no usable word list."
        )
        return set()
    if "words" in data and isinstance(data["words"], list):
        return {
            word.lower()
            for word in data["words"]
            if isinstance(word, str)
        }

    words = set()
    for key, value in data.items():
        if isinstance(value, str):
            words.add(value.lower())
        elif isinstance(key, str) and key not in {"metadata", "info"}:
            words.add(key.lower())
    if not words:
        command.dictionary_warnings.append(
            f"Human-language dictionary '{filename}' contains no usable word list."
        )
    return words


def _warn_empty_dictionary_set(command, directory, files_found):
    if files_found > 0:
        command.dictionary_warnings.append(
            f"Found {files_found} human-language dictionary file(s), "
            "but none could be loaded."
        )
    else:
        command.dictionary_warnings.append(
            "No human-language dictionary files were found in "
            f"'{directory}'."
        )
