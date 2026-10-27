# Dependency audit remediation — isolated verification

VERIFIED: the original PR 39 head `039c153f06fc4500331029abde7e5755f78219cc` failed strict pip-audit on dnspython 2.8.0 / CVE-2026-114605. The production lock changes exactly that pin to 2.9.0; no application module, mathematical behavior, contract, schema, Dockerfile or CI policy changes.

VERIFIED: the official PyPI wheel SHA-256 is `9a4aedb833c3c1b49214d04d44d3032ab7a9135f7c1d29a549b4ff78fd82fda9`, checked against downloaded bytes. Its Python >=3.11 requirement matches the existing Python 3.11.16 API image. Two temporary read-only, network-disabled containers, with no data/credential mounts, compared the existing 2.8.0 package and mounted 2.9.0 wheel. Both passed normal DNS wire round-trip, offline email validation, Pydantic EmailStr and `backend.api.main` import. The bounded 20-compression-pointer fixture was accepted by 2.8.0 and rejected by 2.9.0. Running API, web and database containers were not replaced by this probe.

The first private probe invocation failed because its `/probe.py` script did not place `/app` on sys.path. That harness failure is retained; explicitly setting PYTHONPATH corrected the harness before the two successful comparisons. It was not an application defect.

VERIFIED: the frontend subtree remains identical to the original tooltip candidate. Private primary evidence: `tooltip-release-20261028/dns-security-probe.json`, both versioned logs, and retained harness-failure log under the task visualization directory. The existing raw-Git frontend build remains applicable only through this verified subtree identity.

NOT TESTED at this report commit: replacement exact-head CI, hosted Preview and production release. They remain required gates. Running Render/local API images are preserved; this source-pin correction does not patch a deployed backend. Live transitive reachability and deployed package version are not certified here. No production database operation, migration, seeding or credential/configuration change occurred.
