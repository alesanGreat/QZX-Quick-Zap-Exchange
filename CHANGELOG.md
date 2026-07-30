# Changelog

This file distinguishes released package history from work in the development
checkout. Changing this file does not publish a package or create a release.

## 0.2.2.0.6a8 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Prepared a corrected publication candidate from the runtime validated in
  alpha 7, without changing its 96-command interface.
- Required the source distribution to be built from the immutable tag on a
  POSIX filesystem and to preserve executable mode `0755` for `qzx.sh`.
- Added an automated distribution verifier and CI release gate for package
  metadata, attribution, hashes, PyPI rendering, and the Unix launcher mode.
- Preserved `v0.2.2.0.6a7`, its PyPI publication, GitHub pre-release,
  artifacts, and hashes after its immutable source distribution exposed
  `qzx.sh` with non-executable mode `0666`.

## 0.2.2.0.6a7 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Published the 96-command `qzx-0.2.2.0.6a7` wheel and source distribution on
  PyPI and as byte-identical immutable assets of its GitHub pre-release.
- Verified the wheel SHA-256 as
  `77c678480e9bd84336c7718f54620f43ec53648608a81fe26c580081b2d51eda`
  and the source distribution SHA-256 as
  `3b0da145f312148eb31303c7cf423186d1eb9151bb536ee1aa4c8fa587fcc2c9`.
- Recorded that the source distribution built on Windows stored `qzx.sh` with
  non-executable mode `0666`; PyPI artifacts are immutable, so the correction
  is carried by alpha 8 instead of rewriting alpha 7.
- Passed the hosted ten-platform matrix and the specialized Alpine, Debian,
  FreeBSD, OpenBSD, OmniOS, Oracle Solaris, native-formatting, and real SSH
  deployment workflows for the immutable `v0.2.2.0.6a7` tag.
- Preserved `v0.2.2.0.6a6` as an immutable validation tag; alpha 6 was not
  uploaded to PyPI or published as a GitHub Release.

## 0.2.2.0.6a6 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Fixed every Windows interpreter compatibility probe so `cmd.exe` delayed
  expansion cannot consume Python's `!=` operator, and recognized managed
  toolchain roots exposed by GitHub Actions and CMake.
- On macOS, verified an apparently absent listener with the exact native
  `lsof` query before declaring its port free.
- Withheld legacy `inspectPort` termination suggestions when the operating
  system cannot provide the process creation timestamp needed to bind a later
  `killProcess` action to the same process identity.
- Preserved `v0.2.2.0.6a5`, its GitHub pre-release, and its PyPI artifacts as
  immutable public history.

## 0.2.2.0.6a5 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Published the 96-command `qzx-0.2.2.0.6a5` wheel and source distribution on
  PyPI and attached those same artifacts to its GitHub pre-release.
- Made the Unix launcher portable to POSIX `sh` instead of assuming
  `/bin/bash`, so minimal Linux, BSD, Solaris, and illumos environments can
  execute the same checked-in launcher without an artificial Bash dependency.
- Preserved `v0.2.2.0.6a4`, its GitHub pre-release, and its PyPI artifacts as
  immutable public history.

## 0.2.2.0.6a4 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Installed Bash explicitly in the minimal Alpine test image, matching the
  interpreter declared by the executable `qzx.sh` launcher.
- Preserved `v0.2.2.0.6a3` as an immutable validation tag after Alpine exposed
  the missing guest dependency; alpha 3 was not uploaded to PyPI.

## 0.2.2.0.6a3 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Added the Git runtime required by real deployment tests in the specialized
  Alpine, FreeBSD, OpenBSD, and OmniOS jobs, and made the SSH deployment test
  verify its remote backup through SSH instead of assuming a shared local
  filesystem.
- Preserved alpha 1 and alpha 2 as immutable public PyPI and GitHub
  pre-releases; alpha 3 itself remained an unpublished validation tag.

## 0.2.2.0.6a2 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Restored the executable Git mode of `qzx.sh` after the
  `v0.2.2.0.6a1` validation tag exposed a `Permission denied` failure in
  Alpine Linux. Alpha 1 remains published and immutable; this follow-up
  preserves its tag, artifacts, hashes, and release history.

## 0.2.2.0.6a1 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Reduced the default Windows launcher path from a reported 20–60 seconds to
  a measured 0.568-second median across seven fresh processes by using the
  validated command index, importing only the requested command, deferring
  first-run telemetry until after visible output, and reserving costly system
  probes for the detailed welcome view.
- Made the Windows and Unix launchers locate a compatible standard CPython
  3.13 runtime predictably, including a bounded `uv python find 3.13`
  recovery path and structured failures when no supported runtime exists.
- Added deterministic `auditWorkspace` plans and made `repairWorkspace`
  require an explicitly selected, fingerprinted plan with preview, backup,
  staging, rollback, and time-of-check/time-of-use protection.
- Prevented partial or overlapping path moves, preserved destinations during
  cross-filesystem failures, and strengthened backup-first behavior across
  destructive commands.
- Made `createDocTemplatePython` and `cleanDevCaches` preview-first,
  transactional, and recoverable; destructive application now validates the
  target and aborts if its safety backup cannot be created.
- Reworked `releaseProject` as bounded release preparation and
  `deployProject` as an explicit artifact deployment with staging, hashes,
  health checks, rollback, and no hidden build, publication, permission, or
  service actions.
- Made `generateContent` preview the exact bounded text sample before any
  Gemini request, require explicit application, avoid credentials in URLs and
  errors, and prefer current stable models discovered from the provider.
- Consolidated portable environment reporting under `systemInfo`, retained
  `getEnvironmentInfo` as a documented compatibility wrapper, and added the
  strictly allowlisted `runDiagnosticCommand` while deprecating
  `commandsBridge` for removal after QZX 0.2.x.
- Normalized command boolean metadata so `true` and `false` are real typed
  values rather than command-specific strings.
- Expanded real command, rollback, security-boundary, launcher, Windows,
  WSL2, and cross-platform regression coverage while keeping the 16-environment
  compatibility catalog synchronized.
- Split the former all-in-one `bootstrapProject` into a read-only
  `planProjectBootstrap`; the deprecated 0.2.x wrapper now previews safely and
  refuses the former combined writes, installs, secret generation, hooks, and
  database migrations.
- Updated the bilingual command catalog, lifecycle records, structured output
  policies, reproducible evidence, and manually reviewed translations for the
  enlarged 96-command development inventory.

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
