# Vongola Family V2 — implementation and verification report

Date: 2026-11-01, Asia/Shanghai. **Status: PARTIAL.** Configuration and controlled
fallback workflow are implemented and independently reviewed. Full native operation
on both platforms is **INCONCLUSIVE / NOT TESTED**, for the reasons below.

## A. Initial Repository Findings

**VERIFIED:** root `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`,
branch `codex/repository-cleanup-20261101`, HEAD
`07f97848a1844e228bc229f11f5faa3d81f6fa11`. No branch/HEAD change occurred.
The initial tree had one tracked edit, `frontend/README.md`, and 18,058 untracked
files. They were preserved; no cleanup, staging, commit, push, merge or deployment
was performed. This report concerns this checkout, not other worktrees or production.

**VERIFIED inventory:**

- `AGENTS.md`, `memory.md`, `handoff.md` and the previous October 29 roster
  spec/plan/review supplied project context. Previous records were treated as leads.
- `CLAUDE.md` already imported `@AGENTS.md`; it needed no change.
- Claude names were `chrome`, `hayato`, `kyoya`, in `novaq-growth-designer.md`,
  `novaq-backend.md`, `kyoya.md`. Chrome used Opus without project memory;
  Hayato/Kyoya inherited the model and used project memory. Their existing tool
  lists included Bash; a prior Kyoya command-access failure's original cause was
  not established by those declarations. No current project-local Codex agents,
  config or V2 contract existed in the inspected inventory.
- `.claude/settings.json` was absent. Ignored `.claude/settings.local.json` existed
  with 27 allow entries; its contents were preserved. Existing design skills under
  `.agents/skills/`, CI configuration and untracked `.claude/launch.json` were left
  alone. No existing project hook was found in the inspected Claude configuration.
- Installed CLI: `codex-cli 0.166.0-alpha.5.1`. Python 3.13.13 and existing PyYAML
  6.0.3 were available. `where.exe claude` exited 1: Claude is unavailable on PATH;
  its installed version is **UNKNOWN**. No tools/accounts were installed/changed.
- Current chat offered default/explorer/worker and the wording reviewer, with
  command access. Native Hayato invocation returned `unknown agent_type 'hayato'`.
  A fresh CLI prompt later discovered all three new native declarations.

## B. Dual-Platform Implementation

The approved [specification](../specs/2026-11-01-vongola-family-v2.md) and
[plan](../plans/2026-11-01-vongola-family-v2.md) define the exact edit scope.

| Files | Actual change |
| --- | --- |
| `AGENTS.md` | Added canonical V2 roles, five stages, preflight, handoffs, verdicts, risk levels, reviewer fallback, two-cycle escalation and enforcement limits. The original engineering instructions remain intact. |
| `docs/agents/chrome.md`, `hayato.md`, `kyoya.md` | Shared specialist references migrated from the previous prompts. Retained design/wording/chart, backend/context and independent audit expertise. Resolved Chrome implementation language and frontend correction routing; marked historical source claims for rechecking. |
| `.claude/agents/chrome.md`, `hayato.md`, `kyoya.md` | Thin native adapters reading the canonical contract and shared role reference. Retained Chrome Opus and Hayato/Kyoya inherited model/project-memory settings. Chrome has explicit investigation tools and plan mode. |
| `.claude/agents/novaq-growth-designer.md`, `novaq-backend.md` | Removed replaced declarations so each native name appears once. Historical records/memories retain their original filename references; the current adapters/reference paths above supersede those navigation hints. |
| `.claude/settings.json` | Added secret-path denials and mutation/service-command approval patterns for Bash and PowerShell. No allow rules or global permission changes were added. |
| `.codex/config.toml` | Enabled agents; inherited parent model, sandbox, approvals and managed requirements. |
| `.codex/agents/{chrome,hayato,kyoya}.toml` | Native names/descriptions/instructions; shared references; app/plugin capability reductions. Shell retained for Git/tests. No hardcoded Codex model or unsupported per-agent sandbox override. |
| `.codex/rules/vongola.rules` | Restrictive approval rules for matched Git mutations, destructive command prefixes and deployment/database/service tools. No allow rules. |
| `scripts/check_vongola.py` | Offline TOML/YAML/JSON/adapter checks and explicitly selected synthetic-fixture checks. Uses existing PyYAML; no dependency addition or model API. |
| `docs/agent-evals/vongola-v2/README.md`, `labels.py.txt`, `total.py.txt` | Small controlled assignments, requirements and seeded inputs outside application code. |
| This report, spec/plan; `output/vongola-v2-20261101/` | Reviewable scope, actual command outputs, baseline/preservation identities and disposable evaluation copies. |

