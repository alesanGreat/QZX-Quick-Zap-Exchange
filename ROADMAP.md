# QZX public roadmap

This roadmap describes current priorities, not promised release dates. QZX
changes versions, publishes packages, creates releases, and deploys the website
through separate reviewed operations.

## Now

- Align the public repository, PyPI package, website, license, attribution, and
  command counts.
- Keep QZX Result Contract v1 transport-independent, machine-checkable, and
  internally consistent across its normative prose, JSON Schema, validator, and
  conformance fixtures.
- Maintain the MCP 2026-07-28 interoperability profile so external MCP tools can
  adopt the QZX result envelope without adopting QZX command names or runtime.
- Complete the Apache-2.0 rights audit before declaring the license transition
  finished.
- Keep human terminal output and `--json` as two presentations of the same
  structured command result.
- Strengthen recoverable backups and explicit behavior for dangerous commands.
- Publish honest compatibility evidence without equating a target platform with
  complete proof.

## Next

- Earn the first independently reviewable QZX Result Contract implementation or
  pilot with public success and failure evidence. Until independent evidence
  exists, do not describe QZX Result Contract as an industry standard.
- Recruit pilots who complete a real task and voluntarily report repeat use,
  prioritizing MCP and non-QZX producers where the mapping solves a real result
  interoperability problem.
- Run a small reproducible benchmark on Windows and Linux before expanding it.
- Add continuous ARM64 and real macOS evidence when suitable environments are
  available.
- Improve onboarding from installation to a useful first command.
- Publish costs, a concrete support goal, and reports that separate money,
  credits, donated infrastructure, and volunteer time.
- Add a second trusted project administrator with documented responsibilities.

## Later, after demand is proven

- Broaden the benchmark across agents, models, and operating systems.
- Offer optional support, integration, training, and compatibility services
  without locking CLI features behind payment.
- Evaluate managed compatibility testing only after several independent teams
  confirm the same operational need.
- Consider a fiscal host or legal entity only when real recurring obligations
  justify its cost.

## How to propose a change

Open a focused issue describing the user problem, affected platforms, expected
result, safety implications, and evidence that would demonstrate completion.
Funding can accelerate an agreed public milestone but does not buy control of
the general roadmap.

Detailed financing and operational planning is maintained privately outside
the public repository.
