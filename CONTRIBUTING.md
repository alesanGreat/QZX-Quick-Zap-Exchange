# Contributing to QZX

Thank you for helping QZX become more useful, predictable, and
cross-platform. Contributions can be code, tests, documentation, reproducible
bug reports, compatibility evidence, translations, or design review.

## Before starting

For a small correction, open a focused pull request. For a new command, public
contract change, large refactor, or telemetry change, open an issue first so
the design and evidence can be agreed before substantial work begins.

Read:

- [the project philosophy](docs/philosophy.md);
- [the command lifecycle policy](docs/command-lifecycle.md);
- [the project overview](README.md);
- [the security policy](SECURITY.md) for private vulnerability reports.

To contribute a real platform run without changing code, use the
[Golden Core evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=golden_core_evidence.yml)
for canonical cohort captures and Golden Core boundaries. Use the
[general platform-evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=compatibility_report.yml)
for another command or a bounded manual observation. Review every generated
record manually before uploading it; public forms must never contain
credentials, private paths or remotes, usernames, hostnames, personal data,
proprietary content, or internal addresses.

Public commands must preserve the dual-output contract: warm human output by
default and equivalent stable JSON under `--json`, with at least `success` and
a descriptive `message`.

Every public command must also have one exact entry in
`src/qzx/resources/command-lifecycle.json`. Planning and proof-of-concept work
is not registered as an executable command. Alpha, Beta, Release Candidate,
Stable, and Deprecated describe the command contract independently from the
QZX package release channel.

## Development and verification

Use the cross-platform reference runtime, standard CPython 3.13.x, and an editable checkout:

```powershell
python -m pip install --editable .
python -c "import qzx; print(qzx.__file__)"
python -m pip install ruff==0.16.0
python -m ruff check src tests
python -m pytest -q
```

QZX accepts standard CPython 3.11 or newer. The cross-platform certification
matrix remains on standard CPython 3.13.x so operating-system coverage does not
multiply into an unsustainable version-by-platform matrix. CI separately runs
version-range regressions across the supported CPython series. Experimental
free-threaded CPython builds, PyPy, and other implementations are not certified.
Evidence from those runtimes is welcome through the form matching the tested
command when it identifies the exact implementation, version, build, and
observed boundary.

Run the real command as well as proportional automated tests. For website
changes, use the separate website workspace and its own contribution process;
the website source is intentionally not part of this repository.

Mocks are limited to harmless, deterministic assertions about QZX-owned logic.
They must not stand in for an operating system, kernel, permission, process,
filesystem, shell, network, native utility, or native dependency when claiming
compatibility. A mocked test may verify isolated control flow, including a
safety barrier around a destructive operation, but it proves neither the real
operation nor the platform integration. See the
[test evidence policy](tests/README.md) before adding or reviewing tests.

Keep changes focused. Preserve unrelated comments, documentation, and local
work, and do not include generated or machine-local artifacts.

## Developer Certificate of Origin

QZX uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/)
as its initial, low-friction contribution policy. By adding a `Signed-off-by`
line, you certify that you have the right to submit the contribution under the
project's license and agree to the DCO.

Create the sign-off with:

```bash
git commit -s
```

It produces a line like:

```text
Signed-off-by: Your Name <your-email@example.com>
```

Use a real name and an email address you are comfortable placing in public
history. A GitHub `noreply` address is acceptable. Unless a file states
otherwise, submitted project material is licensed under Apache-2.0.

## Review and credit

The maintainer evaluates contributions for correctness, security, privacy,
compatibility, maintainability, evidence, and fit with QZX. A submission may be
declined or revised without diminishing the value of the attempt.

Significant contributors, reviewers, translators, and sponsors receive
appropriate credit. Sponsorship does not buy a favorable review, private
features, access to private telemetry, or control of the roadmap.
