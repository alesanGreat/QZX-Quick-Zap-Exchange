#!/usr/bin/env python3
"""Smoke the installed native projectLanguages backend outside the source tree."""

import json
import tempfile
from pathlib import Path

from qzx.commands.development.project_languages import ProjectLanguagesCommand


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="qzx-native-language-smoke-") as temporary:
        root = Path(temporary)
        (root / "sample.py").write_text(
            "# comment\nprint('QZX')\n\n",
            encoding="utf-8",
        )
        result = ProjectLanguagesCommand().execute(str(root))

    engine = result.get("analysis_engine", {})
    languages = result.get("languages", [])
    if (
        not result.get("success")
        or engine.get("language_detection") != "Tokei"
        or engine.get("native") is not True
        or result.get("languages_found") != {"Python": 1}
        or not languages
        or languages[0].get("code_lines") != 1
        or languages[0].get("comment_lines") != 1
        or languages[0].get("blank_lines") != 1
    ):
        raise SystemExit(
            "Native projectLanguages smoke failed: "
            + json.dumps(result, ensure_ascii=False, sort_keys=True)
        )

    print(
        json.dumps(
            {
                "success": True,
                "engine": engine.get("language_detection"),
                "engine_version": engine.get("language_detection_version"),
                "native": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
