# Kyoya reviewer and Hayato backend identity

Date: 2026-10-29 (Asia/Shanghai).

## Approved requirement

The owner approved creating the independent reviewer discussed as Hibari, requested first names, and explicitly requested replacing Gokudera with Hayato. The effective reviewer identifier is `kyoya` (Kyoya Hibari); the existing backend identifier becomes `hayato` (Hayato Gokudera). Chrome retains her current identity and role. This is configuration/documentation work, not authorization to review or repair the application now.

## Reviewer responsibility

Kyoya reviews work from Chrome, Hayato or the parent for four concerns: security, code quality/regressions, authorized scope/protected boundaries, and evidence/verification integrity. He follows the single engineering protocol in `AGENTS.md`; that obligation remains with every agent. His default output is findings and a bounded review conclusion, with implementation corrections returned through the parent to the responsible agent.

Configure `.claude/agents/kyoya.md` with the inherited model and permission mode, a local-development/documentation tool list, and `memory: project`. Memory supports recurring finding IDs, reviewed-source identity, actual verification and unresolved work. Only his own memory records and the disposable artifacts of authorized checks may be written during a review. The prompt forbids implementation, fixture, test-expectation, root-instruction and operational changes. This is an agent responsibility rule; the tool list is not a filesystem sandbox. No host permissions or approval bypasses are changed.

Required review behavior: identify the exact revision/dirty source and approved task, independently inspect source and evidence, run relevant authorized isolated checks where feasible, reproduce numerical claims when applicable, keep observed facts distinct from inferred risks, preserve failed/unknown gates, and avoid claims of blanket security or guaranteed absence of errors. Missing verification cannot be treated as a pass. Persistent memory must not replace fresh evidence or expose secrets/customer records.

## Identity continuity and documentation

Keep `.claude/agents/novaq-backend.md` as the existing backend definition. Change only its identifier, introduction and memory path. Move the existing backend index from `.claude/agent-memory/gokudera/MEMORY.md` to `.claude/agent-memory/hayato/MEMORY.md`, preserving its contents apart from the name in its heading. Inspection found only that index, with no task records to migrate.

Existing setup/review documents retain their historical names and actual earlier verification results. Add a current-identity note and update current invocation guidance so they do not direct new work to the retired `gokudera` identifier. Chrome's suggested enhancements remain proposals; her agent definition is outside this edit scope.

## Acceptance and permitted files

- Exactly three local agent identifiers: `chrome`, `hayato`, `kyoya`; valid frontmatter and nonempty prompts.
- Hayato's behavior, model/tools and memory content are preserved through reversible naming edits. The old memory index path is absent.
- Kyoya's four review responsibilities, independent findings workflow, memory discipline and execution limits are explicit. His memory index invents no completed review or test result.
- All referenced repository entry points exist; final links/whitespace and exact file scope pass static checks. Runtime discovery, review behavior and memory loading are reported separately if not executed.
- Scope: backend definition/index migration; new Kyoya definition/index; this spec and its implementation plan; identity/current-usage notes in the existing backend setup spec/plan and Chrome role review. No application, test, root governance, deployment or Chrome prompt edits. No commit or push is part of this request.

Source: [Claude Code custom subagents](https://code.claude.com/docs/en/sub-agents), including project scope, inherited configuration, tool selection and project memory (consulted 2026-10-29).
