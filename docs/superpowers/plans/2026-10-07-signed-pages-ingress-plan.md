# Signed Pages ingress: plan (PROPOSED, 2026-10-07)

Status: **PROPOSED**. Not authorized for implementation or release. This
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

## Rollback

- Backend: set `NOVAQ_PROXY_MODE=direct`, `1fbe812c`'s default (VERIFIED,
  `settings.py:128`), and restore the Start Command. Alternatively, redeploy
  the previous backend commit; current `main` has no proxy mode.
- Pages: roll back to the previous Pages deployment.
- No database change is involved.
