# Python compatibility policy

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

This document records why standard CPython 3.11 is the supported minimum for
QZX and how that decision is enforced. It is a product and compatibility policy,
not a temporary development convenience.

## Current contract

- QZX supports **standard CPython 3.11 or newer**.
- Standard **CPython 3.13.x** is the cross-platform certification runtime.
- Experimental free-threaded CPython builds, PyPy, and other Python
  implementations are not certified unless a future policy explicitly says so.
- A supported minimum and a certification runtime are deliberately different
  concepts. The certification runtime is not the package minimum.

The canonical machine-readable source remains
`src/qzx/resources/product-manifest.json`. Packaging, launchers, CI, generated
metadata, documentation, and public release surfaces must stay synchronized with
that manifest.

## Why the floor is 3.11

The `>=3.11` floor was selected after QZX's complete automated suite passed on
standard CPython 3.11, 3.12, 3.13, and 3.14. The change therefore did not trade
away tested behavior merely to claim a wider compatibility range.

Keeping 3.11 materially lowers adoption friction. Existing projects, servers,
CI runners, developer machines, and AI-agent environments can install QZX
without upgrading Python solely for QZX when the runtime is otherwise capable
of running it. Requiring 3.13 had been a larger installation barrier than the
actual code required.

The compatibility work also exposed real portability defects instead of merely
changing packaging metadata. In particular, testing the wider range led to
hardening Windows junction detection on older supported Python releases and
process-tree verification around timed-out `runScript` executions. Wider runtime
coverage therefore improved QZX itself as well as its installability.

Do **not** raise `Requires-Python` above `>=3.11` merely because:

- development happens on a newer interpreter;
- newer syntax or typing conveniences are attractive;
- the cross-platform certification matrix uses 3.13;
- a maintainer wants to simplify local tooling at the expense of users.

A future increase in the minimum Python version is a product/adoption decision.
It requires a concrete unavoidable runtime or dependency reason, explicit
maintainer approval of the compatibility tradeoff, regression evidence for the
new boundary, and synchronized updates across every affected public surface.

## CI design: support axis versus certification axis

QZX intentionally avoids multiplying every operating system by every supported
Python series. The GitHub Actions design uses two complementary axes.

The broad platform matrix in `.github/workflows/test.yml` stays on standard
CPython 3.13. It provides the deepest Windows, Linux, and macOS operating-system
and architecture evidence. The dedicated `python-version-range` job protects the
supported interpreter range separately:

- Windows Server 2025 — CPython 3.11;
- Ubuntu 24.04 — CPython 3.11;
- Ubuntu 24.04 — CPython 3.12;
- Ubuntu 24.04 — CPython 3.14.

CPython 3.13 is not duplicated in that range job because the broad certification
matrix already exercises it much more extensively.

The following OS-specific or operational workflows intentionally remain on
CPython 3.13 as certification/reference jobs rather than minimum-version jobs:

- `.github/workflows/public-surface-parity.yml`;
- `.github/workflows/test-alpine-linux-3.24.1-amd64.yml`;
- `.github/workflows/test-debian-13.6-amd64.yml`;
- `.github/workflows/test-freebsd-15.1-release-amd64.yml`;
- `.github/workflows/test-omnios-r151054-lts-x86_64.yml`;
- `.github/workflows/test-openbsd-7.9-amd64.yml`;
- `.github/workflows/test-oracle-solaris-11.4-cbe-x86_64.yml`;
- `.github/workflows/test-real-deploy-project-ubuntu-24.04-amd64.yml`;
- `.github/workflows/test-real-format-code-ubuntu-24.04-amd64.yml`.

`scorecard-analysis.yml` does not define the QZX Python runtime and is not part
of this compatibility axis.

The repository-root `action.yml` and the nested Result Contract Composite Action
also provision CPython 3.13 for their own validator process. That is an
intentional execution runtime for the Action; it does **not** mean the QZX
package or a caller repository requires Python 3.13.

A fixed `3.13` in one of these certification workflows must therefore never be
used as evidence that `Requires-Python` should be raised to 3.13. Conversely,
changing every fixed certification job to 3.11 would weaken the deliberate
separation between support-range regression and deep platform certification.

## Automatic guardrails

`tests/test_python_compatibility_policy.py` is intended to make accidental drift
fail CI. Among other things, it checks that:

- the development channel requires Python `>=3.11`;
- the certified runtime remains `CPython 3.13.x`;
- package classifiers include 3.11, 3.12, 3.13, and 3.14 and exclude unsupported
  older series;
- the broad CI matrix remains on 3.13;
- `python-version-range` exists and covers 3.11, 3.12, and 3.14;
- Black/Ruff compatibility targets remain aligned with Python 3.11.

The GitHub Action pinning tests independently protect immutable Action SHA pins.
These tests are part of the policy: an agent should not weaken or delete them to
make an incompatible runtime-floor change pass.

## Changing this policy in the future

If a genuine technical requirement eventually forces the minimum above 3.11,
treat the change as a coordinated compatibility migration rather than routine
cleanup. At minimum, review and synchronize:

1. `src/qzx/resources/product-manifest.json`;
2. package metadata and Python classifiers;
3. `qzx.bat` and `qzx.sh` interpreter selection;
4. Ruff/Black language targets and other developer tooling;
5. the GitHub Actions support-range matrix;
6. compatibility-policy tests;
7. README and public documentation;
8. CodeMeta/CITATION and generated projections where applicable;
9. release history, PyPI metadata, GitHub Release facts, and website surfaces;
10. regression evidence demonstrating the new supported boundary.

Do not rewrite historical release requirements. A new policy applies to the
release that introduces it and later releases.

## Evidence for the 3.11 decision

The compatibility campaign that established this policy recorded complete test
success on standard CPython 3.11, 3.12, 3.13, and 3.14, with 722 tests passing on
each supported series at the time of the change. Repository launchers were also
validated on 3.11, and the release pipeline separated range regression from the
3.13 cross-platform certification matrix.

That evidence is why 3.11 should be treated as an intentional supported base,
not as a number another agent should casually increase.