**VERIFIED preservation:** 1,012 baseline tracked files were fingerprinted. Every
baseline tracked file outside the four intended governance/native-declaration paths
matches its baseline, including the unrelated README edit. All five existing agent
memory files match exactly. Every pre-existing untracked path still exists; no new
unrelated path was detected. Untracked-file contents were not exhaustively hashed.
No application/math/API/schema/data/runtime configuration changed.

The normalized original `AGENTS.md` equals the final file after removing only the
V2 insertion: SHA-256 `efa0ee5ba76ee67035af68f214b0f94322e0f99226464bfb0046b28a84f5f78a`.
Initial preservation code missed CRLF when locating that insertion; normalizing both
texts corrected the check, and the equal hashes are retained in `preservation.json`.

## C. Agent Behavior Comparison

| Agent | Inspected previous definition | New contract and actual evidence |
| --- | --- | --- |
| Chrome | Growth/frontend designer with implementation instructions and no capability preflight contract. | Investigation/planning role retaining design expertise; proposes scoped handoffs and does not edit application code. Explorer fallback reproduced case loss, identified the expression and handed off acceptance cases without edits. Native adherence remains unverified. |
| Hayato | Backend specialist with scope, evidence, ownership and resume discipline. | Authorized engineering implementation role retaining backend expertise, frontend design/wording constraints when assigned, actual-result handoff and no self-approval. Worker fallback changed one expression in an owned synthetic copy and passed 4/4 cases. |
| Kyoya | Independent security/code/boundary/evidence reviewer; Bash present in declaration, memory-only writes advisory. | Explicit preflight, verdicts and independent fallback contract. A separately identified default agent inspected actual source/diffs, executed checks and detected the seeded defect. Its review is not attributed to native Kyoya. |

## D. Six Improvement Results

| Improvement | Result and limits |
| --- | --- |
| 1. Capability preflight | **IMPLEMENTED; VERIFIED for fallbacks.** Source/Git/commands succeeded for explorer, worker and independent default reviewer; worker proved assigned-directory write access with a disposable marker. Native execution failure caused dependent work to stop, with no false handoff or PASS. Full native capability checks remain blocked. |
| 2. Structured handoffs | **IMPLEMENTED; VERIFIED in the fallback evaluation.** Chrome-role investigation → worker implementation → separate reviewer carried objective, evidence, exact files/hashes, actual checks, limits and bounded verdicts. No runtime synchronization framework. |
| 3. Permissions/safety | **PARTIAL.** Both native control formats are configured. Codex rule-engine matching was exercised; live end-to-end enforcement and Claude rule execution remain unverified. Advisory and unsupported coverage are separated below. |
| 4. Risk-based verification | **IMPLEMENTED; VERIFIED for this scope.** Source/configuration checks, meaningful positive/negative fixture controls, rule-engine tests, preservation and independent review were used. No application-wide suites for this nonfunctional task. |
| 5. Independent reviewer fallback | **IMPLEMENTED; VERIFIED for this change.** Actual default reviewer had source/Git/Python access and implemented none of the reviewed work. Original reported Kyoya access limitation's root cause remains **UNKNOWN**; current native failures do not establish that historical cause. |
| 6. Controlled evaluations | **IMPLEMENTED; VERIFIED for fallback roles and deterministic fixtures.** Native Codex evaluation was attempted and stopped INCONCLUSIVE. Claude runtime evaluations were NOT TESTED. No reliability/performance statistic is claimed. |

## E. Compatibility Matrix

“Discoverable” below means the fresh CLI's model-visible spawn-role declaration,
not successful execution. The running desktop chat's registry did not refresh.

| Platform/agent | Configured/static parsed | Native discoverable | Native invocable/executed role test |
| --- | --- | --- | --- |
| Codex Chrome | Yes | **VERIFIED**, fresh prompt | Attempted; **INCONCLUSIVE**, thread initialization failed |
| Codex Hayato | Yes | **VERIFIED**, fresh prompt | Current chat rejected the name; fresh runtime test NOT TESTED after Chrome prerequisite failed |
| Codex Kyoya | Yes | **VERIFIED**, fresh prompt | **NOT TESTED**; no additional native launch after host/runtime blockers |
| Claude Chrome | Yes, YAML/current-doc structure | **NOT TESTED** | **NOT TESTED**, CLI unavailable |
| Claude Hayato | Yes, YAML/current-doc structure | **NOT TESTED** | **NOT TESTED**, CLI unavailable |
| Claude Kyoya | Yes, YAML/current-doc structure | **NOT TESTED** | **NOT TESTED**, CLI unavailable |

