# Changelog

This file distinguishes released package history from work in the development
checkout. Changing this file does not publish a package or create a release.

## 0.2.2.0.5 — 2026-07-29

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Made HTTP downloads transactional and restricted them to credential-free
  HTTP(S) URLs, with enforced timeouts, size validation, SHA-256 evidence, and
  fail-closed backups before replacement.
- Made ZIP creation atomic so a failed compression cannot truncate or delete a
  prior archive; existing archives now require an explicit backed-up
  replacement.
- Rebuilt ZIP extraction around whole-archive validation, staged writes,
  expansion limits, conflict preservation, and backed-up overwrites.
- Required safety backups before forced copies, forced moves, workspace
  repairs, and real source formatting; preview and dry-run paths remain
  read-only.
- Upgraded duplicate detection and repository auditing from MD5 candidates to
  SHA-256, with byte-for-byte confirmation before reporting or deleting a
  duplicate.
- Fixed the missing-language-dictionary fallback in
  `getHumanLanguageStats`; dictionary and file-analysis failures now remain in
  structured results instead of contaminating machine-readable standard
  output.
- Fixed `getProgrammingLanguageStats` field aggregation and made complete or
  partial per-file failures propagate to the command's top-level status.
  Dictionary fallbacks are also reported as structured warnings.
- Reworded public descriptions for human-language analysis and HTTP status
  checks around observable behavior instead of implementation history or
  misleading ping terminology.
- Added a pinned Ruff correctness gate and isolated dependency auditing to CI,
  alongside the expanded cross-platform GitHub Actions matrix.
- Expanded deterministic regression coverage from 276 to 302 passing tests on
  the certified local CPython 3.13 runtime.

## 0.2.2.0.4 — 2026-07-29

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Added a package-shipped lifecycle registry so every command exposes its own
  Alpha, Beta, Release Candidate, Stable, Deprecated, or Retired state
  independently from the package release channel. Planning and
  proof-of-concept entries remain outside the executable command loader.
- Added lifecycle metadata to human help, structured JSON, command listings,
  and the generated catalog, with fail-closed inventory and promotion-review
  validation.
- Replaced `auditLanguages` with the clearer `projectLanguages` command while
  retaining `auditLanguages` as a compatibility alias. The new implementation
  reports language, file, line, and byte evidence and honors project ignore
  rules.
- Hardened `compareFiles`, `checkDns`, `getNetworkConfig`,
  `getStartupPrograms`, and `inspectPort` with clearer structured failures,
  bounded work, and richer real-system evidence.
- Strengthened the shared command contract so known commands consistently
  return descriptive human output by default and complete, stable JSON with
  `--json`.
- Strengthened dangerous-command backups and approval barriers, including
  explicit target validation and process identity checks before mutation.
- Adopted the standard CPython 3.13.x build as QZX's certified Python runtime
  and concentrated the cross-platform test matrix on Python 3.13.
- Set distribution metadata to `Requires-Python: >=3.13`. Experimental
  free-threaded CPython builds, PyPy, other implementations, and other Python
  series may work but are not certified.
- Preserved the immutable `>=3.9` metadata of the already published PyPI
  `0.2.2.0.2` artifacts as a clearly labelled historical fact.
- Added maintained dependencies for language detection, portable ignore rules,
  and structured DNS queries.
- Kept `getNetworkConfig` discoverable on Unix variants whose DNS resolver
  backend cannot be imported at startup; DNS inspection now degrades locally
  instead of making the whole QZX command inventory unavailable.
- Removed live third-party TLS endpoints from the deterministic unit suite so
  provider outages cannot produce false release failures.
- Improved lifecycle inventory failures with the exact command modules and
  import errors that caused an incomplete runtime inventory.
- Synchronized the exceptional Oracle Solaris `--no-deps` test installation
  with every applicable QZX dependency and added a regression check against
  future packaging drift.
- Made the macOS/Linux `inspectPort` fallback re-check TCP and UDP ownership
  after a controlled termination, returning an evidence-backed boolean
  `port_cleared` instead of an unnecessary unknown state.

## 0.2.2.0.3 — 2026-07-29 (not distributed)

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

This pre-publication validation tag was not uploaded to PyPI or published as a
GitHub Release. Cross-platform checks exposed a Solaris command-discovery
failure and a nondeterministic external TLS test, so the immutable tag was
superseded by `0.2.2.0.4`.

## 0.2.2.0.2 — 2026-07-24

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

Published on PyPI as wheel and source distribution.

- Corrected the public author and maintainer email in package metadata to
  `qzx@yumbale.com`.
- Added the professional tag and GitHub Release workflow, including immutable
  annotated tags and reuse of the exact PyPI artifacts.
- Restricted source distributions to the public, versioned documentation and
  excluded local operational material from package artifacts.

## 0.2.2.0.1 — 2026-07-24

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

Published on PyPI as wheel and source distribution.

- Changed the project license to Apache-2.0 and added the canonical creator and
  maintainer attribution across the CLI, package metadata, README, and website.
- Reconciled the current command catalog with the official PyPI 0.2.2 wheel.
- Centralized product, release, output, compatibility, and telemetry facts in
  `src/qzx/resources/product-manifest.json`.
- Added explicit published-versus-development availability to command
  documentation.
- Added reproducible command snapshots and bilingual command descriptions.
- Consolidated the public command catalog and individual command references.

## 0.2.2 — 2025-03-18

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

Published on PyPI as `qzx-0.2.2-py3-none-any.whl`.

- SHA-256:
  `d1f6cf9b5cbc116b4397f9a11b2eb7d4723e6ffb2ea505187946196e459bd378`
- Published metadata declares Python 3.6 or newer.
- The inspected wheel contains 54 command spellings, including `qzxHelp` and
  `qzxListCommands`.

For complete distribution metadata, use the
[PyPI JSON API](https://pypi.org/pypi/qzx/json).
