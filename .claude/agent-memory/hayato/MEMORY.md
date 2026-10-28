# Hayato backend agent memory index

## How to resume

- Read the active checkout's `AGENTS.md`, `memory.md`, latest relevant `handoff.md` entries and task spec/plan. Permanent rules stay there.
- Confirm checkout/branch/HEAD and dirty files before relying on a task record. History and saved notes do not prove current behavior.
- Match the delegated goal to a record before repeating investigation or implementation. Resume the same task identifier when appropriate.
- One owner writes a task and its record at a time. This index is advisory, not a concurrency lock; the parent coordinates ownership.
- Store detailed records in `tasks/<stable-task-id>.md`. Include ownership, source references, actual verification, relevant dirty-source identity and the next action. Keep this index under 200 lines.
- Read/write this memory explicitly if automatic memory loading is unavailable. Report any inability to persist the handoff.

## Setup provenance

VERIFIED at setup on 2026-10-29: the repository root was `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`, branch `main`, HEAD `3ee8fe2c5d3f1521e37255959f2383e67e374b4c`. This identifies where the configuration was prepared; it is not a backend verification baseline or a claim about another worktree, GitHub or production.

The role is defined in `.claude/agents/novaq-backend.md`. Setup specification and usage are in `docs/superpowers/specs/2026-10-29-claude-backend-subagent.md` and `docs/superpowers/plans/2026-10-29-claude-backend-subagent-plan.md`.

## Backend task index

No backend task has been delegated or completed through this agent yet. Consult the existing root handoff and linked reports for earlier project work; do not mark it as this agent's work. No backend tests or Claude runtime verification are claimed by this setup record.
