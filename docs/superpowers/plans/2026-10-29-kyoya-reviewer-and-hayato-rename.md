# Kyoya and Hayato implementation plan

Date: 2026-10-29 (Asia/Shanghai).

Specification: [Kyoya reviewer and Hayato identity](../specs/2026-10-29-kyoya-reviewer-and-hayato-rename.md).

## File scope

- Add `.claude/agents/kyoya.md` and `.claude/agent-memory/kyoya/MEMORY.md`.
- Update `.claude/agents/novaq-backend.md` and move `.claude/agent-memory/gokudera/MEMORY.md` to `.claude/agent-memory/hayato/MEMORY.md`.
- Add this plan and its specification.
- Update only current-identity/usage guidance in the existing `2026-10-29-claude-backend-subagent.md` spec, `2026-10-29-claude-backend-subagent-plan.md` plan and `2026-10-29-chrome-role-review.md` report.

## Steps

1. Establish current instructions, exact checkout/HEAD, dirty files, current definitions/memory and source paths appropriate to the reviewer. Consult official configuration documentation.
2. Write Kyoya's four-part review role and minimal memory index, keeping findings independent from implementation.
3. Apply the backend first-name change and preserve the existing memory. Update active instructions without rewriting historical execution evidence.
4. Parse all definitions, check unique names/settings, compare Hayato and his migrated memory against the committed originals with naming edits reversed, and confirm Chrome/application/governance preservation.
5. Validate links, source paths, memory size, whitespace and exact diff scope. Record actual results and untested behavior.

## Current roster and invocation

| Identifier | Responsibility | Definition | Memory |
| --- | --- | --- | --- |
| `chrome` | Existing frontend/growth design role | `.claude/agents/novaq-growth-designer.md` | Her proposed project-memory enhancement remains unapplied |
| `hayato` | Existing backend role | `.claude/agents/novaq-backend.md` | `.claude/agent-memory/hayato/MEMORY.md` |
| `kyoya` | Independent security, code, boundary and evidence review | `.claude/agents/kyoya.md` | `.claude/agent-memory/kyoya/MEMORY.md` |

In Claude Code, in this checkout:

> Use hayato for this backend task: [task]. Check current project records and his memory first, then resume matching unfinished work.

> Use kyoya to review [exact revision, working diff or files] against [approved task/spec]. Check security, code correctness, scope boundaries and the evidence behind all material claims. Report findings only and save a concise review record.

The parent coordinates ownership and sends corrections to Chrome or Hayato. Resume Kyoya for related follow-ups within the same conversation; in later conversations use the same review ID and verify the changed source. A running session may need a restart to discover the renamed/new agent; other worktrees need these files made available separately.

## Actual verification

Status: COMPLETE for configuration, identity continuity and documentation.

- VERIFIED: static validation executed with the repository `.venv/Scripts/python.exe` and `yaml.safe_load`, exiting 0. Exactly three definitions parsed with unique identifiers `chrome`, `hayato`, `kyoya`. Chrome retained Opus; Hayato and Kyoya use the inherited model and project memory. Kyoya's tool list excludes agent spawning and messaging tools; no permission-mode override was added.
- VERIFIED: reversing only Hayato's name, introduction and memory-path edits reproduced the committed backend prompt at base `ea14e2713ac9950bc032b4a969c1c3bf759feb93`, normalized text SHA-256 `5eb56f3f3d0c00f316460fbc519251ccd0fa707b66f970e4ae194f7370b11cd8`. The backend responsibilities and settings were preserved.
- VERIFIED: reversing only the migrated memory heading reproduced the committed backend index, normalized text SHA-256 `d132ebf3cae8056dfb72e1c9ef3005f99f9085967018f118c5b13d076aec0ad8`. The old `gokudera/MEMORY.md` path was absent. Both current memory indexes were under 200 lines; Kyoya's index claimed no completed application review.
- VERIFIED: Chrome's entire definition matched the committed original. The tracked diff contained only the backend definition/index and the three specified documentation updates; the five added paths matched the specified Kyoya files, new memory destination and new spec/plan. No application, test, root governance or project-history file was changed or staged.
- VERIFIED: all 29 reviewer source entry points existed; the four responsibilities and memory-only/application-review constraints were present in the prompt. All nine final scoped files passed UTF-8, newline, whitespace and document-link checks; `git diff --check` passed. These are configuration/content checks, not execution evidence that the reviewer obeys its instructions.
- NOT TESTED: Claude discovery/invocation, memory loading and actual review behavior. Python `shutil.which('claude')` returned `None`. No external model request was made. The prompt's write restrictions are not a host-enforced filesystem sandbox.
- NOT TESTED: backend/frontend suites and browser/native/production behavior, because this task changed only agent configuration and documentation. No application review, security audit, numerical validation, service operation, commit or push was performed by this setup.
