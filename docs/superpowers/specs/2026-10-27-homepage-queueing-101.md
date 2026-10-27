# Queueing Theory 101: approved local homepage and Help integration

Follow-up: the later [combined-video and placement specification](2026-10-27-combined-video-and-homepage-placement.md) supersedes this document's two-video selection and right-column Queue Types carousel. The original authorization and verification below describe the earlier version.

## Authorization and source

The owner approved the interactive Hero spotlight preview and explicitly requested local application on 2026-10-27. The accepted layout places the headline and How it works disclosure on the left; the two-part lesson player and Queue types disclosure on the right. Both disclosures start closed, reveal smoothly, and offer manually controlled Previous/Next slides that wrap. No automatic scrolling, anchor navigation, timed slide advance, or programmatic focus movement is added to the disclosures.

The approved reference is novaq-homepage-lessons.html in this chat's visualization directory. Its 14-second media excerpts are presentation constraints of that preview. The application will serve the full previously reviewed Part 1 (2:25 displayed duration) and Part 2 (4:22) lessons. Both contain English synthetic narration and visible English captions; this is labeled in both application languages.

Base: bb585a45faf8845007e8eea7afe7c8f40ec06435. Root main at 6093d78a is older; the existing ux-workflow-audit checkout has unrelated changes and is not modified. Work is isolated on codex/homepage-queueing-101.

## Implementation contract

- Use typed React components, existing theme tokens, existing queue illustrations and natural symmetric EN/TL strings. Preserve the hero's one primary analysis action, signed-in/signed-out destinations, calculator, Help, language and theme controls.
- Reuse the new lesson component in the Help index; preserve its current guides, tutorials and search. Include new lesson matches when determining empty search results.
- Load only a requested same-origin MP4; validate expected size and type, use a Blob URL for seeking even without server Range support, and abort/revoke/pause on replacement or unmount. Follow the established tutorial player's loading/lifecycle pattern without changing existing tutorials.
- Put playback controls outside the picture so they do not cover burned-in captions. Support manual play/pause, seek, speed, mute and supported fullscreen. Keep complete captions/transcript and direct downloads available. No autoplay attribute.
- Keep a field-collection checklist with observed-vs-unknown and field-log-vs-upload distinctions. Header-only field sheets contain no fabricated company rows.
- Disclosures use linked ARIA state and inert collapsed content. Inactive slides are hidden from interaction and assistive technology. All slides share an intrinsic stage height; rapid navigation cancels obsolete motion. Respect reduced-motion preferences.
- Fictional teaching examples remain explicitly illustrative. Theta remains an optional, model-specific rate with a stated exponential-patience example; no fitted/company result or universal staffing claim is introduced.

## Permitted scope

HomePage, HelpPage, new learning/home components and catalog/content, same-origin media/captions/posters/field sheets, both locale catalogs, additive scoped styles, behavioral tests, and this spec/plan/verification report. No backend, mathematical formula/model selection, API/schema, authentication, proxy/CSP, database, optimizer, simulation, dependency version, production or repository Docker Compose configuration change. Local activation may use a web-image override while preserving the existing API/database containers, settings and ports; do not run migrations or seeding.

## Verification and limits

Run the repository gates using the correct Python environment and locked frontend dependencies. Verify asset hashes/bytes and locale symmetry; test media lifecycle, actual navigation contracts, disclosure/loop behavior and search integration. Inspect the built React application in a real browser for EN/TL, light/dark, reduced motion, mobile/desktop overflow, media playback/seek, focus/keyboard and viewport stability. Record every failure and repair. Local source/build/browser proof does not establish production state, learner comprehension or the unrelated open statistical findings. No push or production deployment is authorized.
