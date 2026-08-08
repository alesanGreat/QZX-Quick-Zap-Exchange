# Changelog

This file distinguishes released package history from work in the development
checkout. Changing this file does not publish a package or create a release.

## 0.2.2.0.7a3 — 2026-08-08

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Moved the transitive per-command implementation fingerprint into QZX itself so
  CI, safety reviews, evidence capture, and website generation share one
  canonical digest algorithm instead of reimplementing it in private tooling.
- Upgraded Golden Core platform evidence to bind every observed command result
  to its exact implementation digest; the merger now rejects cross-run code
  drift even when version and Git revision metadata appear otherwise coherent.
- Normalized fingerprint source text to UTF-8 with LF line endings so the same
  maintained command code has one identity across Windows, Linux, and macOS;
  this deliberately migrates the 87 digest values without changing command
  behavior and eliminates checkout line endings as false code drift.
- Classified Golden Core failure evidence by meaning rather than by score: ten
  commands now capture a reproducible caller-visible failure or boundary, while
  five commands explicitly record that no representative caller-controlled
  failure applies instead of manufacturing an infrastructure fault for a green
  dashboard badge.
- Fixed PyPI-facing README links by converting repository-relative Markdown
  destinations to immutable release-tag URLs during package metadata rendering;
  release verification now rejects relative links in wheel `METADATA` and sdist
  `PKG-INFO` before publication, preventing the `/project/qzx/...` 404 pattern.

## 0.2.2.0.7a2 — 2026-08-08

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Added a sanitized Golden Core platform-evidence capturer that executes all 15
  selected commands through the real CLI on each CI host while using only
  disposable file, Git, project, and loopback HTTP fixtures.
- Added a fail-closed evidence merger that requires one immutable source
  revision, one QZX version, the complete Golden Core command set, valid result
  hashes, and observed Windows, Linux, and macOS runs before producing an
  aggregate compatibility record.
- Extended the existing GitHub Actions matrix to publish one reviewable evidence
  artifact per Windows, Linux, and macOS environment and a separately validated
  cross-platform summary instead of treating a green test badge as sufficient
  compatibility evidence.
- Added tests that reject private-path leakage, missing declared platforms,
  duplicate or tampered evidence, invalid result metadata, and incomplete
  command assertions.
- Made aggregate evidence deterministic by deriving its evidence window and
  timestamp from the input captures and stable environment IDs, and by writing
  UTF-8 with explicit LF line endings, so identical records produce the same
  bytes and SHA-256 regardless of merge time, input order, operating system,
  download directory, or local filenames.
- Preserved the Golden Core candidate boundary: platform evidence records only
  the exact host, source revision, fixtures, arguments, and results observed;
  it does not create a universal compatibility guarantee or automatic Beta
  promotion.

## 0.2.2.0.7a1 — 2026-08-08

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Established QZX Golden Core as a machine-readable candidate cohort of 15
  high-frequency read-only commands, with a public verifier and explicit
  readiness dimensions for tests, safety review, result contracts, real
  execution evidence, platform coverage, release quality, and lifecycle review.
- Kept every Golden Core command honestly at its existing Alpha lifecycle stage;
  selection is a focus mechanism, not a compatibility guarantee, certification,
  paid edition, industry-standard claim, or evidence of external adoption.
- Added positive and negative QZX Result Contract v1 conformance fixtures plus
  a dependency-free runner that checks exact acceptance and rejection behavior.
- Added an adoption guide, an evidence-gated `ADOPTERS.md` register that begins
  with no independent adopters, and a structured GitHub intake form for native
  producers, adapters, consumers, and bounded interoperability pilots.
- Expanded the canonical safe evidence workflow for Golden Core identity,
  interface discovery, environment, storage, memory, directory inventory, text
  search, and file-integrity commands without automating native or external
  evidence that still needs a controlled environment.
- Published the Alpha wheel and POSIX-built source distribution to PyPI and as
  byte-identical assets of the GitHub pre-release. A normal installation still
  selects `0.2.2.0.6`; `--pre` or an exact version opts into this Alpha.
