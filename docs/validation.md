# Validation snapshot — 8 November 2026

## Expanded evaluation

**100 attempts, ten per task: 99 passed, one failed, none blocked.** All 99 recorded passes survived a separate read-only artifact recheck. The original 24 runs were retained and 76 new attempts added; the earlier pilot is excluded.

| Task | Verified runs | Median time | Average API cost |
| --- | ---: | ---: | ---: |
| Monthly revenue | 10 of 10 | 26.7 s | US$0.036 |
| Overdue invoices | 10 of 10 | 26.7 s | US$0.040 |
| Reconciliation exceptions | 10 of 10 | 25.3 s | US$0.036 |
| Invoice lookup | 10 of 10 | 25.3 s | US$0.046 |
| Customer contact update | 10 of 10 | 28.1 s | US$0.047 |
| Draft invoice entry | 10 of 10 | 31.8 s | US$0.047 |
| Receipt recording | 10 of 10 | 29.5 s | US$0.047 |
| CSV import | 10 of 10 | 26.1 s | US$0.046 |
| Calc sort and export | 9 of 10 | 57.5 s | US$0.117 |
| Writer text replacement | 10 of 10 | 35.7 s | US$0.042 |

The 100 attempts used 7–23 desktop inputs and 6–12 model requests each. Overall median elapsed time was 27.880 seconds, including desktop setup and verification. The model was `gpt-6.1-terra`, SDK 3.31.0, Linux arm64/X11 at 1200×900, and LibreOffice 7.4 for the two Office tasks. All data and source documents are synthetic.

## The retained failure and source cohorts

The first Calc run, `20261108T125117-bdb21f`, was stopped at the Save As format dropdown because the driver limited input to the active dialog's rectangle. The dropdown extended below it. The driver was corrected to allow the owned application's area while retaining process/focus checks. An API-free GUI smoke test verified the correction before measured work resumed.

- Historical report cohort: 24/24 passed; unchanged prior archive.
- First expansion cohort, `c523e53`: 12/13 passed.
- Corrected expansion cohort, `e041a50`: 63/63 passed.

The failed attempt was not replaced. This is an iterative evaluation of fixed tasks, not 100 trials of one frozen driver. See the [methodology](evaluation-methodology.md) and [use-case selection](desktop-use-cases.md). There are no held-out inputs, layout perturbations, production accounts or human/API baselines.

## Cost

The combined model API estimate is **USD 5.039898**, including the failure: USD 0.05039898 per attempt, or USD 0.05090806 per verified success. The old 24 cost USD 0.878374 and the new 76 cost USD 4.161524, below the USD 20 extension allowance.

At one attempt per workday, the equally weighted task average projects to USD 1.007980 for 20 workdays. Per-task projections range from about USD 0.71 for a simple report to USD 2.35 for Calc. These are standard-rate token estimates, not invoices; cache discounts, hosting, implementation and media production are excluded. All 100 attempts returned complete token usage. The earlier pilot cost USD 0.035597 and remains excluded.

## Evidence and checks

- [100-attempt gallery](../examples/evaluation-100/index.html), [summary](../examples/evaluation-100/summary.json), [cost details](../examples/evaluation-100/cost-analysis.json), [independent recheck](../examples/evaluation-100/independent-recheck.json), [SHA-256 manifest](../examples/evaluation-100/manifest.json).
- The [original nine-run](../examples/evaluation/index.html) and [24-run](../examples/evaluation-24/index.html) packages remain unchanged.
- Workflow checks compare complete database state and exact audit CSVs. Office checks examine saved CSV/ODT content and original-source hashes. The model cannot call the verifier.
- **220 unit and integration tests passed locally.** These cover business rules, atomic/duplicate handling, independent oracles, native window/PID/focus bounds, popup handling, limits, packaging and study accounting. See CI for the current test result.
- Presentation reports were regenerated after execution to add companion-file links and label non-CSV output correctly; raw run records, actions, screenshots and exports were not changed.
- Desktop containers were stopped after the completed study. Credentials are excluded from source, evidence and the guest desktop.
