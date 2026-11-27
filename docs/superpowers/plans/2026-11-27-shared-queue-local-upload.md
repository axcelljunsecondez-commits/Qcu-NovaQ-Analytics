# Shared Queue upload implementation plan

1. Read the shared aggregate preview and its consumers in `AnalysisSetupPage.tsx`. Keep the existing preview, apply, confirmation, save-closing, and cache calls.
2. Place the shared-file findings and existing closing control in the upload card. Add the source-derived operating-hours display using the existing bilingual key. Use existing shared-file styles, adjusting that stylesheet only if the placement requires it.
3. Update the focused upload test to exercise different file endpoints and verify that the findings appear with the picker. Run shared upload, setup and simulation regressions, frontend typecheck, lint, and build. Preserve user-owned changes and app contracts.
4. Have Kyoya compare the isolated candidate with the cached source and independently inspect actual checks. Exercise the local UI with the owner-supplied CSV and a disposable database before reporting local availability.
