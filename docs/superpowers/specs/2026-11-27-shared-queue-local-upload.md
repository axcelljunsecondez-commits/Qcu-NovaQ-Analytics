# Shared Queue upload and operating hours

The owner reviewed the standalone workflow preview and asked to apply it locally first. This candidate uses cached `origin/main` at `e303b179bed1d084bb57dbbc95a26661473e5aa9`.

The Shared Queue planning upload shows the file picker, the uploaded file's operating hours, the existing optional closing rule, and the action that processes the file in a single card. Use the existing file preview as the source of the start and end. Display the uploaded rows as currently supported by the aggregate reader. Keep Planning and Review only explicit choices. Preserve generic upload fallback, replacement confirmation, current-file checks, and the existing next links.

Use the existing English and Filipino locale keys for operating hours and closing. Preserve the existing saved closing choice and show the existing explanation of that choice where a user can read it in context. Capacity and abandonment can stay unknown during upload. Simulation remains the place to answer those model questions.

The initial upload-only scope was expanded after the owner approved earlier-cutoff simulation, Checks, and Reports. The [Shared Queue arrival allowance specification](2026-11-27-shared-arrival-allowance.md) governs the resulting cutoff behavior.

Acceptance uses the reference CSV's 05:00–18:00 window and a fixture with a different end. Matching preview and apply requests must remain unchanged. A declined file retains the usual upload. Existing closing policy and planning-vs-review behavior must remain intact. No production work is in scope.
