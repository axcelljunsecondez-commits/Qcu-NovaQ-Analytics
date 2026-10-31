# Dependency audit repair for the shared-queue release

The owner authorized completing the gated release to novaq.site. PR40 merged as
4d4e8eac46f4a042d2e64785519fcf4a9ef724fb; production remains3ee8fe2c. The exact
main CI41238134386 now fails production dependency audits which passed in the
earlier PR run. Deployment is stopped until those real findings are repaired.

VERIFIED findings: npm flags follow-redirects1.16.1 (GHSA-mrwp-f3q8-3g9p), patched
in1.16.2. pip-audit flags pyasn1 0.6.4 (CVE-2026-119194/119195/119196/119197), all
patched in0.6.5. The primary GitHub advisories and official PyPI0.6.5 release were
inspected. These findings establish affected dependency versions; NovaQ-specific
exploitability is NOT TESTED and is not asserted.

PROPOSED repair: update only the resolved follow-redirects lock entry and the
production pyasn1 pin to those published patched versions. Keep parent dependency
declarations, all other resolved dependencies, runtime source, queueing mathematics,
simulation/statistics, API shapes, schema, auth settings and signing bridge intact.
No audit ignore, severity threshold change, scanner exception or broad audit fix.

Expected outcome: strict production npm/pip audits pass with the two patched
packages; existing behavioral/type/build checks pass; independent artifact
comparison establishes whether browser output changed. Complete new exact-head
PR/Preview and main CI gates before backend-first/frontend publication. Preserve
the owner's separate frontend/README.md edit and every unrelated untracked file.

Sources:
- https://github.com/advisories/GHSA-mrwp-f3q8-3g9p
- https://github.com/advisories/GHSA-2qm8-x737-gmw5
- https://github.com/advisories/GHSA-fm9c-5rcf-2q5p
- https://github.com/advisories/GHSA-9m75-vc3g-4x39
- https://github.com/advisories/GHSA-mm57-4v3p-rchx
- https://pypi.org/project/pyasn1/0.6.5/
