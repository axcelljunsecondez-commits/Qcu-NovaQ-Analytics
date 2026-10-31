# Shared-queue release dependency repair plan

Status: IN PROGRESS. Governing scope is the matching November1 specification.
This is a necessary release-gate repair; no production deployment has occurred.

1. Preserve the two failed audit logs and current lock entries. Resolve the
   patched follow-redirects entry with npm in an owned temporary directory; adopt
   only that entry. Change only pyasn10.6.4 to0.6.5 in the production lock.
2. Verify exact file/node differences, published artifact integrity, installed
   versions and strict production audits. Run existing auth regressions with the
   patched pyasn1, frontend tests/type/lint/build with fresh locked dependencies,
   and compare output hashes to the qualified Preview. Do not alter tests.
3. Commit only the two locks and this spec/plan after the available package,
   integrity and auth checks, so exact-head Linux CI can run while lengthy local
   frontend/audit checks continue. Pending checks are not passes. Retain the
   existing release branch and normal push history, create a corrective PR to
   current main4d4e8eac; require all11 exact-head CI jobs and new hosted Preview.
4. Reuse the fresh isolated recovery/offhost evidence while within the24-hour
   requirement; qualify the patched backend dependency separately. Merge only
   after required gates pass, require all11 new main CI checks and tree equality.
5. Deploy exact verified main to existing Render first, then existing Pages;
   automatic deployment settings, signing bindings and migration-free startup
   remain fixed. Verify actual public behavior and artifacts, record limits and
   preserve the qualified/open SEED-001 finding.

Executed local evidence at candidate preparation: npm production audit reports
zero vulnerabilities; npm resolution changed exactly follow-redirects1.16.2;
official PyPI wheel checksum matches;36 auth regressions and independent DER
roundtrip pass on verified pyasn1 0.6.5. Full frontend validation is running.
Native Windows strict pip audit fails on Linux-only uvloop; WSL lacks venv support.
The unchanged strict audit is running in a disposable cached production-base
Linux container. No scanner flags or production gates have been weakened.

Permitted tracked files: frontend/package-lock.json, requirements-production.lock,
and the matching November1 spec/plan. The working README is explicitly unowned and
excluded. Protected source paths must remain byte-for-byte unchanged.
