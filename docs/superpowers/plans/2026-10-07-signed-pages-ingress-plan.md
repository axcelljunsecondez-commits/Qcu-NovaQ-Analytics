# Signed Pages ingress: plan (2026-10-07)

Status: **RELEASED 2026-10-07 12:05 UTC** (owner: "start the ingress window"); see the release window record below. This
replaces the GO packet §3 exception "Direct `onrender.com` URL bypasses
Cloudflare" with planned work, as the owner decided on 2026-10-06.

## Problem (VERIFIED 2026-10-06)

- The Render backend is reachable directly at
  `https://qcu-novaq-analytics.onrender.com`, bypassing the novaq.site Pages
  bridge. CORS, CSRF and auth still apply.
- Render sits behind Cloudflare. Its app-level peer is a local `127.0.0.1`
  proxy behind Render `10.x` hops (GO packet §6, follow-up row). No
  `FORWARDED_ALLOW_IPS` value yields the end user's IP.
  - Logged-out rate limits are therefore keyed per Render hop and shared by
    all users.
  - The bridge forwards no client IP: `frontend/functions/api/[[path]].ts`
    has a fixed header allow-list.

## Existing design to port (excluded from G-A, branch `ci/verify-fcbc8db1`)

`1fbe812c` "Add signed Pages ingress for Render", on top of `81bc427a` and
`6ef85712`:
- Files:
  - `backend/api/proxy_assertion.py` (new);
  - `backend/api/settings.py`, with `NOVAQ_PROXY_MODE=pages_signed`,
    `NOVAQ_PROXY_ASSERTION_SECRET` and `NOVAQ_PROXY_ASSERTION_PREVIOUS_SECRET`;
  - `backend/api/rate_limit.py` and `main.py`;
  - `frontend/functions/api/[[path]].ts`;
  - `docs/operations.md`;
  - tests (`tests/test_proxy_assertion.py`, `apiProxy.test.ts`).
- Contract, from that commit's `docs/operations.md`:
  - The Pages Function signs v1 HMAC-SHA256 over the version, Unix time, a
    32-hex nonce, the client IP taken from `CF-Connecting-IP`, the method and
    the path plus query.
  - The backend rejects requests that are missing, malformed or unknown-key,
    older than 60 s, more than 5 s in the future, or replayed (in-memory nonce
    cache, 10,000 entries, fail-closed).
  - `/health`, `/ready` and OPTIONS are exempt.
  - Rate limits use the verified signed IP.
  - The Start Command adds `--workers 1 --no-proxy-headers`.
  - Secret rotation uses a previous-secret overlap.
- `1fbe812c` CI run 37033297305 passed. It was never reviewed for release.

## Facts to establish before implementation (UNKNOWN today)

1. Whether `1fbe812c`'s code depends on the client-version fence `81bc427a`.
   `81bc427a` is a git ancestor of `1fbe812c` (VERIFIED); the code dependency
   is UNKNOWN. The fence changes `http.ts`, `router.tsx` and API behaviour, so
   it is a separate product decision.
2. What value `NOVAQ_PROXY_ASSERTION_SECRET` holds today. The key exists among
   Render's 17 env keys; its value was never read. Also whether Pages holds a
   matching secret (Pages lists one encrypted secret of unverified name).
3. Render instance count, and its zero-downtime replacement behaviour. Nonce
   memory is per process, as the commit documents.
4. Whether UptimeRobot (`/api/ready`) and Render's own health probes stay on
   exempt routes. Expected yes.

## Findings from the probe port (2026-10-07, VERIFIED)

Method: `1fbe812c` alone was cherry-picked onto `main` `07f73b6f` in a
throwaway worktree (`.claude/worktrees/ingress-probe`, detached, nothing
committed).

- **Fact 1 settled: no code dependency on the fence.** All code files apply
  cleanly. The only conflicts are in tests: the `import` line of
  `tests/test_production_hardening.py`, and two fence-only tests in
  `apiProxy.test.ts` (client-protocol header passthrough, fence 403 body). With
  those two tests dropped:
  - backend `test_proxy_assertion.py` 28, `test_production_hardening.py` 21 and
    `test_api_event_logging.py` 5 pass (54);
  - `apiProxy.test.ts` 14 pass;
  - `npm run typecheck`, `npm run lint`, `ruff check backend tests` and mypy on
    the four backend files are clean.
  - `test_proxy_assertion.py` still sends the fence's `X-NovaQ-Client-Protocol`
    header, which `main` ignores; a port should remove it.
  - Full suites and CI were NOT run on the probe.
- **The Pages Function fails closed.** Without a valid
  `NOVAQ_PROXY_ASSERTION_SECRET` (43-char base64url, 32 bytes), every `/api`
  call returns 500 `proxy_secret_unconfigured`; without `CF-Connecting-IP` it
  returns 403. So the Pages secret must be set **before** the Pages deploy (step 4).
