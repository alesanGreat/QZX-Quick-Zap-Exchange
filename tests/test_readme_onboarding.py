"""Keep the first copyable installation aligned with the shipped product."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "src/qzx/resources/product-manifest.json").read_text(encoding="utf-8"))


def test_first_install_matches_the_published_channel():
    first_block = re.search(r"```bash\n(.*?)\n```", README, re.DOTALL).group(1).splitlines()
    assert first_block[0] == MANIFEST["channels"]["published"]["install_command"]
    assert first_block[1] == "qzx version --json"


def test_optional_extras_use_the_same_channel():
    prefix = MANIFEST["channels"]["published"]["install_command"].rsplit(" qzx", 1)[0]
    for extra in ("filetype", "ai"):
        assert f'{prefix} "qzx[{extra}]"' in README


def test_onboarding_steps_are_the_canonical_commands():
    for step in MANIFEST["onboarding"]["steps"]:
        command = " ".join(["qzx", step["command"], *step["arguments"]])
        if step["machine_output"]:
            command += " --json"
        assert command in README


def test_first_use_reaches_a_practical_project_workflow():
    assert "qzx diagnoseProject ." in README
    assert "qzx diagnoseProject . --json" in README
    assert "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/blob/main/docs/project-briefing.md" in README


def test_creator_support_and_professional_services_are_discoverable():
    assert MANIFEST["product"]["attribution"] in README
    for route in ("alejandro-sanchez", "donate", "professional-services#request"):
        assert f"https://qzx.yumbale.com/en/{route}" in README
