# Chrome role review and existing-agent names

Date: 2026-10-29 (Asia/Shanghai).

Current identity update: the backend was subsequently renamed from `gokudera` to `hayato`, preserving its memory, and reviewer `kyoya` was added. See the [current roster and usage](../plans/2026-10-29-kyoya-reviewer-and-hayato-rename.md). The review observations and earlier execution records below retain their original two-agent context. Chrome's proposed enhancements remain unapplied.

## Outcome and scope

VERIFIED: the active root checkout was `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`, branch `main`, HEAD `3ee8fe2c5d3f1521e37255959f2383e67e374b4c`. This review concerns the two local agent definitions, not a claim about other worktrees, GitHub or production.

The existing frontend definition `.claude/agents/novaq-growth-designer.md` is now named `chrome`; the existing backend definition `.claude/agents/novaq-backend.md` is now named `gokudera`. Filenames remain stable. Chrome keeps `model: opus`; Gokudera keeps `model: inherit`, its tool list and `memory: project`. Gokudera's memory index moved to `.claude/agent-memory/gokudera/MEMORY.md`, with its content preserved apart from the heading. There are still two project agent definitions.

Chrome's role enhancements below are PROPOSED, not applied. No application source, user-facing wording, tests, dependencies or services were changed. The character names do not change either agent's engineering responsibilities.

## Main recommendations

1. Add project memory and resumable task records to reduce repeated explanations and investigation.
2. Make startup and browser coverage match the assigned task, with explicit ownership shared through the parent.
3. Refresh two concrete instructions: the Plotly npm alias and the approved English-heading exception.

Expected efficiency benefits are INFERRED; agent speed, token usage and task quality were NOT TESTED or measured.

## F1: Give Chrome persistent task memory

VERIFIED: Chrome's frontmatter contains `name`, `description` and `model`, with no `memory` field (`.claude/agents/novaq-growth-designer.md:1-5`). Her prompt has no persistent task index or instruction to resume previously completed investigation. The only project agent memory index inspected at the start belonged to the backend agent. Gokudera already has a task-record/resume procedure in `.claude/agents/novaq-backend.md:19-28` and `:61-74`.

PROPOSED: add `memory: project` and a short `.claude/agent-memory/chrome/MEMORY.md` index. Store task IDs, checkout/HEAD and relevant dirty-source identity, owned files, approved design decisions, previously raised findings, actual validation and next action. Keep longer records in task files; do not duplicate root project history or permanent rules. Revalidate affected source before reusing historical evidence.

Official behavior: project memory uses `.claude/agent-memory/<agent-name>/`; ordinary subagents do not inherit the main conversation's history or auto memory. See [Claude persistent memory](https://code.claude.com/docs/en/sub-agents#enable-persistent-memory) and [startup context](https://code.claude.com/docs/en/sub-agents#what-loads-at-startup). Memory loading depends on the user's actual Claude configuration and remains NOT TESTED here.

## F2: Match startup work to the assignment

VERIFIED: Chrome currently reads a broad set of prior UX specifications before proposing changes (`.claude/agents/novaq-growth-designer.md:98-101`) and starts by walking the funnel on phone/desktop in both themes (`:103-109`). It does not distinguish a focused component task, findings-only review, visual prototype and broad funnel audit in that startup sequence.

PROPOSED: establish the task mode, completion criteria and affected routes first. Read current project records, then the applicable specifications and linked evidence. Inspect changed screens plus their direct consumers for focused tasks; reserve the complete funnel audit for assignments that require it. Reuse an identified suitable local server instead of assuming a new preview must always be launched. Use available preview/browser tools; report NOT TESTED when unavailable rather than treating static inspection as visual QA. Browser fixture creation, email, sign-up, simulation and saved-data actions must respect the assigned environment and authorization.

Retain the required frontend gates for application changes. Avoid repeatedly rerunning successful gates without a new change or unresolved concern. A smaller startup is not permission to skip the active task's required verification.

## F3: Add an explicit ownership and backend handoff procedure

VERIFIED: Chrome has strong protected-behavior limits (`.claude/agents/novaq-growth-designer.md:142-147`) but no startup procedure to establish checkout identity, dirty files, task ownership or an active task record. Gokudera has these checks. Chrome's current prompt also does not name the backend agent.

PROPOSED: before editing, identify the exact checkout and assigned files from the parent's task. Preserve others' changes. Use one writer per task/file scope and have the parent resolve overlap; memory notes are not locks. When a needed API field, persistence behavior or calculation is absent, return the exact route, field, units, consumer and acceptance criteria to the parent for Gokudera. Chrome should not manufacture a frontend substitute or independently send work to another agent. Resume the same task identifier for related follow-ups.