- Verified SHA-256
  `cf0e1b266ac038752dd82f78b7663def27dced630bfb70ea497bf8cc938dff67`
  for the wheel and
  `2caedc507d28d4893c522f2f1eb5b9b7d4b4db94d046a96b967cda74abb5a462`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6 — 2026-08-07

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Published QZX Result Contract v1 as an open, additive JSON envelope with a
  JSON Schema 2020-12 document, public specification, and dependency-free
  validator for commands, automation, MCP servers, and AI-agent tools.
- Enforced the shared result contract at the final CLI boundary so invalid
  internal producer output becomes an explicit `invalid_result_contract`
  failure instead of leaking an ambiguous document.
- Required wheel and source-distribution verification to prove that the schema,
  specification, validator, immutable release description, attribution, and
  executable POSIX launcher are all present in the release artifacts.
- Closed the `0.2.2.0.6aN` package sequence with a normal PEP 440 distribution
  so `python -m pip install --upgrade qzx` selects the current 87-command QZX
  package. QZX remains Alpha software and individual command maturity remains
  explicit; this publication does not promise a stable API or version 1.0.
- Added public `qzx_in_action` fixtures and a regression test so the README's
  first structured-output example works in a fresh repository clone.
- Published the verified wheel and POSIX-built source distribution to PyPI and
  as byte-identical assets of the normal GitHub Release while preserving the
  product-wide Alpha classifier and explicit per-command maturity.
- Verified SHA-256
  `95d8fec99e5890f38c1ad7baf5251c8aaf4685db1a1b1952cb23ec56e88865cb`
  for the wheel and
  `bb9d04d0ffeef026a2f4d91f855fba0796df90c5e2d3505f0027c6024c66cdba`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6a13 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Consolidated `scanProject` into a substantially stronger `projectDoctor`
  that inspects manifests safely, reports configured workflows without
  executing project scripts, and distinguishes observed facts from checks
  that were not run.
- Removed the overlapping `getProgrammingLanguageStats` implementation and
  its private heuristic data; `projectLanguages` is now the single focused
  command for source-language composition.
- Centralized strict boolean parsing so arbitrary Python objects can no longer
  become accidental approvals in commands that mutate state or run tools.
- Added reproducible website evidence for `systemInfo`, `projectDoctor`,
  `auditWorkspace`, and the non-mutating `repairWorkspace` preview.
- Reframed command-page safety labels around behavior and built-in
  protections while keeping approval, backup, and external-service boundaries
  explicit.
- Published the verified 87-command wheel and POSIX-built source distribution
  to PyPI and as byte-identical assets of the GitHub pre-release.
- Verified SHA-256
  `b252a7f1876b0872c0405cdfb77af30967007dcb0d670a5a8e309a6ef44c3cee`
  for the wheel and
  `4527f933c6b3dfc5415477b73db843510154f9890e6002ac5cfa559c76cbc050`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6a12 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Made the packaged README describe the immutable source release it belongs
  to instead of embedding a mutable "latest published" version that became
  stale as soon as a new artifact reached PyPI.
- Added a distribution-verification barrier that requires both the wheel long
  description and source distribution to identify their own exact version.
- Preserved PyPI as the authority for the version selected by installation
  commands without allowing that external state to make packaged
  documentation internally inconsistent.
- Published the verified 89-command wheel and POSIX-built source distribution
  to PyPI and as byte-identical assets of the GitHub pre-release.
- Verified SHA-256
  `ab6109e6eb17cb3a4b8db230f84b96fcd1c55ed09a4bef6226a94b4cd215dfe2`
  for the wheel and
  `317c90d0b1abfe369ff2b3386bcfb353c3e2c7db7afb2ee74ed79d6d1d37693e`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6a11 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Replaced the misleading `findDeadCode` command with `findUnusedCode`; its
  result now identifies review candidates and explicitly warns that dynamic
  dispatch, reflection, and framework discovery can hide legitimate uses.
- Fixed the analyzer so references inside the definition file count as real
  usage and framework-discovered QZX commands and pytest suites are not
  misclassified.
- Centralized the generated-output, dependency, environment, cache, and
  coverage directories excluded by recursive source analysis.
