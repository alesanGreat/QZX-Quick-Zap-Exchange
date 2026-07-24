# Repository structure

QZX separates maintained source files from generated and local artifacts:

```text
src/qzx/              Python package
  commands/           Command implementations by category
  core/               Command loading and shared behavior
  resources/          JSON dictionaries shipped with the package
tests/                Automated tests and small fixtures
docs/                 Project documentation
  guides/             Development and implementation workflows
  operations/         Production runbooks
  policies/           Translation, versioning, and release rules
  troubleshooting/    Known regressions and focused remedies
  reference/          Generated and curated command references
    baselines/         Small reviewed historical measurements
  checklists/         Repeatable validation matrices
examples/             Standalone usage examples
scripts/              Build, CI, debug, setup, and maintenance tools
infra/containers/     Container definitions
artifacts/            Generated or machine-local files
archive/              Retained legacy material
WebsiteQZX/           Current PHP SSR/Tailwind v4/Turbo Drive website
WebsiteQZXLegacy/     Preserved former React/Vite website
```

The maintained public page sources use a page-first hierarchy:
`WebsiteQZX/php/views/pages/<page-id>/<locale>.php`; localized articles use
`WebsiteQZX/php/views/blog/<article-id>/<locale>.php`. Locale, page, shared UI,
environment-variable and translation-approval registries remain under
`WebsiteQZX/content/`. `locales.json` controls which locales are public,
`pages.json` groups slugs and search metadata by semantic page, and `blog.json`
owns article routing, publication dates, images and FAQ structured data.
`WebsiteQZX/dist/` is generated deployment output.

Command documentation keeps reviewed facts separate from projections:
`WebsiteQZX/content/command-policies.json` owns safety classifications,
`command-policy-reviews.json` binds those decisions to implementation digests,
`command-descriptions.<locale>.json` owns localized summaries,
`command-translation-reviews.json` binds them to the canonical English source,
and `command-evidence.json` stores reproducible stdout examples.
`WebsiteQZX/public/data/commands.json` and `docs/reference/commands-generated.md`
are generated projections and must not be edited by hand.

## Documentation ownership

The root `AGENTS.md` is the entry point for agents. It contains only the
cross-cutting rules, high-risk authorization boundaries, and routing table that
must be visible before the task domain is known.

Detailed information has one canonical home under `docs/`:

- `guides/` contains repeatable development and implementation procedures.
- `operations/` contains current infrastructure topology and production
  runbooks.
- `policies/` contains product decisions and authorization rules.
- `troubleshooting/` contains incident-specific symptoms and remedies.
- `reference/` contains generated or curated technical reference material.
- `checklists/` contains repeatable validation matrices.
- Top-level thematic documents such as `telemetry.md` cover one domain that
  crosses several implementation areas.

When a detail changes, update its canonical document. Keep a short reminder in
`AGENTS.md` only when missing it could cause irreversible data loss, a privacy
violation, analytics contamination, or an unauthorized external action.

## Build output

Package publishing scripts write distributions to
`artifacts/packaging/dist/`. Intermediate builds and generated metadata live
under `artifacts/packaging/`.

## Temporary and local data

Caches, ordinary runtime output, external test data, and test results live under
`artifacts/`. Git ignores those contents; only `artifacts/README.md` is
versioned. The fail-closed archives created automatically before dangerous QZX
commands are the deliberate exception: they default to `~/QZX-Backups` so
they remain outside the path being protected. `QZX_BACKUPS_PATH` can relocate
them when the operator requires another storage location.

Browser captures, smoke output and other per-execution diagnostics use
`artifacts/runs/YYYYMMDD-HHMM-<task>/`; do not add new loose task folders to the
root of `artifacts/`. Everything in `artifacts/` must remain disposable or
reproducible. Dropbox synchronization is managed outside this repository; QZX
does not use a project-local ignore file for it. Promote small, reviewed and
non-reproducible historical measurements to `docs/reference/baselines/`.

## Python package

The installable package uses the standard `src` layout. Run it from a checkout
with `qzx.bat`, `./qzx.sh`, or after an editable install:

```bash
python -m pip install -e .
python -m qzx
```
