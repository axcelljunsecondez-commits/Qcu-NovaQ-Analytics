# Local wording and English headings

Status: APPROVED SPECIFICATION by the owner's explicit implementation request on 27 October 2026. Application scope is local only. This document is not verification evidence.

## Approved behavior

Use the wording in `overall-revision-2.pdf` as supplied; accept natural/conceptual Filipino and familiar English terms. Do not apply the earlier reviewer's editorial alternatives. Built-in page, section, card and dialog headings, including heading-styled labels such as Find Help, remain English in both languages across the application. Ordinary field/result labels, explanations, buttons, navigation and tabs retain their selected-language/PDF wording. User-entered names and data remain untouched.

Apply English by usage. A translation key shared between a heading and another label must not force both usages into English. Preserve interpolation and accessible label associations; mark built-in English headings with the appropriate language where possible. Help search must still find the displayed guide titles and the selected-language descriptions.

## Copy provenance and conflicts

Source PDF SHA-256: `49c5b160798df6535c5c99ac810371605dba41fa030777c6bcb80fd68b75deac`. The prior local review accounted for 80 BEFORE blocks and 92 mapped keys. Its recommended copy is not the implementation source: use the PDF-requested fields and document headings instead.

Follow AGENTS.md's stop conditions for confirmed contradictions with implemented units, capacity definitions, or the saved-run evidence boundary. Retain the existing affected string and report the exact requested string and reason; do not silently replace it with a reviewer alternative or alter mathematics to accommodate it. Independent nonconflicting wording and heading work continues. Parameterize screenshot-example operating hours using the existing hours placeholder. Use the PDF's explicit final tab-name entry where the document supplies a later tab-specific label. Keep actual workbook sheet/PDF section identifiers unchanged; they are not ordinary UI headings.

## Permitted implementation

Frontend heading translation helper and heading consumers, both locale catalogs, narrowly scoped label/tooltip case styling required by the PDF, Help title search and affected Help screenshots, meaningful tests and these implementation records. No queueing math, API/schema, backend behavior, authentication, data, media replacement, dependency, production configuration or deployment change. The earlier combined-video/horizontal-diagram proposal is separate and is not included.

## Verification

Re-establish clean worktree provenance; record every applied/retained PDF field. Exercise English and Filipino across pages, shared components, dialog/search headings, interpolation, user names, keyboard associations and responsive layouts. Refresh affected Help screenshots only against an isolated synthetic fixture. Run repository-required gates and actual local browser checks before frontend activation. Preserve existing API/database services and data, and report any unavailable runtime gate honestly. No commit or push is requested.
