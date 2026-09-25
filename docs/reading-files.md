# Read logs and documents in bounded, faithful pages

[Español](reading-files.es.md)

> **Unreleased development workflow.** These pagination and encoding options
> are integrated in the development checkout, not in the published QZX
> **0.2.2.0.9** package. A normal PyPI installation of that version cannot run
> this workflow. The example checks the installed command's capabilities before
> reading a file. A coordinated release must update this notice, the package,
> GitHub release and public command documentation together.

An agent inspecting a log needs more than a string. It needs to know whether
that string is the entire file, which bytes come next, whether text was lost,
and whether the file changed while the agent was working.

`readFile` provides one cross-platform JSON interface for those decisions.
It reads regular files without executing their contents or uploading them.
There is no account, API key, LLM dependency or paid feature in this workflow.

## First success without using personal data

From `QZX-Source/`, using a Python environment with QZX's dependencies:

```console
python examples/read_file_pages.py --demo --page-bytes 32
```

The script creates a temporary UTF-16 document containing accented Spanish,
Japanese and an emoji; reads it through real QZX CLI calls; verifies that the
reassembled text is exact; and removes only its own fixture. Its default output
is one compact JSON summary. Check `success: true`, `demo_verified: true` and
`pages` greater than one. These are expected conditions, not fabricated output.

The script uses the adjacent source checkout when available. When distributed
on its own, it uses QZX in the same Python environment, never an unrelated
`qzx` executable on PATH. Unsupported old packages are rejected before reading.
Telemetry is disabled for the example's child processes.

## Inspect one bounded page

With the development checkout's QZX entry point:

```console
qzx readFile application.log --max-bytes 4096 --json
qzx readFile application.log --max-lines 20 --max-bytes 16384 --json
qzx readFile "path with spaces/document.txt" --json
```

Without `--json`, QZX displays text and a descriptive message that makes a
partial read visible. Use JSON for automation. Read `content` once at the top
level; the same text is not duplicated in `details`.

The default is **65,536 source bytes per page**, plus a four-byte encoding probe.
`max_bytes` accepts integers from 1 through 16,777,216. A byte budget bounds
file I/O, not the serialized JSON size, token count or total process memory.
JSON escaping and metadata add output bytes. A smaller budget is usually better
for an agent that only needs to inspect a region of a large file.

`max_lines` also limits the page, but never disables the byte budget. A single
very long line can span pages; `ends_with_partial_line` makes this explicit.
`max_lines=0` requests no content and provides no continuation: it is not an
instruction to traverse a file.

## Continue without losing or repeating text

Every successful result provides:

| Field in `details` | Meaning |
| --- | --- |
| `offset` / `bytes_consumed` | Physical source byte range consumed, including a BOM on the first page |
| `encoding` | Actual decoder used, including the detected Unicode byte order |
| `read_complete` | Whether this page reached the observed end of the file |
| `entire_file_read` | True only when this call started at zero and reached EOF |
| `truncated_by` | `max_bytes`, `max_lines`, or null at EOF |
| `next_read` | Complete arguments for the next call, or null when no continuation is offered |
| `fingerprint_token` | A token derived from path, size, nanosecond mtime, device and inode |
| `source_bytes_read` | Actual bytes read for this page, including the encoding probe |

Use **all** of `next_read`, not a guessed offset. It preserves the decoder,
limits and `expected_fingerprint` guard. A split multibyte character or CRLF
stays for the next page; the consumer must not add newlines between pages.
`total_lines` remains `"unknown"` unless this call read the complete file from
zero. QZX does not scan the rest of a large log to manufacture that count.

The [runnable consumer](../examples/read_file_pages.py) demonstrates the entire
loop without importing private QZX implementation modules:

```console
python examples/read_file_pages.py application.log --page-bytes 4096
python examples/read_file_pages.py "legacy export.txt" --encoding cp1252
```

