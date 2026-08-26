# QZX public roadmap

This roadmap describes current priorities, not promised release dates. QZX
changes versions, publishes packages, creates releases, and deploys the website
through separate reviewed operations.

## Now

- Earn the first independently reviewable implementation or bounded pilot of
  **QZX Result Contract v1** with public success and failure evidence. Until
  independent evidence exists, do not describe the contract as an industry
  standard or list an adopter.
- Keep existing external interoperability proposals technically healthy and
  easy for upstream maintainers to review. Resolve real upstream problems,
  respond quickly to technical feedback, and prefer a useful accepted change
  over QZX branding or outreach volume.
- Keep Result Contract v1 transport-independent, machine-checkable, and aligned
  across normative prose, JSON Schema, dependency-free validators, receipts,
  fixtures, and the reusable repository-root Composite Action.
- Maintain revision-specific MCP profiles for 2025-06-18, 2025-11-25, and
  2026-07-28 without forcing adopters to upgrade their whole MCP stack or adopt
  QZX command names/runtime.
- Preserve the Golden Core evidence chain for its 15 selected commands. The
  current published names have release-quality evidence, but all remain Alpha
  until lifecycle promotion and independent evidence justify a stronger claim.
- Keep the public repository, PyPI package metadata, website, license,
  attribution, command count, compatibility claims, and generated references in
  sync without changing versions merely to refresh documentation.
- Keep human terminal output and `--json` as two presentations of the same
  structured command result, with recoverable safeguards for dangerous
  operations.

## Next

- Convert useful upstream work into the first independently accepted or
  published interoperability evidence; do not count an open contributor PR as
  adoption, endorsement, or certification.
- Revalidate dependent integrations only after their upstream API dependency is
  accepted, rather than publishing chains of PRs against speculative APIs.
- Collect independent Golden Core platform/failure reproductions that complement
  QZX's own Windows, Linux, macOS, x64 and ARM64 CI evidence.
- Run a small reproducible benchmark on real tasks before broadening claims
  about time, token, or workflow savings.
- Measure installation-to-first-value friction from real users and simplify the
  maintained onboarding path only when evidence identifies a concrete obstacle.
- Publish costs, a concrete support goal, and reports that separate money,
  credits, donated infrastructure, commercial work, and volunteer time.
- Add a second trusted project administrator with documented responsibilities
  when a real continuity need and suitable person exist.

## Completed foundations to preserve

- Apache-2.0 licensing, attribution, governance, security, contribution/DCO,
  trademark, citation, sponsorship, issue-template, and public-roadmap surfaces
  are published and must remain coherent.
- QZX exposes 87 canonical commands with no compatibility aliases; command
  lookup is case-insensitive while documentation uses canonical
  `lowerCamelCase` spelling.
- The Result Contract public schema, conformance receipt, evidence validators,
  negative fixtures, immutable GitHub Action pinning examples, and CI smoke
  tests cover both conformance and intentional nonconformance.
- Golden Core release-quality evidence is bound to published pre-release
  `0.2.2.0.7a5`; this evidence does not itself promote commands beyond Alpha.
- The no-argument and `welcome` flows provide a read-only first success,
  catalog exploration, command-specific help, safety guidance, and the same
  machine-readable onboarding plan without probing the host by default.
- Public CI includes real Windows, Linux and macOS coverage, including ARM64
  jobs where supported. Platform targets are still narrower claims than
  universal compatibility.

## Later, after demand is proven

- Broaden benchmarks across agents, models, operating systems, and independent
  environments.
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
