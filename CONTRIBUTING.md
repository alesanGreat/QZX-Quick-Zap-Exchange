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
- [the project overview](README.md);
- [the security policy](SECURITY.md) for private vulnerability reports.

Public commands must preserve the dual-output contract: warm human output by
default and equivalent stable JSON under `--json`, with at least `success` and
a descriptive `message`.

## Development and verification

Use a standard global CPython 3.13.x installation and an editable checkout:

```powershell
python -m pip install --editable .
python -c "import qzx; print(qzx.__file__)"
python -m pytest -q
```

QZX concentrates its compatibility tests on the standard CPython 3.13.x
build. Other Python versions or implementations may work, but experimental
free-threaded CPython builds, PyPy, and other implementations are not
certified. Compatibility reports from those runtimes are welcome when they
identify the exact implementation, version, and build.

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
