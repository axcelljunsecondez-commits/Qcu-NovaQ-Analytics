# Frontend wording and combined-video release — 27 October 2026

APPROVED SPECIFICATION: the owner requested deployment after testing. This supersedes the earlier local-only delivery boundary for these completed frontend changes.

Scope: English headings by usage across NovaQ; the submitted English/Filipino wording with the thirteen documented semantic holds; refreshed Help screenshots; the exact owner-supplied combined MP4 on Home and Help; and the full-width collapsible horizontal queue comparison below the hero/video. Existing approved specs and application records define the implementation.

Protected scope: backend, queueing/statistical computations, API contracts, signing bridge, authentication behavior, database schema/data, dependencies and service configuration. No backend release, migration, seeding or production SQL is part of this release.

1. Pin current main, the exact scoped candidate, Pages project/production source and previous successful production deployment. Preserve automatic deployment settings and signing bindings.
2. Execute frontend tests/typecheck/lint/build and production dependency audit, backend tests, ruff and mypy. Inspect the complete staged file list/diff and protected-path comparison. Commit only the approved frontend and its evidence documents, then push a feature branch and open a release PR.
3. Require all configured PR CI jobs on the exact candidate. Build a Cloudflare Pages Preview from the candidate branch without copying production secrets. Check compiled UI, media and byte hashes, EN/TL headings/copy, keyboard/disclosure motion, responsive layouts and Help images. An unsigned Preview cannot establish production API functionality.
4. Merge only the pinned passing candidate; require merged-main CI and an identical source tree. Trigger the existing Pages production Git build. Leave Render and the operational database untouched.
5. Verify Pages canonical production commit/deployment and actual novaq.site bytes, Home/Help behavior, media playback/seeking, EN/TL and responsive/keyboard behavior, public security headers and existing read-only API endpoints. Record exact results and limitations.

Stop the affected release on an unexplained required gate failure or changed scope. Do not count skips/expected failures as passes. The pre-existing seed-sensitive Decision finding remains OPEN and is not repaired by this frontend release. Full narration/caption transcription, fresh OAuth registration, production database fingerprints and actual rollback execution remain outside the verification claims.

VERIFIED baseline: GitHub main is 2524ece5ed1fbb7f7dbd7b19362af57ed2f32b3a, identical in file tree to local HEAD 48442ec894bb1473f96cde0124dff62fac4d1b80 before this release's changes. Pages canonical production is eca900df-2ec2-4da2-960c-6ba91d32b7e2 at that main revision. Production auto-deployment is disabled, Preview deployment setting is none, and production signing binding is secret_text. That successful production deployment is the identified frontend rollback target; rollback execution is NOT TESTED.

Release completion and cloud outcomes must be recorded separately from this plan after execution.
