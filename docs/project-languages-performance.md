# projectLanguages: performance without weaker analysis

Updated: 2026-09-25.

Historical incident with full diagnosis, benchmarks, failed paths, invariants and follow-up:
`docs/incidents/incident-260925-201200-projectlanguages-performance-native-selection.md`.

## Scope

The optimizations belong to QZX's project language analysis and shared path identity code. They apply to arbitrary projects; there are no rules, filenames, thresholds, or classification shortcuts specific to Workspace MCP or Valis MCP Manager. The production composition command is a benchmark consumer, not an alternative analyzer.

## Implemented changes

- The portable Pygments counter uses compact per-line code/comment flags instead of dictionaries, reuses token-category decisions, and avoids unnecessary splitting of single-line/whitespace tokens. It still consumes the public `lexer.get_tokens()` stream, including preprocessing and filters. Mixed code/comment lines, Unicode whitespace and line separators keep their previous treatment.
- Native result aggregation creates a language accumulator only when needed. It resolves example display paths only while there is room in the existing bounded example list; all files still contribute to all totals.
- `qzx.core.path_identity.canonical_path_key` resolves Windows links freshly with one final-path lookup for an existing path. Identity keys retain the extended-path prefix, avoiding the second lookup used solely to make a display path prettier. Keys are internal, not report paths. Unsupported runtimes, missing paths and lookup errors retain the portable `Path.resolve()` behavior. No persistent path identity cache is used.
- `scripts/build_native_project_languages.py` provides a reproducible source-checkout native build and verified cache installation. Source fingerprints must match before and after compilation and verification. A failing smoke test or changing source prevents installation. Identical already-installed binaries are retained rather than replaced while in use.

The concurrent general grouped-scan implementation and Rust single-read exclusion probes were preserved. Grouped scans retain per-project metadata traversal, ignore handling, unclassified files, exclusions and scan-error accounting; a successful native parse alone does not replace those checks.

## Native provisioning for a source checkout

From the QZX-Source root, with Rust and the Python development environment available:

```console
python -B scripts/build_native_project_languages.py
```

An existing external Cargo target directory may be reused:

```console
python -B scripts/build_native_project_languages.py --offline --target-dir /absolute/external/cargo-target
```

`--offline` requires dependencies to be present already. The build uses the lockfile, release profile and one Cargo worker. It never runs as part of a normal analysis. Cache discovery and the builder share `QZX_NATIVE_CACHE` or the platform's standard per-user cache location. A platform-compatible installed wheel can supply its bundled extension without this source-build step.

When Rust is unavailable, QZX retains its Python implementation. `QZX_PROJECT_LANGUAGES_BACKEND=python` explicitly selects it. Do not make discovery load an arbitrary old cache entry merely to avoid the fallback; a native binary must match the source fingerprint.

## Reliability checks

The regression suite covers the original line-counting model, 1,000 deterministic random token streams, real lexers, lexer filters, Unicode line separators, generated-marker boundaries, binary/generated/oversized precedence, ignore changes and deletions, fresh edits with the same size and modification time, symlink retargeting, and native failure followed by a clean portable scan.

Differential verification on 2026-09-25:

- Portable old versus optimized counter: exact equality for every one of 717 files, using the same freshly read content and alternating execution order.
- Native prior compatible binary versus current binary: complete payload equality for 718 records in an immutable snapshot. The snapshot comparison includes native exclusions and is distinct from the 717 recognized production files.
- Fresh canonical path resolution: alternating old/new implementations kept 717 recognized files and complete scans in all six runs. New implementation scan wall times were 0.590, 0.654 and 1.147 seconds; old implementation times were 0.960, 1.404 and 2.952 seconds. Median process CPU decreased from 0.922 to 0.703 seconds. These are in-process analyses, not fresh CLI startup measurements.

Tokei and Pygments already have different language/comment classification conventions. Native-versus-portable totals are not interchangeable golden outputs. Validate each optimized backend against its own previous implementation on identical content. A live working tree can also change between measurements.

## Measured full-command performance and limitations

The actual consumer command was launched from `C:\Windows\System32` in a fresh process for each measurement. The timer included CMD/Python startup and output generation. No analysis-result cache, daemon, skipped files or approximate counter was introduced.

Before provisioning the matching native backend, three complete runs took 60.726, 47.087 and 35.947 seconds. Native discovery had fallen back to Python because the current source fingerprint was absent from the native cache.

The final ten JSON-output runs took 1.618, 1.489, 1.166, 1.090, 1.124, 2.019, 3.281, 4.745, 1.683 and 2.077 seconds: median 1.651 seconds, with 9/10 below four seconds. The subsequent exact human-output command took 0.917 seconds. All ten recognized 717 files, 4,169,453 bytes, 104,792 content/code lines and 103,288 source/code lines.

Earlier post-change measurement batches also showed substantially larger outliers, including 16.421 seconds. They were retained rather than discarded. The changes demonstrate faster analysis and mostly sub-four-second full invocations in the final batch, but **a strict less-than-four-second bound for every invocation is not certified**. Do not present one fast run or the median as a universal latency guarantee, and do not attribute the remaining variance to a cause that has not been measured.

The portable full-file differential's counter CPU decreased from 13.641 to 13.031 seconds; its wall time decreased from 20.635 to 18.712 seconds in that alternating comparison. The portable fallback is accurate and improved, but is not claimed to meet the native route's four-second objective for this corpus.

Raw timings, profiles, frozen inputs and validation logs for the local campaign are indexed in the workspace handoff under the `20260925-language-speed` evidence directory. No PyPI, GitHub or website release is implied by these local changes.
