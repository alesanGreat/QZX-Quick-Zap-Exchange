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

Use the global Python installation and an editable checkout:

```powershell
python -m pip install --editable .
python -c "import qzx; print(qzx.__file__)"
python -m pytest -q
```

Run the real command as well as proportional automated tests. For website
changes, use the separate website workspace and its own contribution process;
the website source is intentionally not part of this repository.

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
