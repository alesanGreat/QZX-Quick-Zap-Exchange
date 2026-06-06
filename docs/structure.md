# Repository structure

QZX separates maintained source files from generated and local artifacts:

```text
src/qzx/              Python package
  commands/           Command implementations by category
  core/               Command loading and shared behavior
  resources/          JSON dictionaries shipped with the package
tests/                Automated tests and small fixtures
docs/                 Guides, references, and checklists
examples/             Standalone usage examples
scripts/              Build, CI, debug, setup, and maintenance tools
infra/containers/     Container definitions
artifacts/            Generated or machine-local files
archive/              Retained legacy material
WebsiteQZX/           Website project
```

## Build output

Package publishing scripts write distributions to
`artifacts/packaging/dist/`. Intermediate builds and generated metadata live
under `artifacts/packaging/`.

## Temporary and local data

Backups, caches, runtime output, external test data, and test results all live
under `artifacts/`. Git ignores those contents; only
`artifacts/README.md` is versioned.

## Python package

The installable package uses the standard `src` layout. Run it from a checkout
with `qzx.bat`, `./qzx.sh`, or after an editable install:

```bash
python -m pip install -e .
python -m qzx
```
