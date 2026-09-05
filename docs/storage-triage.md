# Storage triage with QZX

Use this workflow when a machine or project is running short on storage and you want evidence before deciding what to change.

The workflow is intentionally diagnostic. It does **not** delete files, clean directories, or make space automatically.

## 1. Install or update QZX

```bash
python -m pip install --pre --upgrade qzx
```

The current QZX release is pre-release software, so `--pre` is required when you explicitly want the newest published pre-release.

## 2. Measure the filesystem

```bash
qzx getDiskSpace --json
```

Use an explicit target when needed:

```bash
qzx getDiskSpace C: --json
qzx getDiskSpace /home --json
```

`getDiskSpace` is read-only. Start here to identify which filesystem is constrained before scanning content.

## 3. Investigate large files

From the directory you want to inspect:

```bash
qzx findFiles . "*" --min-size 100MiB --sort-by size --descending true --limit 20 --json
```

This returns large-file candidates without deleting or modifying them. Adjust the path, size threshold, and limit to match the environment.

## 4. Confirm duplicate content

```bash
qzx findDuplicateFiles . 10240 6 --json
```

The second positional argument is the minimum size in KB; `10240` means 10 MiB. The third is the maximum directory depth. `findDuplicateFiles` verifies duplicates using size, SHA-256, and byte-for-byte comparison.

Finding duplicate content is evidence, not permission to delete it. Copies can be intentional backups, build inputs, synchronized files, or application data.

## 5. Optionally inspect physical-disk health

Capacity pressure and hardware health are different questions. If `smartctl` is installed and you know the physical disk identifier, QZX can request S.M.A.R.T. health:

```bash
qzx getDiskHealth PhysicalDrive0 --json
qzx getDiskHealth sda --json
qzx getDiskHealth disk0 --json
```

Use the identifier that applies to the current host. `getDiskHealth` is optional and depends on host support and `smartctl`; a capacity problem does not imply a hardware-health problem.

## Decision sequence

Use the evidence in this order:

1. **Measure** — identify the constrained filesystem with `getDiskSpace`.
2. **Investigate** — list the largest relevant files with `findFiles`.
3. **Confirm** — verify actual duplicate content with `findDuplicateFiles` when duplication is suspected.
4. **Check health only when relevant** — use `getDiskHealth` separately from capacity analysis.
5. **Decide outside this workflow** — review ownership, retention, backup, and application requirements before any cleanup or deletion.

The important boundary is deliberate: **measure → investigate → confirm → optionally check health**. There is no automatic-delete step.

## Related resources

- [QZX command catalog](https://qzx.yumbale.com/en/commands)
- [Disk-space guide](https://qzx.yumbale.com/en/blog/check-disk-space-windows-linux-macos)
- [AI-agent quickstart](https://qzx.yumbale.com/en/ai-agent-quickstart)
- [Professional services](https://qzx.yumbale.com/en/professional-services)

QZX is completely free and open source. If you need help adapting this workflow to a real automation or mixed-platform environment, the professional-services route is available without changing the product's free feature set.
