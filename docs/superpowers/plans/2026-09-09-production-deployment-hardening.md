# NovaQ Production Deployment Hardening Plan

Date: 2026-09-09

1. Preserve and record the dirty-tree baseline, migration chain, required
   untracked release files, and all existing verification results.
2. Harden configuration parsing, Docker-secret support, production preflight,
   database URL construction, pool bounds, and tests.
3. Separate migrations and administrator bootstrap from API startup; make the API
   non-root, deterministic, bounded, health-checked, and private in production.
4. Add trusted-proxy production nginx configuration, precise CORS, security
   headers, cache/compression rules, web health checks, and representative tests.
5. Add application rate limiting, request-ID validation, sanitized unexpected
   errors, safe access/security logging, cookie deletion parity, and session
   cleanup.
6. Remove unsupported `.xls` claims and enforce XLSX ZIP expansion, worksheet,
   row, column, cell, and dataframe-memory limits with sanitized errors.
7. Extend CI for both production images, production Compose preflight, Python/npm
   audits, secret scanning, container scanning, TLS smoke tests, and isolated
   backup/restore verification.
8. Expand operations documentation for external TLS, trusted forwarding, rates,
   secret permissions/rotation, migration/rollback sequence, backups, manifests,
   monitoring, alerts, and incident diagnostics.
9. Run focused regressions, then all backend/frontend gates, production preflight,
   image builds, disposable Postgres migration paths, HTTPS/security smoke tests,
   backup/restore rehearsal, dependency scans, image inspection, and Git checks.
10. Publish an evidence table and a final GO/NO-GO decision. Public GO requires a
    reviewed commit containing every runtime/migration file plus operator evidence
    for DNS/TLS, secret files, SMTP, edge limits, off-host encrypted backups,
    monitoring, and alerts.
