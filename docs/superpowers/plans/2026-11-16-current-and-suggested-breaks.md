# Implementation plan

Specification: `docs/superpowers/specs/2026-11-16-current-and-suggested-breaks.md`. Owner authorization is recorded there. Base `8f611d879fdb64373f526a24b540c721934d81ba`, isolated branch `codex/current-uploaded-breaks-20261116`.

1. Establish baseline: inspect upload, Current engine, scenario verification/execution, Apply paths, report/replay consumers, and existing tests. Retain unchanged owner workbook hash. Resolve test environment restrictions with isolated SQLite tests and local loopback access.
2. Add deterministic Current break references before engine changes. Implement validated fixed-window service gating without changing arrival rates/admission rules, queue assignment, or no-break outputs. The existing shared RNG is retained: changed service timing can change same-seed arrival sample paths; no paired-demand claim is made. Cover carry across segments, starts/ends, ongoing service, queued/arriving customers, trace truncation and per-date regeneration.
3. Add shared server-derived suggested break composition and verification. Persist plan-specific breaks/hashes on schema-2 scenarios. Keep baseline hash unchanged. Update both Apply paths to draft-only confirmations, and route selected execution and reports to effective plan Setup. Test isolation, stale/tampered requests and legacy scenarios.
4. Update Suggested save/confirm flow, Current basis/version handling, replay schedule sources, and EN/TL wording. Test multiple plans, no Current cache replacement, new/old basis messages and scheduled-vs-modeled break states.
5. Re-run the exact owner-file derivation and isolated Current diagnostic; verify no starts within baseline break windows and customer accounting. Do not interpret generated events as historical observations or deployment evidence.
6. Run scoped behavioral/regression tests, backend suite, Ruff/mypy and frontend tests/typecheck/lint/build as applicable. Record failures and limitations without weakening gates. Obtain independent review on the actual diff; fix supported issues within scope and rerun affected checks.
7. Deliver reviewed local changes and concise verification evidence. Do not commit, merge, push, deploy or change operational data.

Ownership: parent implements Current engine, replay/basis/locales and reference tests; delegated implementation worker owns plan persistence/API/Suggested UI and their tests. Shared-file edits require explicit coordination. Independent reviewer must not have implemented reviewed changes.
