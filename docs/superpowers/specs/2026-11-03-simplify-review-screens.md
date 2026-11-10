# Simplify NovaQ's review screens

Status: **APPROVED SPECIFICATION** (owner approval recorded from a Codex session; this file records it and adds no new requirement).

## Source of approval

- Codex session `01a18629-1f6c-7492-be64-1876c0804d01` (transcript excerpt reviewed by the parent on 2026-11-10).
- 2026-11-03T12:19 — the owner's own list of concerns (quoted below, verbatim).
- 2026-11-03T12:50 — the owner replied "PLEASE IMPLEMENT THIS PLAN:" followed by the plan (quoted below, verbatim).
- 2026-11-03T18:33 — the owner replied "approve build all the changes in docker".
- 2026-11-04T00:35 — the owner asked for the busiest-arrival fallback (quoted below, verbatim).

The owner's words below are copied exactly, including spelling and spacing. They are not edited or paraphrased.

## The owner's list (2026-11-03T12:19)

```text
this is all my concern
My analyses
   data setup
1. Remove the "Download my current setup"
2. remove the "total rates"only the customer event needed.
3. "Review what NovaQ read" this one we can remove this replace a verdict why this model. back in the backend we will keep for the excel export computation. ask me about this if you need to clarify.

    suggested plans
4. Review the Check 
  Schedule check complete. Review the results.

No break move lowers the peak load within this7move limit.
to this one i only need what break changes if theres move like what minutes we use, ex: 1hr @11:00-12:00 will be 40mins only the findings will be see in this max of 4 rows if theres more give a next next option to this table.

the break details no need we can remove this and the schedule and calculation details.

in the confirm changes. list the choices parameters in this tab but dont need to be detailed list like table.
ex: 70% utilization
    allow break time changes
    and what changes to the break time like from 1hr to 40mins stagger break. this for example you.
compact this positioning to this tab. dont include any unnecessary word. dont over detailed this is only for final review before we save or use this plan.

Analysis Result

1.in the analysis result the current operation by period we can see only the need to adjust max at 5 row if exceed have a next next button and add a smooth transition.


2. remove this "Period that needs attention" and "Busiest period by customer arrivals"

3.Your day, by Busy Level this one i think i dont need.

queue simulation

1. "result check" I need to see at the bottom is the FAIL and give explanation why it fail.


Quick Calculator
1. in "Result" 
 to this box always keep the numbers at the bottom of the header of the box ex:
Average wait in line ⓘ
15mins
this concept apply this to all boxes. in Quick Calculator

"what this means"i think this verdict not helping the user we can just remove this.

final note: we can remove to the all pages the word Capstone Project. 
```

## The approved plan (2026-11-03T12:50, "PLEASE IMPLEMENT THIS PLAN:")

