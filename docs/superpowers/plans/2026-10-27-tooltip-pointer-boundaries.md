# Local tooltip repair plan

1. Reproduce and record real trigger/input rectangles, pointer behavior and scope before editing.
2. Share event handling and floating placement between InfoTip and name Tooltip; remove guest-only behavior and old positioning overrides. Retain actual accessible targets, hoverable text and current copy.
3. Add regression tests for blank-wrapper hover, pointer versus keyboard focus, click/touch pin toggling, outside input activation, Escape persistence, tooltip transfer, scroll/resize dismissal and viewport placement. Preserve existing behavioral assertions.
4. Run focused tests, complete frontend tests/typecheck/lint/build, backend regression/static gates as applicable, and real-CSS browser checks in both languages, themes, desktop/phone/touch and narrow/clipped layouts. Run heavy local suites serially; keep failures and reasons explicit.
5. Deliver local source and a loopback preview with before/after evidence and exact limitations. Docker activation is not claimed while the engine is unavailable. No production mutation, push, migration, seed, backend or database start is authorized/needed for this frontend preview.
