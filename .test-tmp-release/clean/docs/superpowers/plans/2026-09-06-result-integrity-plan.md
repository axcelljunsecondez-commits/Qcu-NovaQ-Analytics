# NovaQ result integrity implementation plan

1. Capture the current dirty tree and review implementation/tests. Reproduce the
   optimization, aggregate, numerical, ingestion, state, and deployment defects.
2. Fix engine feasibility and Erlang-A convergence with regression and invariant
   tests. Make incomplete aggregates explicit and propagate additive metadata.
3. Fix strict uploads, honest model-specific simulation coverage, and versioned
   immutable scenario persistence with API-level regressions.
4. Update React to retain calculation snapshots, block stale saves, use current
   session auth, and display unsupported/incomplete results and correct units.
5. Preserve and harden report generation, including incomplete comparisons,
   unknown utilization, escaped PDF text, and safe spreadsheet strings.
6. Separate development/production deployment, correct cookies/CORS/upload limits,
   retain supported Python compatibility, and add isolated integration checks.
7. Run backend pytest, Ruff, mypy, all frontend gates, and available Docker smoke
   checks. Review cross-subsystem contracts and the original user diff for safety.
8. Record changes, regression coverage, exact executed checks, limitations, file
   inventory, and the preserved baseline in a final implementation report.


## Follow-up execution

1. Inventory available infrastructure and data; request the public URL and observed
   records while independent rehearsals proceed.
2. Add localhost TLS and restored-API overrides plus smoke options with strict
   destination guards. Generate a temporary certificate in ignored storage.
3. Run the HTTPS workflow with production cookie/CORS settings.
4. Dump the synthetic database, restore to a new database and compare contents;
   exercise restored login, snapshots and PDF/Excel through an isolated API.
5. Validate changes and clean up only the rehearsal project; report precisely
   which public-infrastructure and real-data checks still need supplied inputs.
