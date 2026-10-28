# NovaQ Claude backend subagent

Date: 2026-10-29 (Asia/Shanghai).

Current identity update: the backend agent is now `hayato`, with memory at `.claude/agent-memory/hayato/MEMORY.md`; the new reviewer is `kyoya`. See the [first-name and reviewer specification](2026-10-29-kyoya-reviewer-and-hayato-rename.md). The earlier `gokudera` names and setup results below are a historical record of the original configuration, not the current roster.

## Requested outcome

The owner requested a Claude subagent for NovaQ's backend to reduce repeated work and repeated context explanations. Implement a project-scoped Claude Code definition with project-scoped persistent memory. The original identifier was `novaq-backend`; the Vongola naming follow-up below changes it to `gokudera`. This authorizes configuration and documentation only; no backend task has been assigned by this request.

## Design

- Keep permanent engineering rules in `AGENTS.md`, already imported by `CLAUDE.md`. The agent reads the active checkout's project records and applicable specifications instead of copying those rules.
- Use `.claude/agents/novaq-backend.md` for the role, startup procedure, ownership boundaries, verification procedure and return format. Inherit the parent model and permissions; allow local development tools and official-documentation research, without nesting agents.
- Enable `memory: project`, using `.claude/agent-memory/gokudera/MEMORY.md` as a concise index of task records after the naming follow-up. Store checkout identity, affected files, evidence, actual verification and remaining work. Do not copy the main conversation or root project history into it.
- Before implementation, reconcile the assigned task with completed and active work. Reuse valid evidence, recheck affected source and inputs, and resume incomplete work. Parent coordination and one writer per task prevent overlapping assignments; memory files themselves are not a locking mechanism.
- Scope normal edits to explicitly assigned backend files, related tests, task documentation and this agent's memory. Frontend/design work returns to the parent and existing designer. Protected changes follow `AGENTS.md` and the applicable task authorization.

## Acceptance and boundaries

1. The definition parses as YAML frontmatter plus a nonempty Markdown prompt, has a unique name, and references existing repository entry points.
2. The memory index exists, contains no invented backend completion or test result, and describes how to resume work.
3. The instructions require actual evidence and preserve the existing governance import and frontend agent.
4. Only the four files listed in the implementation plan are added. No application changes, commits, pushes, service operations or external model execution are part of setup.
5. Static verification establishes configuration contents only. Claude discovery, invocation and cross-session memory behavior require execution in the user's Claude Code environment and must be reported separately if not tested.

Official configuration reference: [Claude Code custom subagents](https://code.claude.com/docs/en/sub-agents), particularly project scope, frontmatter, persistent memory and context management (consulted 2026-10-29).

## Follow-up: Vongola names and Chrome review

The owner's follow-up is interpreted in the immediately preceding naming discussion as applying Chrome to the existing frontend agent and Gokudera to the existing backend agent, then reviewing Chrome for possible improvements. Use lowercase identifiers `chrome` and `gokudera`, keeping the existing definition filenames. Do not create replacement or duplicate agent roles. Preserve Chrome's Opus model and existing instructions, apart from introducing her name. Preserve Gokudera's configuration and backend responsibilities, updating the frontend handoff name and memory path.

Move the existing backend memory index from `.claude/agent-memory/novaq-backend/MEMORY.md` to `.claude/agent-memory/gokudera/MEMORY.md`, preserving its contents apart from the heading. The inspected source directory has only that index and no task records. Claude's project memory directory is keyed by the agent identifier.

Review Chrome's current prompt against the active checkout's frontend configuration and approved wording specification. Record concrete suggestions and their evidence in `docs/superpowers/reports/2026-10-29-chrome-role-review.md`. Performance benefits are hypotheses until measured. Suggested role enhancements remain PROPOSED in this review; this follow-up does not apply them or change application code.

The follow-up file scope is the two existing agent definitions, the memory index move, this specification, its implementation plan and the new Chrome review report. All original application, production and mathematical boundaries remain in force.
