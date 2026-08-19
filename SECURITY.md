# Security policy

QZX welcomes responsible security reports about the current published package,
the current development checkout, and the official website.

## Report privately

Do not open a public issue for a vulnerability that could put users or systems
at risk. Use the repository's
[private vulnerability report](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/security/advisories/new)
so the finding can be discussed in a private GitHub advisory. If that channel
is not suitable, email `qzx@yumbale.com` with the subject
`[SECURITY] QZX report`. Include, when safe:

- the affected QZX version or website URL;
- operating system and Python version;
- a concise description of the impact;
- reproducible steps or a minimal proof of concept;
- whether the issue is already public;
- a safe way to contact you.

Do not include real credentials, private user data, destructive payloads, or
unnecessary personal information. If a large or sensitive attachment is needed,
ask for an appropriate transfer method first.

QZX will acknowledge and triage reports as capacity permits. The project does
not promise a fixed response or resolution time, but will coordinate a
reasonable disclosure path, credit the reporter if requested, and publish
useful remediation after affected users have had a fair opportunity to update.

## Scope and safety

QZX runs with the permissions of the current user and is not a security
sandbox. Reports are most useful when they show a boundary QZX claims to
enforce but fails to enforce, such as backup, preview, permission, redaction,
telemetry, parsing, or recovery behavior.

Only test systems and data you own or are explicitly authorized to test.
Security research never authorizes access to third-party infrastructure or
user data.
