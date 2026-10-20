# Short-viewport workflow footer and keyboard focus

Date: 2026-10-19. **Status: source implemented; approved image build and isolated verification passed in the stated matrix. Subsequent owner-authorized local activation passed its scoped smoke; see the [activation record](../reports/2026-10-19-local-compose-focus-activation.md).** Implementation used the owner's existing UX-repair and verification-closure authorization. The specific CSS rule is an implementation choice, not a separately owner-selected design. Rebuild and existing-container replacement approval boundaries remain unchanged. See the [source verification record](../reports/2026-10-19-short-viewport-focus-verification.md).

Evidence and owner-authorized verification execution: [build addendum](../reports/2026-10-19-approved-build-verification-addendum.md).

## Verified defect

At 667x375 in Filipino/light, the sticky workflow footer is 135px tall and covers the keyboard-focused analysis selector. The selector is focused but its centre is occupied by a footer link. No document-width overflow is present; width measurements alone did not detect the obstruction.

## Required observable outcome

Keyboard-focused analysis controls remain visible and usable in a short viewport. All existing workflow links, action labels, route order, context identity, and access rules remain available. The normal desktop footer behavior remains outside the short-height change.

## Permitted implementation scope

Only `frontend/src/styles/global.css`: under `@media (max-height: 480px)`, set `.workflow-footer` to `position: static; bottom: auto;`. This returns the existing footer to document flow so it cannot cover earlier inputs. On short pages it remains after the content; on long pages the user reaches it by scrolling. The breakpoint is assessed by the matrix below.

Additional verified finding within this same CSS scope: the immediate mobile-to-desktop transition animated sidebar width and main margin-left, temporarily covering the focused selector. Replace those two geometric transition properties with paint-only color/background/border transitions in the existing desktop rule. Preserve collapse/expand handlers, widths, layout endpoints, labels, routes, and reduced-motion overrides.

No component, API, schema, mathematics, statistical acceptance criterion, translations, or protected behavior changes. The exact initially proposed diff and temporary-browser preview are retained in the primary checkout's verification evidence directory. Source and new built-image verification are recorded separately. The earlier selector image lacks this rule; the approved final image includes it. See the [exact image execution record](../reports/2026-10-19-approved-focus-image-verification.md).

## Verification required before acceptance

- Reproduce the current obstruction through normal Tab navigation before applying the source correction.
- Check focused-control visibility and hit testing at 667x375 and 812x375 in EN/TL and light/dark.
- Check desktop 1280x720 retains its existing footer position and selector behavior, and a portrait viewport still reaches all workflow actions.
- Check normal and reduced-motion preferences without changing assertions or adding a CSS-text snapshot that merely mirrors the implementation. Re-run the original matrix without an animation-settling precondition to verify the additional resize obstruction is cleared, and check desktop sidebar collapse/expand behavior.
- Run the required frontend gates, preserving earlier failures and distinguishing source/fixture checks from a newly built and activated image.
- A new source digest requires its own reviewed build candidate under the owner's rebuild approval rule. Existing-container replacement remains a separate itemized action.