- **Rate-limit keying changes in both modes.** Today logged-in requests are
  keyed per session-cookie hash, others per TCP peer. `1fbe812c` drops the
  cookie key everywhere ("a raw cookie is never identity": a forged cookie gets
  a fresh bucket). In `pages_signed` mode the key is the verified client IP.
  In `direct` mode, which is the rollback setting, every user would share the
  TCP-peer key (Render `10.x` hops) for compute (30/min), report (10/min),
  upload, admin and auth limits. Rollback would therefore not equal today's
  behaviour unless the port keeps the session key in `direct` mode.
- **Redirect handling is hardened too.** The bridge now returns 502
  `api_redirect_rejected` for any API redirect off the API host (today it passes
  external redirects through unchanged).
- **The production validator relaxes `FORWARDED_ALLOW_IPS`** only in
  `pages_signed` mode.
- Facts 2–4, read from the dashboards 2026-10-07 (names only, no values):
  - Pages `novaq-frontend` has two variables: `NOVAQ_API_ORIGIN` (text) and
    `NOVAQ_PROXY_ASSERTION_SECRET` (encrypted secret). Render also has a
    `NOVAQ_PROXY_ASSERTION_SECRET` key. Whether the two values match, or are
    valid 32-byte base64url, is UNKNOWN; step 3 replaces both with a fresh secret.
  - Render service: Free plan; no Scaling section is offered, so one instance
    (INFERRED from the plan); Health Check Path is empty, so Render sends no
    HTTP health checks; Start Command
    `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --no-access-log`.
  - UptimeRobot checks `https://novaq.site/api/ready` through the bridge, so it
    is signed; `/ready` is exempt anyway.

## Owner decisions (2026-10-07)

1. Port `1fbe812c` **without** the client-version fence (`81bc427a`, `6ef85712`).
2. `direct` mode keeps the pre-ingress rate-limit keys (session cookie when
   sent, otherwise the client address), so rollback restores today's
   behaviour exactly; `pages_signed` keys on the verified client IP as designed.
3. Step 2 authorized: port on its own branch, full gates, local commit only.
   Push, CI, secret creation and the release window each need a separate OK.

## Port (step 2) on branch `feat/signed-pages-ingress`

`1fbe812c` cherry-picked onto `main` `07f73b6f`, with these adaptations:
- `backend/api/rate_limit.py`: the `direct` branch is the pre-ingress code
  unchanged (decision 2).
- `tests/test_proxy_assertion.py`: the fence header is removed; the
  direct-mode test now pins the pre-ingress keys (a cookie-blind mutant fails it).
- `frontend/src/cloudflare/apiProxy.test.ts`: the two fence-only tests are dropped.
- `docs/operations.md`: rate limits described per mode; the fence sentence
  removed; the Start Command keeps `--no-access-log`:
  `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log`.

Gates on the port (2026-10-07, Windows, Python 3.13.13 with the release
requirements, Node from the existing frontend install):
- `python -m pytest tests/ -x`: 1615 passed, 118 skipped, 1 xfailed.
- `ruff check .` clean; `mypy .` no issues in 169 files.
- Frontend: vitest 53 files / 392 tests, `typecheck`, `lint`, `build` all pass.
- Not run: PostgreSQL-backed tests (no `NOVAQ_TEST_DATABASE_URL`) and GitHub CI.

## Proposed steps (each needs owner authorization)

1. Spec: decide fence in or out, and confirm the contract above.
2. Port `1fbe812c` (with or without `81bc427a`) onto `main` on its own branch.
   Run the full backend and frontend gates and CI.
3. Generate a fresh 32-byte base64url secret. The owner sets it in Render and
   Pages; it never goes into Git or chat.
4. Release window:
   - deploy the Pages Function first, so it signs while the backend ignores
     the signature;
   - then deploy the backend with `NOVAQ_PROXY_MODE=pages_signed` and the new
     Start Command.
5. Verify:
   - novaq.site login and Analysis smoke test;
   - direct `onrender.com` API calls return the assertion refusal (not 200);
   - `/ready` stays 200;
   - logs show per-user client IPs and no 5xx.
6. Remove `FORWARDED_ALLOW_IPS=127.0.0.1` if it becomes irrelevant under
   `--no-proxy-headers`, and close this exception.

## Release window (2026-10-07)

Owner: "start the ingress window". All times UTC.

