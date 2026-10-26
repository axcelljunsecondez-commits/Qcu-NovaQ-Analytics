# Homepage and Help release preparation

## Authorization and scope

The owner requested progress toward release on `novaq.site` after review of the local homepage/Help feature. Prepare a concrete candidate commit, feature-branch push, draft PR/CI and manual Pages preview. Do not push main, merge, change production settings or publish production before the final candidate and release conditions are reviewable.

Implementation spec: `../specs/2026-10-27-homepage-queueing-101.md`.
Local validation: `../reports/2026-10-27-homepage-queueing-101.md`.

This candidate changes frontend presentation, lessons, static assets, translations and their tests/docs only. Preserve the API, queueing mathematics, database, signing bridge, CSP, dependency versions and service settings. Backend/database migrations, seeding, SQL, Render changes and copying production credentials into Preview are outside this release scope.

## Verified starting state

- Local branch `codex/homepage-queueing-101`, base `bb585a45faf8845007e8eea7afe7c8f40ec06435`.
- Refreshed origin/main matches that base.
- Cloudflare account/project were read through the connected API. Existing Pages project: `novaq-frontend`, Git repository `axcelljunsecondez-commits/Qcu-NovaQ-Analytics`, root `frontend`, build `npm run build`, output `dist`.
- Current production Pages deployment: `394e20e2-620f-4868-b972-1435d3675ac2`, source `bb585a45faf8845007e8eea7afe7c8f40ec06435`, environment production, successful deploy stage.
- `production_deployments_enabled=false`, Preview setting `none`; retain these values.
- Preview and Production point to the existing Render API. Production has the signing-secret binding; Preview does not. No secret value was printed or copied.

These observations are a timestamped starting point, not proof that a later candidate is deployed.

## Execution sequence

1. Review the complete allowed file list/diff and media hashes; confirm protected paths and dependency manifests remain unchanged. Commit the verified candidate and record its actual SHA.
2. Push only the feature branch. Open a draft PR to main and attach it to this task. Read exact-head CI, including native PostgreSQL and isolated stack checks. Stop release progress on any unexplained failed required check; diagnose without weakening the gate.
3. Request a Pages deployment explicitly from the feature branch. Confirm returned environment is `preview` and its commit equals the pinned candidate. Do not enable automatic deployments or change production/preview environment settings.
4. Verify HTTPS static assets/MIME/byte hashes, complete video playback/seek, captions/downloads, Home/Help routing and search, EN/TL and themes, mobile/desktop layout, reduced motion, no-jump transitions, full-size queue diagrams and browser script/CSP errors.
5. Record the actual Preview API behavior separately. Because the signing binding is absent, backend-dependent Preview checks may be blocked. Do not claim a complete sign-in workflow or add a production secret to make this appear tested. Local signed-in/navigation tests and CI are separate evidence.
6. Re-read the production deployment and settings to confirm they were not changed during preparation. Assemble exact candidate/PR/CI/preview URLs, failures/limits, rollback target and a narrowly scoped frontend-only production proposal for owner review.

## Release gates and recovery

- Exact candidate/head/tree, scoped diff, media hashes and applicable local gates established.
- Required exact-head CI successful; no skipped or failed gate described as passed.
- Hosted Preview static feature checks successful; authentication limits explicitly identified.
- Existing production frontend/API health checked separately; current deployment/settings match the recorded starting state.
- No whole-system mathematical correctness claim: the known seed-sensitive Decision finding and any unexecuted coverage remain disclosed.
- For a frontend-only release, recovery is a Pages rollback to the recorded previous production deployment, with API/database unchanged. Database backup/restore and migration gates apply if that scope changes; this plan authorizes no such change. Preview proof is not a tested production rollback.
- Final production action requires a concrete reviewed candidate and explicit release authorization; no production action is performed by this preparation plan.

Candidate SHA, CI run IDs, Preview deployment and readiness status are UNKNOWN until the corresponding commands/API responses establish them. Save the resulting evidence and release packet outside the Git worktree to avoid self-referential candidate-SHA documentation commits.
