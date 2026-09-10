# Website triage: DNS, TLS and HTTP with QZX

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

A website that does not load is not a single diagnosis. Use three existing
commands to separate name resolution, TLS certificate evidence and the response
from a specific HTTP endpoint before changing anything.

[Browser guide in English](https://qzx.yumbale.com/en/troubleshoot-website-dns-tls-http) ·
[Guía en español](https://qzx.yumbale.com/es/diagnosticar-sitio-web-dns-tls-http)

## Install and identify

```bash
python -m pip install --upgrade qzx
qzx version --json
```

These commands are available in published Alpha `0.2.2.0.8`; they do not require
a new development build, a QZX account or an API key. See the
[installation guide](installing-qzx.md) for pipx and managed Python environments.
Use the installed help as the source of truth for parameters.

## Run three independent checks

Replace `example.com` with an authorized hostname and the HTTPS URL with a safe,
read-only endpoint. DNS and TLS take a hostname, not a URL. Run each line
separately, including when an earlier diagnostic produces a failure:

```bash
qzx checkDns example.com --json
qzx checkSslCertificate example.com 443 --json
qzx checkUrlStatus https://example.com 10 --json
```

The HTTP timeout argument is 10 seconds, not a shared deadline for all three
commands. Remove `--json` for readable terminal output. Several JSON outputs are
separate documents; concatenating them does not create one valid JSON document.

These are network probes, not configuration changes. They contact DNS resolvers
and the destination, whose logs can record the requests. Do not use a URL that
triggers a server-side action. Review hostnames, URL query parameters and result
contents before sharing evidence; do not include credentials in a URL.

## Prepare commands for your own website

The browser guide also includes a local command preparer. Enter a hostname or
an HTTPS URL such as `https://status.example.com:8443/health`; it separates the
DNS hostname, TLS port and HTTP endpoint automatically. A bare hostname assumes
HTTPS and port 443. Review the generated URL before running each line.

The preparer does not execute QZX, contact the destination, send the input to the
website server, or save it. Internationalized hostnames are shown in their ASCII
DNS form. Editing the destination clears the previous commands until you prepare
again, and Turbo navigation discards the entered destination from its snapshots.
The original example remains available when JavaScript is disabled.

This deliberately shell-neutral preparer supports hostnames, optional ports and
simple ASCII paths. It rejects IP addresses, credentials, query parameters,
fragments, percent-encoded paths and shell metacharacters instead of silently
removing or changing them. These are limits of the **web preparer**, not a new
restriction on the published CLI. Use the command references for other endpoints.
Preparing or copying commands is not evidence that a diagnostic ran successfully.

## Read the evidence, not only the exit code

`success` describes whether the diagnostic completed. A completed check can
report a target problem. Keep the process exit code and the domain-specific
fields; neither replaces the other.

### DNS: did the name resolve from this host?

Inspect `records.A`, `records.AAAA`, `record_status` and `errors`. The configured
local resolver is part of the observation. A missing AAAA or MX record alone is
not proof of a website outage. `query_failed` is inconclusive rather than the
same thing as `no_record` or `dns_name_not_found`. Some record types can resolve
while others fail, so `success: true` does not guarantee a complete lookup.

### TLS: is the observed certificate valid here?

Inspect `is_valid`, `chain_trusted`, `hostname_match`, `days_remaining` and
`verification_error`. A decoded but invalid certificate can return
`success: true` with `is_valid: false`. Check the local clock and trust store
as well as the remote certificate. Do not disable validation to hide a trust
failure. A certificate check is not a full security audit.

### HTTP: what did this URL return?

Inspect `is_online`, `status_code`, `status_detail` and `response_time_ms`.
A received **404 can return exit code 0 and `success: true`, while
`is_online` is false**. This means a diagnostic result was obtained; it does
not mean the requested resource exists.

- **401/403:** a server or intermediary replied; inspect authentication or
  access rules rather than assuming the server is offline.
- **404:** inspect the exact path, routing and deployment.
- **5xx:** inspect the application or proxy logs you administer.
- **No `status_code`:** use `status_detail` to distinguish available connection,
  DNS, TLS or timeout evidence; do not invent a root cause.
- **2xx/3xx:** an endpoint responded. A login page, cache or broken JavaScript
  application can still return 200; verify the actual user journey separately.

The command follows ordinary redirects but is not a complete redirect-chain
trace. It does not render JavaScript, log in, provide a browser session or
perform continuous monitoring. A CDN can respond while the origin is down,
and a firewall can treat the CLI differently from a browser. These results
represent one machine at one time, not worldwide availability.

## A recorded target failure, not an invented sample

This excerpt comes from the published `0.2.2.0.8` wheel on standard CPython
3.13.13, Windows x64. A disposable loopback HTTP endpoint intentionally returned
404; it is not an outage of example.com or QZX.

```json
{
  "success": true,
  "is_online": false,
  "status_code": 404
}
```

[The complete JSON observations](website-triage-evidence.json) preserve both
the HTTP 404 and negative-DNS results, their exit codes, runtime, capture times
and the verified PyPI wheel fingerprint. This controlled evidence does not
establish cross-platform compatibility, real adoption, uptime or performance.

## Ask an agent for the next useful check

> Using these three QZX results, identify the earliest layer with evidence of a
> problem. Distinguish a failed diagnostic from an unhealthy target and an
> inconclusive query. Cite actual fields, separate facts from assumptions, and
> propose one next check. Do not change DNS, certificates, firewall rules or
> deployments. Do not claim the application works merely because HTTP returned 200.

For a recurring check, define the endpoint's expected status, acceptable TLS
state, sampling interval and escalation policy explicitly. Run a bounded probe
from an authorized second network when the observation point matters. A
single diagnostic does not establish an SLA or a performance benchmark.

## Support or integrate the workflow

The CLI is free. [Support QZX development](https://qzx.yumbale.com/en/donate)
or [discuss scoped professional work with Alejandro Sánchez](https://qzx.yumbale.com/en/professional-services#request)
for an alerting policy, deployment gate or custom integration. Agree on scope,
acceptance evidence and budget first; a donation does not buy priority or an
emergency-response commitment.

## References and limitations

- [checkDns](https://qzx.yumbale.com/en/commands/check-dns)
- [checkSslCertificate](https://qzx.yumbale.com/en/commands/check-ssl-certificate)
- [checkUrlStatus](https://qzx.yumbale.com/en/commands/check-url-status)
- [IETF HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- [Python TLS verification](https://docs.python.org/3/library/ssl.html)
- [QZX security and telemetry](https://qzx.yumbale.com/en/security)

QZX remains Alpha. Consult the installed command help and
[compatibility evidence](https://qzx.yumbale.com/en/compatibility) rather than
assuming every platform, proxy or authentication setup behaves identically.
