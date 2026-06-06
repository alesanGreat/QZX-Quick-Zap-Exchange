# Local artifacts

This directory is the single destination for generated and machine-local files.
Its contents are ignored by Git.

- `backups/`: local project backup archives.
- `cache/`: installed dependencies and disposable caches.
- `packaging/build/`: intermediate Python package builds.
- `packaging/dist/`: wheels and source distributions.
- `packaging/metadata/`: generated package metadata.
- `runtime/output/`: command output and scratch files.
- `tests/data/`: large or external test datasets.
- `tests/results/`: test reports and container output.

Every subdirectory can be recreated or repopulated without changing source code.
