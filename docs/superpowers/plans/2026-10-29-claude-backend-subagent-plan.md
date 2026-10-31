# NovaQ Claude backend subagent implementation plan

Date: 2026-10-29 (Asia/Shanghai).

Current identity update: use `hayato` for the backend and `kyoya` for the independent reviewer. Backend memory is now `.claude/agent-memory/hayato/MEMORY.md`. See the [current roster and reviewer plan](2026-10-29-kyoya-reviewer-and-hayato-rename.md). Earlier names and verification records below describe the configuration before this follow-up.

Specification: [Claude backend subagent](../specs/2026-10-29-claude-backend-subagent.md).

## File scope

Add only:

- `.claude/agents/novaq-backend.md`
- `.claude/agent-memory/gokudera/MEMORY.md` (moved from the original `novaq-backend` directory during the naming follow-up)
- `docs/superpowers/specs/2026-10-29-claude-backend-subagent.md`
- `docs/superpowers/plans/2026-10-29-claude-backend-subagent-plan.md`

## Steps

1. Inspect current instructions, project records, existing agents, backend entry points and official Claude configuration documentation.
2. Create the backend role and a minimal memory index. Include task ownership, resume behavior, bounded verification and an evidence-based return format.
3. Parse the definition, validate referenced paths and ownership/memory requirements, check whitespace and inspect the exact file list. Confirm `CLAUDE.md`, the existing designer and application sources are untouched by setup.
4. Report the setup, invocation text and untested Claude runtime behavior.

## How to use

Open Claude Code in the checkout containing these files, then ask:

> Use the hayato subagent for this backend task: [describe the task]. Read its project memory and the current handoff first, resume any matching unfinished work, and give it exclusive ownership of the assigned backend files. Return actual changes, verification and remaining work, then save a concise task record.

Within the same conversation, ask the parent to resume the existing backend agent for related follow-ups. In a later conversation, the agent uses its memory records and the repository's current state. If it is not discovered, restart Claude Code in this checkout. A different Git worktree needs the definition and memory made available there; setup does not copy them to other worktrees.

## Verification record

Status: COMPLETE for configuration and documentation; runtime behavior NOT TESTED.

- VERIFIED: parsed the new definition with the repository `.venv/Scripts/python.exe` and `yaml.safe_load`. Name, description, supported fields, tool allowlist, `model: inherit` and `memory: project` matched the intended configuration. Both project agent names were unique.
- VERIFIED: all 26 referenced repository context paths existed. Ownership/resume requirements were present, and the 20-line memory index explicitly recorded that no backend task or test had been completed through this agent.
- VERIFIED: all four added files decoded as UTF-8 without a BOM, had final newlines and no trailing whitespace. No tracked or staged changes existed, and the single `@AGENTS.md` import remained intact. The existing designer definition was retained.
- NOT TESTED: Claude discovery, delegation and cross-session memory loading. `Get-Command claude` did not resolve an executable; the standard user `.local/bin/claude.exe` and AppData npm `claude.cmd` paths were absent. No Claude process or external model request was started. Automatic memory availability in the user's actual Claude session is UNKNOWN.
- NOT TESTED: backend/frontend application tests. This setup added agent configuration and documentation only; no application, test, mathematical, schema or service change required behavioral verification. This is not a backend correctness or production verification claim.

No backend repair is authorized by setup. Assign the first concrete task with the invocation above.

## Follow-up plan: existing family names and Chrome review

1. Capture the two definitions and backend memory before editing. Inspect the frontend entry points, package alias and approved wording rules used in Chrome's prompt.
2. Set the existing frontend definition's name to `chrome` and backend definition's name to `gokudera`; introduce those names in their opening sentences. Keep both filenames, roles and model settings. Update Gokudera's handoff references to `chrome`.
3. Move the backend memory index to the `gokudera` directory and update its heading. Preserve the rest of its content. Do not create Chrome memory as part of a suggestions-only review.
4. Write the source-grounded review, including proposed additions, existing strengths to preserve, unresolved scope decisions and verification limits.
5. Reparse YAML, check name uniqueness and memory paths, reverse the intended name/reference replacements against captured text hashes, verify only the permitted files changed, and report actual results.

The added file is `docs/superpowers/reports/2026-10-29-chrome-role-review.md`. Other than the already-scoped backend definition, memory and setup documents, only `.claude/agents/novaq-growth-designer.md` is edited. No application or frontend runtime test is needed for this configuration/documentation change. Claude discovery and role-performance improvements require separate runtime evidence.

Follow-up verification: COMPLETE for naming, memory preservation and the source review.

- VERIFIED: the repository Python/YAML parser found exactly `chrome` and `gokudera`, with the intended unchanged model/tool/memory settings. Keeping the original filenames is supported by Claude's identifier-based configuration.
- VERIFIED: reversing only the intended naming changes reproduced Chrome's captured text SHA-256 `ecd295ed03569eefddc529e32dd62bd25806a01271cf4d83e851436d4d6a1e05`. Reversing Gokudera's name, frontend handoff and memory-path changes reproduced `e5e215e87136fcbd3d418619bec5ae7733087c3652558f4a71262fc642e4199a`.
- VERIFIED: reversing only the moved memory index's heading reproduced its original text SHA-256 `a74911da61dbc584a6cb61bf59d72c917e373acaa899030beafa277f56b5417f`. The old index path no longer existed. No Chrome memory was added; it remains a review proposal.
- VERIFIED: captured hashes for `AGENTS.md`, `CLAUDE.md`, root `memory.md` and `handoff.md`, `frontend/package.json` and `frontend/src/router.tsx` matched. All six scoped files passed document-link and whitespace checks; `git diff --check` passed, with no tracked or staged changes.
- NOT TESTED: Claude discovery/invocation, cross-session memory and performance. Python `shutil.which('claude')` returned `None`. No application or browser execution occurred for this naming/documentation change.
