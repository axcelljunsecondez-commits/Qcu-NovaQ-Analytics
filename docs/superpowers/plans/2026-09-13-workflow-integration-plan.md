# NovaQ workflow integration implementation plan

Date: 2026-09-13

1. Add regression tests for unified DES output and non-terminating trace caps.
2. Instrument the existing aggregate DES lifecycle and make trace a wrapper
   over that lifecycle while retaining both public contracts.
3. Add an ownership-scoped workflow API backed by existing Job records:
   selection, evidence retrieval, DES, Monte Carlo, validation, and Decision.
4. Add API tests for ownership, persistence, stale evidence isolation, and all
   deterministic Decision outcomes.
5. Add frontend workflow client types and calls.
6. Persist the Compare selection and require it as Simulation input.
7. Consolidate DES and Live into a single DES/playback category; keep Monte
   Carlo and Validation as distinct categories.
8. Rework Sidebar and AnalysisWorkspace navigation to the required order and
   add the bottom workflow navigator.
9. Rework Decision to render backend evidence and trigger deterministic
   derivation; make Reports show and consume the saved Decision.
10. Add symmetric English/Filipino strings and focused frontend tests.
11. Run all repository gates, rebuild Docker Compose, and verify health.
12. Update handoff/memory and produce the required implementation report.
