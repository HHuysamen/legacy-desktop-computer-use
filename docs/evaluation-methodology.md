# Evaluation methodology: 100 desktop attempts

Protocol: `expanded-100-v1`. The completed evaluation contains 100 attempts: 99 verified passes and one retained failure. All 99 passes were independently rechecked. The [historical 24-run evaluation](../examples/evaluation-24/index.html) is complete and preserved separately. The 76 added attempts produced 75 passes and one failure. The result table and artifacts are in the [100-run gallery](../examples/evaluation-100/index.html).

## Composition and purpose

The completed set contains ten attempts for each of ten fixed tasks:

| Task ID | Application | Historical attempts | New attempts | Fixed task |
| --- | --- | ---: | ---: | --- |
| `monthly-revenue` | LedgerDesk | 8 | 2 | Export September 2026 net invoiced revenue by customer, excluding voids. |
| `overdue-invoices` | LedgerDesk | 8 | 2 | Export unpaid balances due before 15 October 2026. |
| `reconciliation-exceptions` | LedgerDesk | 8 | 2 | Export signed discrepancies with absolute difference greater than USD 0.01. |
| `invoice-lookup` | LedgerDesk | 0 | 10 | Find `INV-260916` and export its details without changing records. |
| `customer-update` | LedgerDesk | 0 | 10 | Update customer 2's email to `billing@beacon.example` and phone to `+1-555-0142`. |
| `invoice-entry` | LedgerDesk | 0 | 10 | Create draft `DRAFT-261101` for customer 3: 1 November 2026, due 1 December, USD 1,250.50. |
| `payment-entry` | LedgerDesk | 0 | 10 | Record synthetic receipt `RCPT-1001`, USD 125.25, against `INV-260916`; transfer no funds. |
| `csv-import` | LedgerDesk | 0 | 10 | Import the fixed three-row `invoices.csv`; preserve references `000101`–`000103`. |
| `calc-sort-export` | LibreOffice Calc | 0 | 10 | Sort the eight-row receivables table by balance descending, then invoice ID ascending; export CSV. |
| `writer-find-replace` | LibreOffice Writer | 0 | 10 | Replace exact `Harbor Systems` occurrences with `Northstar Devices`; preserve near-matches and other content; save ODT. |
| **Total** | **Eight demo-app tasks, two Office tasks** | **24** | **76** | **100 completed attempts** |

The seven additions were selected for distinct interactions: lookup, editing, record creation, receipt allocation, import, spreadsheet manipulation and document editing. See the [use-case research](desktop-use-cases.md). They are not sampled from a measured population of business tasks, and this is not an OSWorld or Windows Agent Arena benchmark result.

## Fixed conditions and human involvement

The model is `gpt-6.1-terra` through OpenAI Python SDK `3.31.0`. Applications run in an isolated Linux/X11 desktop at 1200×900. The model receives the task and screenshots and requests bounded mouse/keyboard actions. It has no DOM, widget inspection, SQL, shell, filesystem-reading or LibreOffice UNO tool.

People engineer the fixture, driver, task wording and verifier. They may perform manual or scripted smoke checks before freezing the new evaluation. During each measured attempt, the model chooses the actions autonomously; the operator does not supply corrective clicks, keyboard input or task hints. Safety and error stops remain enabled.

Each new attempt starts with a fresh guest, reset synthetic records, or newly prepared Office input documents. The same task parameters are repeated ten times per case; this is **not** a held-out-input or layout-perturbation study. Repetition measures consistency on those fixed inputs, not adaptation to unfamiliar workflows.

Freeze the implementation before the 76 new measured attempts and record its source revision, container image ID, fixture hash, applicable input-file hash and application version. The historical 24 attempts retain their original metadata and builds. Do not describe all 100 as having an identical application build or UI: the original reports were recorded before the new workflows were added. If implementation changes during the new evaluation, retain the affected attempts and disclose the change and cohorts.

The canonical inputs are in [tasks.py](../ledgerdesk/tasks.py), [workflows.py](../ledgerdesk/workflows.py) and [office_tasks.py](../ledgerdesk/office_tasks.py). Record their frozen revision alongside the run evidence.

## Verification and retained evidence

A model completion is not a pass. Trusted code checks the output after the model loop; it is not available as an agent tool.

