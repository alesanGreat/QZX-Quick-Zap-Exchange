# Storage triage with QZX

Use this workflow when a machine, volume, home directory, or project is running short on storage and you want evidence before deciding what to change.

The workflow is intentionally diagnostic. It does **not** delete files, clean directories, or make space automatically.

## 1. Install or update QZX

```bash
python -m pip install --upgrade qzx
```

The normal pip channel installs the current QZX distribution when you control the selected Python environment. For an isolated standalone CLI, use `pipx install qzx`; if pip reports `externally-managed-environment`, prefer that route rather than overriding the system Python. See the [installation guide](installing-qzx.md). QZX remains Alpha software; the distribution channel and the command-stability contract are intentionally separate.

## 2. Run the complete read-only diagnosis

From the directory you want to investigate:

```bash
qzx diagnoseStorage . --json
```

Or target a specific directory or volume root:

```bash
qzx diagnoseStorage C:/ --json
qzx diagnoseStorage /home --json
```

`diagnoseStorage` combines three kinds of evidence in one structured result:

1. **Capacity** — the filesystem containing the target path, including total, used, free, and percentage used.
2. **Large files** — by default, up to 20 files of at least 100 MiB within six directory levels, sorted largest first.
3. **Verified duplicates** — by default, files of at least 10 MiB within the same depth, confirmed by size, SHA-256, and byte-for-byte comparison.

The command also returns a capacity status, prioritized review guidance, warnings, probe completeness, and `confirmed_reclaimable_bytes`. That reclaimable figure comes **only** from verified duplicate groups. A merely large file is never counted as reclaimable space.

The result includes `read_only: true`. QZX does not delete or modify files during this diagnosis.

## 3. Tune the scope when needed

A shallower or more selective scan can be useful on a very large tree:

```bash
qzx diagnoseStorage C:/ --min-file-size 500MiB --max-files 30 --max-depth 4 --json
```

If you want a faster first pass without duplicate hashing:

```bash
qzx diagnoseStorage /home --include-duplicates false --json
```

Relevant parameters:

- `path`: directory to diagnose; defaults to the current directory.
- `min_file_size`: threshold for the large-file view; defaults to `100MiB`.
- `max_files`: maximum number of largest files returned; defaults to `20`.
- `duplicate_min_size_kb`: duplicate-scan threshold in KB; defaults to `10240` (10 MiB).
- `max_depth`: maximum directory depth for both content probes; defaults to `6`.
- `include_duplicates`: enables or skips duplicate verification; defaults to `true`.

A successful result can still be `partial: true` if the optional duplicate probe fails after the capacity and large-file probes completed. In that case, inspect `warnings` and `probe_status` instead of treating missing duplicate evidence as “no duplicates”.

## 4. Use the component commands when you need finer control

`diagnoseStorage` composes existing QZX capabilities rather than replacing them. Each probe remains independently useful.

Measure only:

```bash
qzx getDiskSpace --json
qzx getDiskSpace C: --json
qzx getDiskSpace /home --json
```

Search large files with custom filters:

```bash
qzx findFiles . "*" --min-size 100MiB --sort-by size --descending true --limit 20 --json
```

Confirm duplicate content independently:

```bash
qzx findDuplicateFiles . 10240 6 --json
```

`findDuplicateFiles` verifies duplicate candidates using size, SHA-256, and byte-for-byte comparison. Finding duplicate content is evidence, not permission to delete it. Copies can be intentional backups, build inputs, synchronized files, or application data.

## 5. Keep physical-disk health separate

Capacity pressure and hardware health are different questions. If `smartctl` is installed and you know the physical disk identifier, QZX can request S.M.A.R.T. health:

```bash
qzx getDiskHealth PhysicalDrive0 --json
qzx getDiskHealth sda --json
qzx getDiskHealth disk0 --json
```

Use the identifier that applies to the current host. `getDiskHealth` is optional and depends on host support, privileges, and `smartctl`; a capacity problem does not imply a hardware-health problem.

## Decision sequence

Use the evidence in this order:

1. **Diagnose** — run `diagnoseStorage` against the relevant directory or volume.
2. **Check capacity** — confirm whether the containing filesystem is actually constrained.
3. **Review large files** — decide whether the returned large paths are expected and owned by the workload you care about.
4. **Review verified duplicates** — treat `confirmed_reclaimable_bytes` as an upper bound only if one intentional copy per duplicate group can be kept.
5. **Broaden or narrow the scan** — tune thresholds and depth when the first pass is too broad or misses the suspected area.
6. **Check hardware health only when relevant** — use `getDiskHealth` separately from capacity analysis.
7. **Decide outside this workflow** — review ownership, retention, backups, application requirements, and recovery before any cleanup or deletion.

The important boundary is deliberate: **diagnose → inspect evidence → decide**. There is no automatic-delete step.

## Related resources

- [`diagnoseStorage` command reference](https://qzx.yumbale.com/en/commands/diagnose-storage)
- [QZX command catalog](https://qzx.yumbale.com/en/commands)
- [Disk-space guide](https://qzx.yumbale.com/en/blog/check-disk-space-windows-linux-macos)
- [AI-agent quickstart](https://qzx.yumbale.com/en/ai-agent-quickstart)
- [Professional services](https://qzx.yumbale.com/en/professional-services)

QZX is completely free and open source. If you need help adapting this workflow to a production automation, storage policy, or mixed-platform environment, the professional-services route is available without changing the product's free feature set.
