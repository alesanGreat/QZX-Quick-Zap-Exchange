# QZX governance

QZX — Quick Zap Exchange was created by Alejandro Sánchez, who currently
serves as its lead maintainer and project steward.

## How decisions are made

Alejandro is responsible for releases, security, compatibility claims, public
contracts, roadmap priorities, project identity, and the final acceptance of
changes. Routine corrections may be decided in review. Changes to public
command behavior, telemetry, licensing, safety barriers, or project governance
should first be discussed in a focused public issue when disclosure is safe.

Decisions are evaluated against:

1. safety, privacy, and honest claims;
2. usefulness to people and AI agents;
3. cross-platform evidence and accessibility;
4. maintainability and compatibility;
5. the [QZX Core Guarantee](QZX_CORE_GUARANTEE.md) and long-term sustainability.

When a proposal is declined, the goal is to explain the technical or product
reason. No vote, payment, contribution count, or sponsorship automatically
overrides the maintainer's responsibility for the project.

## QZX Result Contract governance

QZX Result Contract is a public interoperability contract. Anyone may implement
it, validate against it, publish compatible tooling, or report independent
evidence without asking QZX for permission or becoming a QZX contributor.

Proposals that change the shared contract should start in a focused public issue
when disclosure is safe. Review should distinguish implementation convenience
from interoperability evidence and should consider existing independent
producers and consumers before changing a public invariant.

Version 1 follows the compatibility rules in
[`docs/result-contract-v1.md`](docs/result-contract-v1.md): additive evolution
may preserve v1, while removing a required field or changing the type or meaning
of a core field requires a new contract version. Published v1 schemas and
conformance material must not be silently rewritten to mean something
incompatible.

Adoption reports and sponsored pilots are judged by the same public evidence
criteria. Conformance, listing in `ADOPTERS.md`, sponsorship, and endorsement
are separate claims; none purchases control of the specification. Alejandro is
the current steward and final release authority, while future maintainer roles
must be documented here before they receive governance authority.

## Contributions and credit

Contributors retain credit for their work and certify submissions under the
Developer Certificate of Origin described in `CONTRIBUTING.md`. Meaningful
code, documentation, translation, testing, review, and sponsored work should be
credited accurately. Contribution does not automatically confer a governance
role or permission to represent QZX.

Additional maintainers may be appointed after sustained, trustworthy work and
agreement on scope, access, security duties, and decision boundaries. Their
roles should be documented here before privileged access is granted.

## Independence and conflicts

Sponsors and customers may fund a bounded result, but they do not receive
private telemetry, a guaranteed favorable result, veto power over the general
roadmap, or exclusive access to essential QZX Core features. Relevant conflicts
of interest should be disclosed before a decision.

## Continuity

Security reports use the private process in `SECURITY.md`. If Alejandro is
temporarily unavailable, no contributor should publish a release, rotate
project credentials, or claim project authority without previously documented
authorization. Establishing a second trusted administrator is an explicit
roadmap goal.
