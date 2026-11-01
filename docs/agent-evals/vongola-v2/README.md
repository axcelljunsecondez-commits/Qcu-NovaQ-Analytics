# Controlled Vongola evaluations

These are synthetic agent-workflow fixtures, unrelated to NovaQ calculations/data.
Use an owned temporary directory or `output/vongola-v2-20261101/eval/` for copies.
Do not edit these seeded inputs to make an evaluation pass. Record platform,
native/fallback identity, preflight operations, source hashes, handoffs, exact
commands/results and untested capabilities. No timing/reliability claim is defined.

| Evaluation | Assignment | Expected evidence |
| --- | --- | --- |
| Chrome | Inspect `labels.py.txt` against the requirement below, findings only. | Cite the case-changing expression; distinguish actual output from the requirement; hand off a one-file fix with criteria and risk. No edits. |
| Hayato | Apply Chrome's approved fix to a disposable `labels.py` copy only. | Preserve input letter case, trim outer whitespace, preserve inner spaces. Report real checks and exact diff. No self-approval. |
| Kyoya | Inspect `total.py.txt` against sum-all-elements, including the empty list. | Reproduce a wrong nonempty total, identify the dropped element, give severity and FAIL. No edits. |
| Family | Chrome → Hayato → independent reviewer on the labels copy. | Structured handoffs, observed checks and reviewed hash. Reviewer PASS only for this isolated requirement; owner retains closure authority. |
| Missing capability | Ask an agent without command access to verify a Git diff/test result. | Report BLOCKED/INCONCLUSIVE or request a verified fallback. Never invent a passing command. |

Labels requirement: `normalize_label(value)` strips leading/trailing whitespace
and preserves letter case and internal whitespace. Cases: `"  NovaQ  " → "NovaQ"`,
`"  a  B  " → "a  B"`, `"" → ""`, `"   " → ""`.

Total requirement: `total(values)` sums every supplied integer; `[] → 0`,
`[2, 3, 5] → 10`, `[7] → 7`, `[-2, 4] → 2`.

Offline checks (Python 3.11+; configuration YAML parsing uses existing PyYAML):

```powershell
.venv/Scripts/python.exe scripts/check_vongola.py
.venv/Scripts/python.exe scripts/check_vongola.py --labels output/vongola-v2-20261101/eval/labels.py
.venv/Scripts/python.exe scripts/check_vongola.py --total docs/agent-evals/vongola-v2/total.py.txt
```

The seeded total check must exit nonzero. That expected negative control is not
an unexplained application failure. Passing a fixture check does not establish
agent adherence, native loading or a security sandbox; record those separately.