**VERIFIED Codex observations:**

- `codex debug prompt-input` initially failed in the enclosing sandbox with Access
  denied. Running that local inspection with authorized host access exited 0:
  the prompt contains the V2 contract and all three native role descriptions.
  Evidence: `fresh-prompt.json`, summarized in `native-discovery.json`.
- `codex --strict-config app-server --print-startup-config` exited 1 on an existing
  global field, `computer_use.windows.always_allowed_app_ids`. It was not edited.
  Normal startup inspection exited 0. Strict debug prompt inspection itself is
  unsupported by the installed command and was retried without that flag.
- The fresh native family attempt used `codex -a never exec --ephemeral --sandbox
  workspace-write --json ...`, with no sandbox/approval bypass. Native Chrome spawn
  failed with `invalid thread-store request: no rollout found for thread id ...`.
  A context-read command also failed with `helper_sandbox_lock_failed` and
  `SetNamedSecurityInfoW sandbox dir failed: 5`. Their root cause is **UNKNOWN**;
  no global ACL/security workaround was applied. Hayato was not started.
- The parent CLI exited 0 but its final verdict was **INCONCLUSIVE**. Exit 0 is
  not treated as a native-agent evaluation PASS. Exact events/errors are retained
  in `native-family-events.jsonl` and `native-family-last.txt`.

## F. Permission Enforcement

| Safeguard | Classification and evidence |
| --- | --- |
| Codex command-prefix rule decisions | **ENFORCED AND TESTED within the rule evaluator only:** `execpolicy check` returned `prompt` for push/commit/add, Remove-Item, alembic upgrade and wrangler deploy; status had no matching rule. Those operations were never executed. |
| Automatic loading/live enforcement of project rules | **CONFIGURED BUT UNVERIFIED.** A fresh session needs trusted project config. These rules govern matched outside-sandbox approval decisions; they are not complete in-sandbox authorization or an OS security boundary. |
| Prefix coverage limits | **UNSUPPORTED by these patterns:** `git -C fixture push` and `pwsh -Command "git push"` had no matches in direct argv rule tests. Aliases, executable paths, indirect programs and other equivalents require separate review. No universal command firewall is claimed. |
| Codex app/plugin reductions | **CONFIGURED BUT UNVERIFIED:** supported native feature keys, not exercised inside a running native role. Shell remains available by configuration; role-specific read-only filesystem confinement is not provided by custom-agent instructions. |
| Claude secret/command rules | **CONFIGURED BUT UNVERIFIED:** exact `.env`, `.env.local`, `.env.production`, `.env.development`, `.env.test` names and secret/backup directories are denied for matching file tools; `.env.example` remains readable. Bash/PowerShell patterns ask for matched mutations/service tools. Arbitrary subprocess file access is not confined by these path rules. Existing local allow rules remain unchanged; effective runtime precedence was not exercised. |
| Claude Chrome tools/plan mode | **CONFIGURED BUT UNVERIFIED.** Parent modes can affect subagent mode. Hayato/Kyoya project memory may enable file tools; it does not enforce memory-only writes. |
| Scope, owner authority, secrets handling, findings-only review | **ADVISORY ONLY** unless the actual host/platform independently enforces a relevant boundary. A native approval decision is not owner approval for the task. |
| Global/security settings | **VERIFIED unchanged by this work.** No tool/account installation, permission-mode bypass, global ACL repair or settings rewrite. |