```text
# Simplify NovaQ’s review screens

## Break scheduling

High arrivals show **when demand is heavy**. Cashier utilization shows **whether the staff on duty can handle it**. The break check connects them by testing whether moving a break eases the busiest workload without overloading another cashier. Keep the existing wait check and report when the evidence is unclear.

The Philippine rule generally provides at least **60 minutes for regular meals**. DOLE’s compressed-workweek advisory also specifies at least 60 minutes for schedules that can reach 12 work hours. It gives no general 90-minute requirement. Workplace agreements can provide additional benefits. [DOLE Labor Code, Articles 83–85](https://dole.gov.ph/book-3-conditions-of-employment/) · [DOLE compressed-workweek advisory](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/11/40740)

Start with **staggering existing breaks**. Keep meals continuous and preserve scheduled break durations. Treat **15, 30, and 60 minutes** as possible limits for a later optional rest-break check. That check needs approved workplace rules for eligible breaks and must preserve total entitled time. It requires separate authorization because it changes scheduling behavior.

## Screen changes

| Screen | What users will see |
|---|---|
| **My analyses → Data and setup** | Show **Customer events** as the template heading with a help tooltip. Remove **Total rates** and **Download my current setup** from the screen. Replace **Review what NovaQ read** with the selected model and a short reason drawn from the calculation. Keep upload warnings, required confirmations, older file compatibility, and the backend data used by Excel exports. |
| **Suggested Plans → Review the check** | Show only the break findings. Each row names the cashier and shows the old and proposed time and duration. Show up to **4 rows** with Previous and Next when needed. If no move qualifies, show one short finding. Remove the generic completion message, **Break details**, and **Schedule and calculation details**. Keep any warning that blocks confirmation. |
| **Suggested Plans → Confirm changes** | Show a short list of the actual choices, such as **70% utilization**, **Break time changes allowed**, and the proposed shifts. Put saved-plan selection in Suggested Plans and show **Use for simulation** when a different eligible plan is chosen. |
| **Analysis Results** | In **Current operation by period**, show only Peak, Critical, and Unstable periods or cashier lines using the existing workload bands. Show the most severe first, up to **5 rows** per page, with Previous, Next, and a transition that respects reduced-motion settings. Remove the two period callouts, **Your day, by Busy Level**, the arrivals and workload charts, and the redundant **What the plan changes** card. Keep the wait comparison chart. |
| **Queue Simulation → Result check** | Put **FAIL** and the reason at the bottom when the check records a failure. Show the affected period or cashier and the threshold when the result provides them. Give unchecked and inconclusive results their own states. |
| **Quick Calculator** | Put the metric name and tooltip above the value in every result card. Remove **What this means** and the extra calculations used solely for that paragraph. |
| **All pages** | Remove **Capstone Project** from user-facing branding. |

## Acceptance checks

Verify both queue types, older uploads and Excel export, saved-plan selection through Simulation, actual failure reasons, and pagination at the 4- and 5-row boundaries. Check English and Filipino on desktop and mobile. Run the frontend gates and verify the existing break-move workflow through review and confirmation.

```

## The busiest-arrival fallback request (2026-11-04T00:35)

```text
you can show a peak hours here there, looks like no changes or novaq didn't solve anything, in the data
```

Context: the request followed a screenshot of Analysis Results where "Current operation by period" showed no rows, while the recorded average wait was 41.5 min and the estimated average wait 6.3 min.

What Codex built for it (Codex's report at 2026-11-04T00:40: "NovaQ already has arrival rates for each period. I've added a fallback for up to five of the busiest periods when the workload table is empty."), as found in `frontend/src/components/results/ResultsSummary.tsx` at commit 164d85ebf:

- When no period or cashier line qualifies for the workload table (Peak, Critical or Unstable), the card shows the existing empty-state message and a list headed by `results.peak_arrival_periods` (English: "Busiest periods with arrival data").
- The list shows up to five periods (`PAGE_SIZE`), highest arrival rate first, using the arrival rates per period the page already has (`arrivalsByPeriod`), filtered to the selected period. Periods without a positive, finite rate are left out.
- When one cashier line is selected, the rates come from that line's own arrival records (`arrivalRecords`) instead of the store total. A period with more than one rate for that line is left out, because one rate cannot be established.
- No arrival rate is calculated or filled in by the browser. The workload table, its 80% cutoff and the existing workload bands are unchanged.

## Implemented in

Commit `164d85ebf` ("WIP: preserve Codex simulation-actions and review-screens work (unreviewed)") on branch `codex/simulation-actions-20261102`, being integrated onto `main` 702a6aa1 in worktree `.claude/worktrees/sim-actions-integrate` (2026-11-10). This record does not claim that review or release has happened.

## Owner decision 2026-11-10: shared period-by-period check (K-SAI-2)

The plan's "Give unchecked and inconclusive results their own states" is narrowed for the shared period-by-period Result check. The owner was asked whether a period whose check could not finish (an error, or not enough simulation runs) should show "INSUFFICIENT EVIDENCE" while the Decision counts it as failed, and chose:

> Show FAIL + reason (Recommended)

Such periods now show FAIL with the existing approved reason text (`decision.status.insufficient_evidence`), so the check agrees with the Decision's failed periods. Backend and Decision logic are unchanged. Independent review: Kyoya PASS (source and automated gates), 2026-11-10.
