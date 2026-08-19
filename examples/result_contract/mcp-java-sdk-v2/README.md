# Official MCP Java SDK 2.0.0 interoperability evidence

This QZX-maintained reference executes one successful and one failed tool call
through the [official MCP Java SDK](https://github.com/modelcontextprotocol/java-sdk)
stable release `2.0.0` on Java 21 LTS. The official client launches the official
server as a child process, negotiates MCP `2025-11-25`, and communicates through
the SDK's `stdio` transports. This exercises newline-delimited JSON-RPC across a
real process boundary. The client-observed SDK models are serialized with the
SDK's Jackson mapper and validated against QZX Result Contract v1.

This example is **not independent adoption**, endorsement, certification, or
evidence from the MCP maintainers. It is a reproducible compatibility test
created and maintained by the QZX project.

## What the example proves

- the official Java client and server actually negotiate MCP `2025-11-25`;
- the server exposes the canonical QZX schema unchanged as the tool's
  `outputSchema`, producing `output_schema_mode: canonical_inline`;
- the official client observes structured content, backwards-compatible text,
  a successful result, and an `isError: true` failed result that pass the
  public QZX evidence validator;
- `io.modelcontextprotocol.sdk:mcp` is pinned exactly to `2.0.0`, and CI rejects
  any change to the committed resolved runtime dependency coordinates;
- the Maven Wrapper pins Maven `3.9.9` and authenticates its distribution with
  SHA-256; the project compiles for the SDK's Java 17 minimum while CI and the
  documented path run on Java 21 LTS.

Maven does not provide a native content-hash lock comparable to `go.sum` or a
NuGet lock file. `dependency-tree.txt` is therefore an exact coordinate lock
and review surface, not a claim that every JAR digest is recorded. Direct
dependencies and build plugins are version-pinned, Maven Central verifies its
published checksums, and CI regenerates and compares the runtime tree.

Serialization explicitly writes LF newlines, so `tool-definition.json`,
`success.json`, and `failure.json` have byte-identical SHA-256 digests across
Windows and Linux for the same source revision. `evidence-metadata.json` remains
environment-specific by design because it records the actual runtime and
operating system. Generation fails closed if any contract evidence digest
changes and publishes the observed digest map for review.

The subprocess transport exercises JSON-RPC framing but does not exercise HTTP
or SSE, and this example does not retain raw frames. Its evidence metadata
records those boundaries explicitly. The neighboring
[TypeScript SDK example](../mcp-typescript-sdk-v2/README.md) complements this
path by retaining actual Streamable HTTP response bodies.

## Reproduce on Windows PowerShell

Install Java 21 LTS and standard CPython 3.13, then run from this directory.
Maven dependencies, build outputs, and generated evidence stay outside the
checkout.

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$mavenHome = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\dependencies\maven"
$repository = Join-Path $mavenHome "repository"
$artifacts = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\cache\maven\mcp-java-sdk-v2.0.0"
$evidence = Join-Path $env:TEMP "ValisIdealis\QZX\runs\mcp-java-sdk-v2.0.0-evidence"
$schema = Resolve-Path "../../../src/qzx/resources/schemas/result-contract-v1.schema.json"
$env:MAVEN_USER_HOME = $mavenHome
./mvnw.cmd "-Dqzx.build.directory=$artifacts" "-Dmaven.repo.local=$repository" `
  "-Dmdep.outputFile=$artifacts/classpath.txt" -B -ntp clean compile dependency:build-classpath
$classpath = "$artifacts\classes;$((Get-Content "$artifacts\classpath.txt" -Raw).Trim())"
java -cp $classpath qzx.evidence.Main $schema $evidence
python -B ../../../scripts/validate_result_contract_evidence.py `
  --profile mcp-2025-11-25 `
  --success "$evidence/success.json" `
  --failure "$evidence/failure.json" `
  --tool-definition "$evidence/tool-definition.json" `
  --report "$evidence/qzx-conformance.json" `
  --json
```

## Reproduce on Linux or macOS

```bash
export JAVA_HOME="${JAVA_HOME:?Set JAVA_HOME to a Java 21 LTS installation}"
export MAVEN_USER_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/dependencies/maven"
repository="$MAVEN_USER_HOME/repository"
artifacts="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/cache/maven/mcp-java-sdk-v2.0.0"
evidence="${TMPDIR:-/tmp}/ValisIdealis/QZX/runs/mcp-java-sdk-v2.0.0-evidence"
schema="../../../src/qzx/resources/schemas/result-contract-v1.schema.json"
./mvnw "-Dqzx.build.directory=$artifacts" "-Dmaven.repo.local=$repository" \
  "-Dmdep.outputFile=$artifacts/classpath.txt" -B -ntp clean compile dependency:build-classpath
classpath="$artifacts/classes:$(cat "$artifacts/classpath.txt")"
java -cp "$classpath" qzx.evidence.Main "$schema" "$evidence"
python3.13 -B ../../../scripts/validate_result_contract_evidence.py \
  --profile mcp-2025-11-25 \
  --success "$evidence/success.json" \
  --failure "$evidence/failure.json" \
  --tool-definition "$evidence/tool-definition.json" \
  --report "$evidence/qzx-conformance.json" \
  --json
```

A passing receipt reports zero warnings and `canonical_inline` for both cases.
CI repeats the coordinate-tree comparison and keeps all Maven artifacts under
the runner's temporary directory; only the reviewable evidence bundle is
uploaded.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
