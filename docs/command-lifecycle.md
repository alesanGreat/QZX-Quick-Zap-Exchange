# QZX command lifecycle

QZX records the maturity of each command independently from the maturity and
release channel of the package. This lets users and AI agents distinguish an
available but evolving command from a stable contract without pretending that
every capability matures at the same speed.

The lifecycle registry is
[`src/qzx/resources/command-lifecycle.json`](../src/qzx/resources/command-lifecycle.json).
It is shipped with QZX, validated against runtime command discovery, projected
into human help, JSON output, and public documentation, and snapshotted by each
immutable release tag.

## Three separate dimensions

| Dimension | Values | Meaning |
| --- | --- | --- |
| Roadmap delivery | Planning, Proof of concept | Work that is not a public executable command |
| Command maturity | Alpha, Beta, Release candidate, Stable | Confidence and compatibility of one command contract |
| Package release channel | `.devN`, `aN`, `bN`, `rcN`, final | Maturity of a particular QZX distribution |

A QZX Alpha package can therefore contain commands at different maturity
levels. Planning and proof-of-concept entries remain outside
`CommandLoader`; the catalog must never describe them as installed
capabilities.

## Lifecycle stages

| Stage | Publicly executable | Contract |
| --- | --- | --- |
| Planning | No | Accepted direction or specification only |
| Proof of concept | No | Isolated feasibility validation |
| Alpha | Yes | Useful for real work and feedback; interface may evolve |
| Beta | Yes | Feature complete and broadly tested; refinements remain possible |
| Release candidate | Yes | Stable-contract candidate under final validation |
| Stable | Yes | Supported documented contract with migration discipline |
| Deprecated | Yes, temporarily | Supported migration period with a replacement |
| Retired | No | Historical releases preserve the former contract |

These labels communicate product confidence; they do not replace the safety
classification, platform evidence, test status, release availability, or
structured result contract.

## Promotion requirements

Promotion is an evidence-backed product decision, not a count of elapsed days.

- **Alpha** requires a real public implementation, documented parameters and
  examples, structured `success` and `message` results, clear failure behavior,
  and the applicable QZX safety barrier.
- **Beta** additionally requires feature completeness, maintained behavioral
  tests, real execution evidence on the environments relevant to the command,
  a reviewed result contract, and no known release-blocking defects.
- **Release candidate** freezes the intended stable contract. Only corrections,
  documentation improvements, and release-blocking fixes are expected.
- **Stable** requires a deliberate compatibility commitment, complete public
  documentation, representative platform evidence, and a migration policy for
  future incompatible changes.

A regression does not silently demote a Stable command. It is fixed in a new
release. A deliberate incompatible redesign uses compatibility handling,
deprecation, or a new interface instead of erasing the earlier promise.

### Machine-enforced promotion reviews

Alpha is the conservative executable baseline. Changing a command to Beta,
Release candidate, Stable, or Deprecated also requires a `review` in the
registry with:

- a real `reviewed_on` date in `YYYY-MM-DD` form;
- a concise `rationale`;
- one or more repository-relative `evidence` references;
- for Deprecated, the canonical public `replacement`.

The loader rejects a stronger label when this review is absent or malformed.
Evidence references cannot be absolute paths or escape the repository, and
documentation generation additionally requires each referenced file to exist.
This does not prove that an attached test passed by itself, but it prevents a
promotion from being an unexplained one-word edit and gives reviewers exact
claims to verify.

```json
{
  "stage": "beta",
  "review": {
    "reviewed_on": "2026-07-29",
    "rationale": "Feature-complete contract reviewed on supported platforms.",
    "evidence": [
      "tests/test_system_commands/test_current_dir.py",
      "docs/reference/commands-generated.md"
    ]
  }
}
```

## Version history

Branches are moving lines of work. They are not the historical authority for a
published version. A release-specific Git tag freezes the source, lifecycle
registry, generated command catalog, and package artifacts together.

The registry was established after QZX `0.2.2.0.2`; it does not rewrite the
metadata of already published distributions. Every future release can expose
the exact command-to-stage map it shipped.

Python package pre-release identifiers follow the standard ordering:

```text
0.2.2.0.5.dev1
0.2.2.0.5a1
0.2.2.0.5b1
0.2.2.0.5rc1
0.2.2.0.5
```

Changing a command stage does not itself authorize changing the package
version, publishing to PyPI, creating a tag, or creating a GitHub Release.

## Contributor workflow

1. Add or update the command implementation.
2. Add the exact canonical command name to the lifecycle registry.
3. Keep Planning and Proof-of-concept entries in `roadmap`; move one into
   `commands` only when it becomes a real Alpha command.
4. Attach the required review before claiming Beta or a later public stage.
5. Run the command through both human and `--json` output.
6. Run tests and regenerate the maintained documentation projections.
7. Review lifecycle, safety, translations, and evidence as distinct facts.

Discovery and documentation generation fail when an executable command is
missing from the registry, a removed command remains, an executable command
uses a roadmap-only stage, or lifecycle metadata is malformed.
