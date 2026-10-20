# Archived analysis workspace selector

Date: 2026-10-19 (Asia/Shanghai).

Owner scope: close remaining verification items and report remaining status. This is a bounded correction to the already approved responsive overview's accurate analysis context requirement, discovered during its required archived-access verification.

## Verified defect

The isolated browser fixture has own active analysis 1 and own archived analysis 2. At `/analyses/2/data`, the context title correctly names archived analysis 2, but `#analysis-switcher` shows active analysis 1. The API's default list excludes archived analyses. `AnalysisWorkspace.tsx` passes only that list to a controlled select whose value is 2; the DOM falls back to its first option because option 2 is absent. Foreign/missing accesses are refused separately and are not inclusion candidates.

## Required behavior

After the current analysis has successfully loaded through the existing authorized API, include it in the workspace selector when it is absent from the default list. Do not duplicate it when already listed. The selected name/value, active context and route must agree. Keep other archived/foreign records excluded and preserve navigation handlers, page suffix and transient child-state reset.

## Scope and verification

- Application scope: `frontend/src/components/analysis/AnalysisWorkspace.tsx` and its existing test file only.
- No API, ownership, archive/write policy, mathematical/statistical behavior, labels, translation keys or data changes.
- Reproduce the missing-option case with a regression for archived and temporarily absent current records, then run affected tests, the full frontend suite, typecheck and lint.
- Source/build status must stay distinct. A build/rebuild and runtime activation require the owner's requested approval; do not claim the deployed defect fixed before an approved build/activation and browser recheck.
- The reproduced seed-sensitive Decision defect remains open. This correction does not resolve or authorize changes to it.