- Corrected `projectDoctor` so stale `build/` copies no longer lower a healthy
  project's score, and made its unused-code evidence and scan boundary
  explicit.
- Removed an actually unreferenced lifecycle helper after the corrected
  analyzer isolated it from the former false positives.
- Published the verified 89-command wheel and POSIX-built source distribution
  to PyPI and as byte-identical assets of the GitHub pre-release.
- Verified SHA-256
  `2f2b557f3a345b5973bbbab7cbfa039a9af0c9693e306ac33b76c465519ed15f`
  for the wheel and
  `0925f2391d53de13ddc8cd92c5382f938c9f8b66d695eb24827eeadab11101c9`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6a10 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Removed the obsolete `kill` and `expected_pid` compatibility parameters
  from `inspectPort`; the command now has one explicit, strictly read-only
  responsibility.
- Removed the residual `killed` field and migration-only response paths from
  port inspection results.
- Revalidated real socket ownership on Windows and the deterministic macOS
  fallback, and synchronized the complete English/Spanish command page.
- Published the verified 89-command wheel and POSIX-built source distribution
  to PyPI and as byte-identical assets of the GitHub pre-release.
- Verified SHA-256
  `ef54de028c33207ec0625f48244d8c1968dc17a3b504b8caf0eb9c090b03f298`
  for the wheel and
  `5a29538a80ea251711707254416ebf42f4d0bc807c9f74dc671ac9dfb25163d0`
  for the source distribution, including executable mode `0755` for `qzx.sh`.

## 0.2.2.0.6a9 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Replaced the inherited alias layer with one case-insensitive canonical
  lowerCamelCase vocabulary, reducing the executable surface from 96 legacy
  entries to 89 focused commands.
- Retired redundant wrappers and overlapping commands instead of preserving
  compatibility machinery that obscured ownership, including the separate
  date/time variants and the duplicate large-file search.
- Renamed unclear operations around paths, archives, disks, executables,
  scaffolding, release preparation, Gemini explanations, and network speed so
  their public names describe what they actually do.
- Made `findFiles` a bounded metadata search with strict filters and rich
  structured results; content search remains the distinct responsibility of
  `findText`.
- Added command-specific `--help` and `-h`, strict boolean parsing, stable
  machine-readable failures, and stronger human output without weakening the
  complete `--json` contract.
- Hardened `runScript` with platform-aware script validation, a 60-second
  timeout, bounded stdout/stderr capture, truncation metadata, and argument
  privacy.
- Consolidated shared path hashing and identity checks, strengthened archive,
  workspace, repository, complexity, GPU, disk, executable, and diagnostics
  behavior, and removed broad exception handlers and unused imports.
- Required every dangerous public command to identify a restorable backup
  target or remain blocked unless the operator explicitly selects the safety
  bypass.
- Regenerated the bilingual command inventory, lifecycle evidence, examples,
  website details, and documentation from the canonical runtime surface.
- Validated the real CLI on PowerShell, `cmd.exe`, and WSL with standard
  CPython 3.13, plus the complete Python and website test suites and a local
  browser smoke test.
- Published the verified 89-command wheel and POSIX-built source distribution
  to PyPI and as byte-identical assets of the GitHub pre-release.
- Verified SHA-256
  `5f082266582b925154e6e51987b82a15244f798ab19ec7789dc67079f20ca3a7`
  for the wheel and
  `f326c42c64069e7c406cd7630b56161abc54fedcefcecc36de17fc8e47304fe7`
  for the source distribution.

## 0.2.2.0.6a8 — 2026-07-30

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

- Published a corrected distribution from the runtime validated in alpha 7,
  without changing its 96-command interface.
- Required the source distribution to be built from the immutable tag on a
  POSIX filesystem and to preserve executable mode `0755` for `qzx.sh`.
- Added an automated distribution verifier and CI release gate for package
  metadata, attribution, hashes, PyPI rendering, and the Unix launcher mode.
- Published byte-identical PyPI and GitHub Release artifacts: wheel
  `120b16787a36719d387bfb282cdefd993abef0028a2b6dba252fd27cc71b8878`
  and sdist
  `349c33cbff48444fc49cba9d995870400960a733a0cd0e831345126248e03998`.
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
