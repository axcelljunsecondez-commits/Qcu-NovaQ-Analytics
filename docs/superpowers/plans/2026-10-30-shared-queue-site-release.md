# Shared-queue workflow release to novaq.site

Owner authorization: “proceed this until the we can release this into novaq.site”.
Date: 2026-10-30. Status: IN PROGRESS; no production GO yet.

Verified starting feature head c767731bf3c4b5c98ea32f5439b11d73382993af;
fresh GitHub main 3ee8fe2c5d3f1521e37255959f2383e67e374b4c. Release branch:
codex/release-shared-queue-20261030. Existing feature/main/worktrees retained.

## Scope and protected boundaries

Release the approved shared plan-selection repair, full-day visual replay and
automatic repetition controls, aggregate planning upload, and relocation of model
choices to Simulation Advanced. Existing project-agent records are non-runtime
documentation in the approved local history. Review the exact main-to-candidate
diff before publishing. Preserve source data, calculations, simulation algorithms,
statistical definitions, auth, API signing bridge, dependency declarations and
database schema. No migrations, seeding or credential/configuration changes.

One prerequisite source repair is authorized by release preparation: annotate the
two existing current/suggested plan names as `tuple[Plan, Plan]` in the continuous
compatibility adapter and reuse the unchanged comprehension. This fixes the
existing mypy str/Literal mismatch without changing names, order, assessments or
response shape. Existing API tests must pass; do not weaken expectations.

## Gates and execution

1. Record candidate scope and type-only correction; run scoped API regressions
   and source typing/lint. Check clean committed sources separately from old
   untracked output artifacts. Preserve the 817-test frontend evidence only while
   its source subtree is unchanged.
2. Verify current Render and Pages identities, deploy controls, build/start
   commands and rollback references. Automatic deploys/previews remain disabled.
   Reuse configured credentials only in process memory; never print/save secrets.
3. Commit reviewed changes, seal a clean Git build context, push the release
   branch and create a scoped PR. Require all configured jobs on its exact head,
   including audits, coverage, PostgreSQL and image scans. Fix actual failures
   within scope; stop for protected-math or unapproved changes.
4. Build a manual Pages Preview from the pinned branch while preserving bindings
   and settings. Verify actual source/artifact hashes and changed UI, with any
   synthetic fixtures explicitly identified. Preview's absent production signing
   secret is a documented limit, never a reason to copy that secret.
5. Prepare fresh production backup/recovery evidence for the backend update,
   using existing encrypted backup configuration and an owned isolated restore.
   Local Docker evidence is not production backup proof. Retain current provider
   deployment IDs for recovery; do not claim operational rollback executed.
6. Recheck PR/main heads and provider controls; merge only after exact-head gates
   pass, and require main CI plus reviewed-tree equality. Deploy the compatible
   API before the new frontend, with no migration/seeding or configuration change.
   Publish Pages manually from exact tested main; commit metadata alone is not
   artifact proof. Retain existing public hostname and project/service.
7. Verify actual production source/build, health/readiness, auth refusals, served
   artifacts and changed workflow within the authorized diagnostic scope. Preserve
   existing operational records. Record actual results, remaining limitations and
   final controls; never label local/Preview results as production execution.

The existing SEED-001/selected-load statistical limitation remains open under its
previous qualified-release acceptance; this shared-queue release cannot silently
claim to repair it. Final production GO requires all applicable gates to pass.

## Prerequisite verification (executed)

The type-only correction passes source mypy (235 files), source Ruff, and 103
existing compatibility/upload/foundation API regressions. The frontend subtree is
unchanged from the 817-test verified source. Current provider observations match
main 3ee8fe2c: Pages production fa285283-e53d-4109-9abd-9b4898f63757 and Render Live
dep-dbgok78n74is73d1jaag. Pages production auto-deploy false / preview none; Render
Auto-Deploy Off / PR Previews Off. Build/start commands remain migration-free.
The production signing binding remains secret_text; Preview has no signing secret.
These observations do not establish candidate CI, production backup or release GO.

## Exact secret-scan metadata findings

The first PR CI run passed lint/types/dependency audit but Gitleaks reported four
generic-api-key findings. Two are the test-file SHA-256 values in the reviewed
source JSON; both reproduce from the named current file and Git blob. Two are
Docker container identities in activation reports; they match retained runtime
records. No credential was found or rotated.

Use the repository's existing exact-fingerprint mechanism for only these four
immutable findings, following the upstream Gitleaks documentation. Do not exclude
paths, rules, commits as a whole, or future findings. Preserve the existing entry.
Run the pinned scanner against the release range and verify that a new synthetic
credential-shaped probe is still detected. Require renewed exact-head CI before
any merge or publication. No application, tests, algorithms or history rewrite.

Owner explicitly approved these four metadata exceptions. Executed with the same
Gitleaks 8.24.3 as CI, verified against its official archive checksum: release-range
scan passed (exit0); a new synthetic credential was detected (exit1, one finding).
No files/rules were excluded. Renew CI on the metadata-only corrective commit.