- Original reports require the exact expected CSV schema, row order and values, using the [independent report verifier](../ledgerdesk/verify.py).
- Lookup requires the correct invoice details and an unchanged database.
- Contact, draft, receipt and import tasks require the expected audit CSV **and** the exact allowed database changes. Unrelated records and schema must remain unchanged. Use the independent expected-state calculation, not the function that applies the UI operation.
- Calc requires all original records, the correct numeric ordering and unchanged cell values. The source ODS must remain unchanged.
- Writer requires the intended text replacement, preserved near-matches, paragraph/heading order and table content. The source ODT must remain unchanged. This checks document content and structure, not pixel-perfect rendering or byte-identical export formatting.

Retain task instructions, model and environment metadata, screenshots, input actions, response text, usage, elapsed time, verifier results and available exports. Keep final database snapshots for state-changing attempts, including failed attempts when the guest remains accessible. Office evidence includes the source-file hash and available source/output documents. If an early failure prevents an artifact from existing or being retrieved, record that limitation; do not fabricate a file or treat missing evidence as success.

The HTML report is a readable view of this record. Original files and machine-readable traces remain the evidence. A recording, when available, supplements those artifacts rather than replacing output verification.

## Counting, failures and cost

Assign the 76 new attempt slots before execution. After an attempt begins, keep it in the planned 100-attempt denominator whether it passes, fails verification, times out, reaches a limit, loses focus or is blocked by an API/safety condition. Do not replace failures with later successful attempts. Diagnostic or development retries must be labelled separately and must not silently enter the measured set.

If the suite stops early, report the planned total, completed slots and unrun slots separately. Do not label unrun slots as successes or present a completed-100 success rate.

The six original-report additions retain limits of 20 model requests, 40 desktop inputs and 300 seconds per attempt. The 70 attempts across the seven new tasks use up to 30 requests, 80 inputs and 420 seconds. **All 76 new attempts have a USD 1 per-attempt cost allowance and share a USD 20 extension allowance.** The historical 24 keep the limits recorded in their original metadata. Timeouts are cooperative; an in-progress transport operation can finish after the deadline, while subsequent actions are refused. Retain each attempt's actual configured limits in its metadata.

Use returned input/output token usage and the recorded standard-rate pricing basis to estimate **model API cost only**. Include failed measured attempts' known usage. If usage is missing, show the cost as incomplete; do not substitute zero. Keep the historical 24 costs separate from the extension subtotal as well as showing the combined measured total. Exclude the earlier pilot from the 100-attempt denominator and report any pilot/development spending separately. Hosting, implementation work and media production are not included in the model estimate. Neither the estimate nor the local guard is a provider-enforced billing cap.

Report outcomes and cost per task and per cohort, alongside the overall result. Means and medians should identify which attempts have usable measurements. An overall result can hide a weak task; ten repeated inputs also do not provide ten independent workflow examples.

## Publishing the result

Publish the measured outcomes, limitations and links to the retained evidence without claiming general business reliability. The Google Search guidance on [original, first-hand content](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide?hl=en) supports making the actual work understandable rather than manufacturing generic summaries. That guidance is about presentation and discovery; it does not validate this protocol or guarantee indexing or citations.

## Recorded protocol amendment

The first 13 new attempts ran at source revision `c523e53`. Twelve passed; the first Calc attempt (`20261108T125117-bdb21f`) stopped when selecting CSV in the native Save As file-type list. That list extends below its parent dialog, outside the driver's then-permitted active-dialog rectangle. The failed attempt remains the first of Calc's ten slots.

Before the remaining 63 slots, the driver was corrected to permit input across the owned application's window area while still requiring the active window to belong to the bound application process. A manual, API-free GUI check confirmed that the previously rejected dropdown click was accepted. Fixed task instructions and input fixtures were unchanged. Per-run source/image identifiers distinguish these two cohorts. This correction and the retained failure mean the combined result is an iterative system evaluation, not 100 trials of one frozen driver version.

## Final result

The combined estimated model API cost was USD 5.039898 (USD 4.161524 for the new 76). The first expansion cohort recorded 12/13 passes; all 63 attempts after the popup correction passed. The failed Calc attempt remains one of its ten runs. Costs, time and outcomes are available per task and source revision in the [cost analysis](../examples/evaluation-100/cost-analysis.json).