| Step | Outcome | Evidence |
| --- | --- | --- |
| Baseline 11:28 | Recorded | Render live `0ddefa6`; Pages bundle `index-jBXJZ6bl.js` (`a4f60c31`); `/ready` and `/auth/config` 200 through novaq.site **and** directly on `onrender.com` |
| CI | PASS | PR #27 (draft, CI only) run 37610684526 on `38fa998`: Success, 11/11 jobs including postgres-integration |
| 1–2 secrets | DONE (owner) | Fresh 32-byte secret generated into the clipboard, set as `NOVAQ_PROXY_ASSERTION_SECRET` in Pages (secret) and Render (Save only); values never shown. 11:29: no Render deploy, site 200. Render lists 18 env keys; the 17 recorded on 2026-10-06 missed `RESULT_JSONB_MAX_BYTES` (absent from the 2026-10-01 audit list, added since; when is UNKNOWN). The owner REPORTED editing only the secret. Its value `786432` (owner-read) is within 1024–10485760 |
| 3 merge | DONE | Render auto-deploy/PR previews Off and Pages Disabled re-read; `main` fast-forwarded to the CI-tested `38fa998a`; GitHub marks PR #27 Merged; Pages recorded `main · 38fa998` as "No deployment available" |
| 4 Pages | DONE 11:59 | Retrying `main · 38fa998` built three **Preview** deployments of `feat/signed-pages-ingress` (`d6fd9c60`, `9c3c672b`, `26d52bfd`; INFERRED cause: Pages first saw that commit on the branch). Production stayed `574e1a9`, novaq.site `/api` 200. Fix: with automatic deployments on (owner), the docs-only commit `1c8e8dee` was pushed to `main` (Render Off/Off re-read first); Pages built Production `b7ac08c8` (`main · 1c8e8de`). 11:59: `/api/ready` and `/api/auth/config` 200 (the new bridge found a valid secret; without one it returns 500), `/api/auth/me` 401, no `X-NovaQ-Proxy-*` header in responses, bundle unchanged `index-jBXJZ6bl.js`. Automatic deployments: owner REPORTED off; read back **Disabled** after step 6 |
| 5 Render | DONE 12:05 | Owner added `NOVAQ_PROXY_MODE=pages_signed` (Save only; value not read back, behaviour below), set the Start Command and Manual-Deployed `1c8e8de` as `dep-db33ac0m7kps73csnpa0`. Deploy log: `==> Running 'uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log'`, `Application startup complete`, "Your service is live", no errors. An external poll every ~20 s saw direct `onrender.com/auth/config` switch from 200 to 403 at 12:05:58 while novaq.site `/api` stayed 200 throughout |
| 6 Verify | PASS 12:06–12:08 | Direct `onrender.com`: `GET /auth/config`, `POST /auth/login`, `GET /auth/me` → 403 `proxy_assertion_required`, also with forged `X-NovaQ-Proxy-*` headers and a fake `X-Forwarded-For`; `/health`, `/ready` and the CORS preflight 200 (exempt); `HEAD /ready` 405 as before (GET-only route). Through novaq.site: `/api/ready` and `/api/auth/config` 200, a bad `POST /api/auth/login` → 401 `invalid_credentials` (signed POSTs reach the app). Owner session in Render logs (user 4): Analyses 6 and 11, optimize separate and breaks, selection, comparison, report preview and PDF, logout — all 200, no 5xx, no assertion refusals. NOT VERIFIED in production: per-client-IP rate-limit keys, because `event=http_request` lines carry no client IP (covered by `test_proxy_assertion.py` and CI) |

Open after the window:
- Step 6 DONE 12:25–12:28 UTC at the owner's request: `FORWARDED_ALLOW_IPS` removed on Render (Save only) and `1c8e8de` redeployed as `dep-db33kc2d0e5s73f0rf2g` (same Start Command, startup complete, live 12:27). Render lists 18 keys without it. A ~20 s external poll through the redeploy saw novaq.site `/api` 200 and direct `/auth/config` 403 throughout; at 12:29 a direct request with a fake `X-Forwarded-For` was still 403. A rollback to `direct` must re-add `FORWARDED_ALLOW_IPS=127.0.0.1`.
- The three stray Preview deployments can stay; they are not served on novaq.site.
- Cleanup 2026-10-07: the `ingress-probe` worktree was removed (its `node_modules` junction first, so the target in `port-g-a-stage1` stayed intact) and the branch `feat/signed-pages-ingress` was deleted locally and on GitHub. It held no commits beyond `main` (`0480c06e`); PR #27 remains Merged.

## Rollback

- Since step 6, rolling back to `direct` also requires re-adding
  `FORWARDED_ALLOW_IPS=127.0.0.1` on Render; `direct` refuses Render's injected value.

- Backend: set `NOVAQ_PROXY_MODE=direct`, `1fbe812c`'s default (VERIFIED,
  `settings.py:128`), and restore the Start Command. Alternatively, redeploy
  the pre-ingress backend commit `0ddefa6` (it has no proxy mode).
- Pages: roll back to the previous Pages deployment.
- No database change is involved.
