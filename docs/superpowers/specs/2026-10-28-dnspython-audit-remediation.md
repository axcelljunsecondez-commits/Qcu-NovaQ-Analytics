# Proven dependency-audit defect during tooltip release

## VERIFIED defect and references

PR 39 CI run `40577444835`, lint job `122447548132`, head `039c153f06fc4500331029abde7e5755f78219cc`: Ruff passed; `pip-audit -r requirements-production.lock --strict` failed on `dnspython==2.8.0`, CVE-2026-114605, fixed version 2.9.0. Dependent Python matrix/image jobs were skipped, not passed. Publication is held until replacement exact-head CI passes.

The [maintainer advisory](https://github.com/rthalley/dnspython/security/advisories/GHSA-45c3-73f7-pv4m), [reviewed advisory](https://github.com/advisories/GHSA-45c3-73f7-pv4m), [maintainer release notes](https://dnspython.readthedocs.io/en/stable/whatsnew.html) and [PyPI release metadata](https://pypi.org/project/dnspython/2.9.0/) establish affected versions below 2.9.0, the CPU-exhaustion correction, and Python >=3.11 for 2.9.0. The existing production Dockerfile already targets Python 3.11.16. No direct dns.* application calls were found; transitive exposure and the actual deployed package version are not certified by that search.

## Scope and plan

This is the separately proven dependency defect allowed by `2026-09-14-api-image-vulnerability-remediation.md`; the older base-image-only task did not authorize arbitrary dependency churn. The current owner's deployment request requires clearing the existing unsuppressed release gate. Apply the smallest source-pin correction, with this explicit defect record, as necessary release repair. No approval to deploy or restart the backend is inferred.

1. Change only `dnspython==2.8.0` to `dnspython==2.9.0` in the production lock. Preserve every other pin, the scientific stack, Python targets, dependency declarations, source modules, authentication/API contracts, database schema, signing bridge and CI policies.
2. Download the maintainer's PyPI wheel, verify its published SHA-256, and run an isolated/no-network probe on the existing Python 3.11 API image. Compare the old/new DNS compression-chain behavior with a bounded 20-pointer fixture; verify normal DNS wire round-trip, email validation, Pydantic EmailStr and API imports. Do not mount application data or inject credentials.
3. Require renewed exact-head CI, including strict pip audit, pip check/image construction, unsuppressed image scanning, supported Python regressions, PostgreSQL, stack recovery, frontend, preflight and secret scan. Do not add ignore IDs or weaken checks. Keep the failed original run as evidence.
4. The frontend subtree must remain byte-identical to the pinned tooltip candidate; reuse its raw-Git build only after verifying subtree identity. Update the PR around the actual final scope.
5. Keep local Docker/Render API images and databases unchanged. A successful frontend publication does not install this dependency into a running backend. Deployment of the patched backend is a separate follow-up; actual live package version and reachability are NOT TESTED here. Do not claim that a green source audit fixes the live backend.

Allowed source scope: the one production-lock pin, this defect record, the existing frontend release plan, and a verification report after execution. No application implementation, tests, migrations, Dockerfile, environment/configuration or mathematical change is part of this correction.

Status: implementation/isolated validation required; this specification is not proof that those gates have passed.