This preserves the frontend/backend boundary and the existing `AGENTS.md` scope rules. It does not expand Chrome's authority over backend files or protected behavior.

## F4: Resolve Plotly through its actual npm alias

VERIFIED: Chrome directs inspection of `node_modules/plotly.js-cartesian-dist-min` (`.claude/agents/novaq-growth-designer.md:57`). The current dependency is declared as `"plotly.js": "npm:plotly.js-cartesian-dist-min@3.7.0"` (`frontend/package.json:18`), and the chart module imports `Plotly` from `plotly.js` (`frontend/src/components/charts/Charts.tsx:4-5`). The prompt's physical-package lookup does not follow the dependency's import name.

PROPOSED: inspect `frontend/package.json` and the active checkout's installed resolution for `plotly.js`, then check the available trace types. Do not infer that the full Plotly bundle is installed from the import name, and do not assume a separate `plotly.js-cartesian-dist-min` directory exists. Keep the existing measured-bundle-cost and dependency-approval boundaries. Actual installed resolution and trace rendering were NOT TESTED in this review.

## F5: Explicitly preserve the approved English headings

VERIFIED: Chrome's wording rules require owner-supplied text, symmetric locale keys and requesting the other language when only one is given (`.claude/agents/novaq-growth-designer.md:35-43`, `:89-96`). Her prior-decisions list includes the wording specification, but the operative wording section does not spell out its heading exception. `docs/superpowers/specs/2026-10-27-local-wording-and-english-headings.md:5-17` explicitly keeps built-in headings in English in both UI languages, while ordinary labels and descriptions follow the selected language and user content remains untouched.

PROPOSED: add this exception directly to Chrome's wording rules and point to the existing `headingText` mechanism, owner wording record and wording-policy tests. Preserve existing owner text; request wording only for genuinely missing slots. Do not ask the owner for a Filipino heading when the approved rule requires the English heading in both modes. This is an instruction clarification, not permission to rewrite translations.

## Optional scope decision: growth specialist or general frontend owner

VERIFIED: Chrome's description focuses on conversion and first value; findings are ranked against understanding the offer, signing up, first result and willingness to pay (`.claude/agents/novaq-growth-designer.md:3`, `:121`, `:138`). That is an intentional growth-design focus, not a complete frontend ownership mandate.

PROPOSED, only if the owner wants broader frontend coverage: add a separate signed-in workflow objective such as completing the assigned analysis task accurately and understandably. Keep growth and task-completion criteria explicit so an important settings, reporting or stale-evidence issue is not dismissed merely because its conversion effect is indirect. Leave this scope expansion unapplied until the owner chooses it.

## Existing strengths to retain

The role already specifies owner-controlled EN/TL wording, no fabricated marketing evidence, real-data chart provenance, uncertainty and stale-state treatment, existing components and theme tokens, keyboard/touch accessibility, reduced motion, responsive checks and frontend validation. These should be preserved rather than restated in additional overlapping sections. Keep Chrome's Opus setting during this review; no model comparison or runtime performance evidence supports changing it.

## Proposed implementation package

If the owner requests application, add project memory, one concise task-start/resume section and the two source-specific corrections. Keep all current protected-behavior and wording constraints. Refer to the backend agent by its current identifier `hayato` (previously `gokudera`). Do not add new agents, nested workers, frameworks, telemetry or product features as part of that package. The optional general-frontend scope decision is separate.

## Verification

VERIFIED: static validation executed with the repository `.venv/Scripts/python.exe` and `yaml.safe_load` and exited 0. It confirmed exactly two unique names, Chrome's unchanged Opus model and absence of project memory, and Gokudera's unchanged inherited model/tools/project-memory settings. Reversing only the intended replacements reproduced both original prompt hashes. The moved memory's original hash was reproduced after reversing its heading change; the former index path was absent, and no Chrome memory was created.

VERIFIED: snapshots of `AGENTS.md`, `CLAUDE.md`, root `memory.md`/`handoff.md`, `frontend/package.json` and `frontend/src/router.tsx` were unchanged. The six scoped files passed whitespace and document-link checks. `git diff --check` passed; no tracked or staged modifications were present. Python `shutil.which('claude')` returned `None`.

NOT TESTED: Claude discovery, delegation, memory loading, task speed, token cost and improved role quality. No external model request was made. No frontend/backend application test suite or browser session was run because the changes are limited to names, the backend memory path and review documentation. Static source inspection is the evidence for the review findings; it is not proof of runtime UI behavior.

Status: COMPLETE for the two existing names, backend memory preservation and source review. Suggested Chrome enhancements remain PROPOSED; runtime behavior and performance remain NOT TESTED.