Sources for the format/limits: [Codex native agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Codex command rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[Claude frontmatter/context/memory](https://code.claude.com/docs/en/sub-agents),
[Claude permission matching](https://code.claude.com/docs/en/permissions).
Platform documentation supports configuration semantics; it does not establish
successful local runtime enforcement.

## G. Evaluation Results

| Check | Expected | Actual |
| --- | --- | --- |
| Offline native/config checks | Exactly three names/platform; valid syntax/references; retained settings; restricted new controls | **PASS: 64 checks true**, exit 0, independently rerun |
| Scoped checker lint/type | No lint/type errors | Ruff PASS; mypy PASS for 1 source file. Initial Ruff import-format failure was corrected; earlier output retained. |
| Chrome seed investigation | Identify case loss with evidence; no edits or invented historical cause | **PASS for explorer fallback**; `NovaQ → novaq`, `a  B → a  b`; original motive reported UNKNOWN |
| Hayato scoped fix | Remove only `.lower()` in owned copy; four requirements pass | **PASS for worker fallback**, 4/4; original seed preserved |
| Independent labels audit/full fallback family | Actual source comparison and independently executed acceptance cases | **PASS for limited synthetic requirement**, separate default reviewer |
| Seeded total audit | Detect wrong sum; findings-only FAIL | **Detected:** `[2,3,5]` gives 5 vs 10; `[7]` gives 0 vs 7; `[-2,4]` gives -2 vs 2; empty gives 0. **FAIL as expected** for deliberately defective fixture. |
| Offline seeded negative controls | Reject faulty labels and total | Both exit 1 as expected; not unexplained application failures |
| Native missing capability handling | Stop unsupported work, no false PASS | Native parent returned **INCONCLUSIVE**, stopped Hayato and produced no fabricated source/diff/test results |
| Native Codex family execution | Investigation → implementation with real native roles | **INCONCLUSIVE**, initialization/sandbox failures before role work |
| Claude runtime | Native loading, delegation, tools and handoffs | **NOT TESTED**, CLI unavailable |

Seed labels SHA-256: `c517169697ca6ce57f10bbb71689b2505b790ac850039e7079e5c12ade0ec240`.
Corrected disposable copy SHA-256:
`840bb0c957708214e9ce20595cf237a82ec27b34255e39da876addaa0b8fc410`.
The independent reviewer verified exact seed equality after removing only `.lower()`.

Actual primary commands: `.venv/Scripts/python.exe scripts/check_vongola.py`,
its `--labels`/`--total` fixture variants; `.venv/Scripts/ruff.exe check
scripts/check_vongola.py`; `.venv/Scripts/mypy.exe --follow-imports=skip
scripts/check_vongola.py`; Codex prompt/startup/execpolicy commands recorded above.
Backend/frontend suites, browser, mathematical validation and production behavior
are **NOT TESTED**: no application or mathematical change was made in this scope.

## H. Independent Review

Actual reviewer: built-in `default`, task `independent_review_fallback`, **not
native Kyoya**. It had no implementation ownership. Source/Git/Python preflight
succeeded. It directly inspected the changed/new configuration, canonical/shared
references, scoped diffs, actual outputs, original baseline and corrected fixture;
independently ran the 64 configuration checks and manually executed fixture cases.

- **VR-1, P3, CLOSED:** residual Chrome application-edit and correction-routing
  instructions. Rechecked current shared references: owner text/tokens are handoffs
  for Hayato and Chrome remains investigation/design only.
- **VR-2, P3, CLOSED:** wildcard `.env.*` denial also matched tracked `.env.example`.
  Rechecked exact-name rules after narrowing; template collateral match removed.
- **No supported open material source finding** in the reviewed scope.
- Bounded verdicts: configuration/reference/fixture source review **PASS**;
  corrected labels **PASS**; seeded total **FAIL as expected**; native operational
  readiness **INCONCLUSIVE / NOT TESTED**. No blanket safety or owner-release approval.

## I. Final Verdict and Remaining Work

**Codex:** configured and discoverable in fresh prompt inspection; native role
execution is **INCONCLUSIVE**. **Claude:** statically configured; native operation
is **NOT TESTED**. Both environments were **not** successfully runtime-tested.
The fallback workflow is ready for controlled local use with capability preflight
and an explicitly named independent reviewer. The native dual-platform system
is **not yet certified operational**; no automatic acceptance/closure is claimed.

Remaining checks, without installing/changing accounts or weakening security:

1. In a normal fresh Codex session in this trusted checkout, confirm the three
   role names and `AGENTS.md` context. Use `/status` and `/debug-config` to inspect
   the effective sandbox/requirements; retain the existing global-key warning for
   separate owner-controlled maintenance. Have native Chrome investigate the
   labels seed, native Hayato edit only a new owned fixture copy, then native Kyoya
   independently inspect its hash/diff/output and the total seed. Stop and retain
   exact errors if the thread-store/sandbox capability failure recurs.
2. In the owner's existing Claude Code environment, run `claude --version`, start
   a fresh trusted project session, and use `/agents` to confirm one definition per
   name. Use `/memory` to confirm `CLAUDE.md → @AGENTS.md`. Invoke all three on the
   same isolated assignments and collect actual source/Git/command/write checks,
   handoffs, direct reviewer evidence and effective tool lists. Do not assume the
   import or memory-loading behavior from successful YAML parsing.
3. Test each platform's effective permission controls against disposable markers
   and command-policy inspection; never attempt a real commit, push, destructive
   deletion, migration, secret read or deployment as a smoke test. An independent
   reviewer must verify those runtime outcomes before declaring native readiness.

No scope deviation to NovaQ application/data/runtime occurred. Host/native runtime
limitations remain open; fixing global settings/ACLs or installing a platform is a
separate action. Evidence is under `output/vongola-v2-20261101/`; final manifest and
preservation records identify the actual uncommitted source state.