It checks capability discovery, exit status, structured success, byte progress,
completion, target identity, limits, encoding and file-change evidence. It
streams a digest and counters rather than keeping the entire file in memory.
The final `decoded_utf8_sha256` hashes the decoded text encoded as UTF-8; it is
**not** the original file's byte hash, especially for UTF-16 or legacy encodings.

To inspect actual page events, explicitly add `--emit-pages`. That mode emits
JSON Lines followed by a final summary. It includes unredacted file content.
Do not send those events to an external model or service without reviewing
whether the file contains secrets or personal information. A later failure
invalidates the traversal even when earlier page events have already appeared.
The example's default `--max-pages 10000` is a traversal safeguard, not a claim
that the file was fully read; exhausting it returns failure.

## Unicode without silent substitution

`encoding=auto` recognizes UTF-8, UTF-16 and UTF-32 BOMs. Without a BOM it
requires valid UTF-8; it does not guess a legacy encoding and replace unknown
bytes. Known exports can be read explicitly:

```console
qzx readFile windows-export.txt --encoding cp1252 --json
qzx readFile unmarked-utf16.txt --encoding utf-16-le --json
```

Explicit UTF-8/16/32, ASCII, Latin-1, CP1252, CP437 and CP850 are supported.
Unmarked UTF-16/32 requires explicit byte order. A requested encoding that
contradicts a BOM fails. Stateful encodings and binary codecs are not accepted
because arbitrary byte-offset resumption would not be reliable.

The returned text preserves original CRLF, LF and CR line endings. An invalid
encoding produces `decode_failed`, not successful text containing replacement
characters. NUL-bearing decoded content is rejected as `binary_content`.
A page boundary is not treated as a decoding failure when the missing bytes
belong to the next page. Extremely small budgets that cannot make progress
return `read_limit_too_small` instead of looping.

## Changing files and limits of the evidence

Within a call, QZX checks the opened regular file and the requested path before
returning success. A change detected during the read produces
`file_changed_during_read`. Ordinary changes between calls produce
`file_changed_since_previous_read` when `next_read` is used.

Do not combine pages from different versions. For an active log, copy it to a
stable file or restart the inspection at offset zero without the old guard.
An ordinary symlink can be followed, but a directory, FIFO or other special file
is not read as text. This is not a filesystem access-control boundary.

The fingerprint is **metadata evidence, not an immutable snapshot or a content
hash**. An edit that deliberately restores the observed metadata may evade it.
For forensic or transactional guarantees, obtain a proper stable snapshot first.
The command does not claim those guarantees, sanitize arbitrary terminal control
sequences, or validate the meaning of the file's contents.

## Why use QZX instead of a native read?

For a small, trusted UTF-8 file inside a Python application, `Path.read_text()`
may be simpler. A shell's native file viewer may also be the right interactive
tool. Choose QZX when a consumer needs the same documented command and JSON
semantics across supported platforms, explicit byte budgets, strict decoding,
resumable progress and change evidence.

This development interface intentionally changes the older whole-file default.
Consumers must check completion and use top-level `content`; `details.content`
is no longer duplicated. QZX remains Alpha, and these behavior changes must be
announced in the next release rather than silently described as already on PyPI.

## Verification, creator and support

The regression suites cover Unicode/BOM variants, byte and line boundaries,
legacy encodings, long lines, invalid input, changing files, special files,
CLI behavior and the executable demo. See
`tests/test_file_commands/test_read_file_pages.py` and
`tests/test_examples/test_read_file_workflow.py`. Targeted tests do not replace
the full architecture, platform, packaging, documentation and release gates.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

When this workflow solves a real problem, [support QZX's continued development](https://qzx.yumbale.com/en/donate).
For a team's log intake, document-processing or agent integration,
[discuss professional work with Alejandro](https://qzx.yumbale.com/en/professional-services).
QZX itself remains free and open source; donations are optional and do not unlock features.
