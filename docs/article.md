# When browser agents aren't enough: automating a native desktop application

Many business workflows still end with someone at a desktop application: select a report, enter a date, inspect the preview and save a file. When the application exposes only a graphical interface, those ordinary steps become an automation problem.

I built LedgerDesk to investigate a narrow question: **can an AI agent generate and export the right business report using only what a person sees on screen?**

LedgerDesk is a fictional finance application built with Python and Tkinter. It has a report selector, parameter fields, a results table and a CSV export confirmation. Its familiar interface and synthetic data make the workflow easy to follow without customer information or production credentials.

The project separates model decisions, executed actions and independent verification.

## A native window, viewed through a browser

The application runs in an isolated Linux desktop inside Docker. A local noVNC viewer lets a person watch or operate that desktop from a browser. Tkinter still draws the actual application window.

The agent has no DOM, browser selectors or application API. It receives screenshots and chooses clicks, typing, keypresses and scrolling through the OpenAI Responses computer tool. The SDK's `ComputerToolset` connects to a small desktop driver, following the official [integration](https://developers.openai.com/api/docs/guides/tools-computer-use-integration) and [driver guidance](https://developers.openai.com/api/docs/guides/tools-computer-use-sdk-drivers).

The controller translates those requested actions into input on the guest desktop. Fixed infrastructure code starts the environment and retrieves an exported file, but the model cannot select shell commands or use those infrastructure operations as tools. To complete the task, it must navigate the visible application.

## Three ordinary tasks with useful edge cases

The fixture contains 6 fictional customers, 25 invoices and 9 reconciliation transactions. That is enough to make an incorrect report plausible and detectable.

The first task is monthly revenue by customer for September 2026. It uses net invoice amounts and excludes voided invoices. Invoices immediately outside the month test date boundaries, while equal customer totals require a deterministic tie-break.

The second is an overdue-invoice report as of October 15, 2026. It must include partially paid invoices at their outstanding balance, exclude invoices due on the as-of date and calculate calendar days overdue.

The third identifies reconciliation differences strictly greater than USD 0.01. Positive and negative one-cent differences are excluded; two-cent differences are included. The export preserves the sign of recorded amount minus expected amount.

Money is stored as integer cents. The [report definitions](report-semantics.md) make the assumptions explicit, including a deliberate limitation: payments are a fixture snapshot, not a history from which arbitrary past balances can be reconstructed.

## Making success independently checkable

A model saying “the report has been exported” is a claim to examine. It is not the acceptance criterion.

After a completed attempt, trusted code retrieves the expected CSV from the fresh guest. A separate verifier constructs the expected result from a newly seeded database. It uses independent queries and formatting rather than calling the application's report-generation function.

Verification checks exact column names and order, row count, row ordering, identifiers and values. Missing records, duplicate identifiers, changed amounts and extra columns fail. The model cannot access the verifier, reference data or expected answers.

This still leaves an important boundary. Correct CSV content alone does not establish that the agent used the GUI. That claim depends on the controller's restricted tool surface, the fresh environment and the captured screenshots and actions. The project records both kinds of evidence.

## Constraining the demonstration

The computer belongs to the demo. The guest receives no host directory mounts or API key, uses a non-root account and has a read-only base filesystem with temporary writable data. Its desktop network is internal; API requests are made by the host process.

Before and after an input, the driver checks the expected window and its focus. It rejects coordinates outside the application, unsupported actions, long text inputs and unapproved key combinations. The model's instructions also treat screen text as untrusted task data.

Each attempt has action, request, time and estimated-cost limits. A pending safety approval stops the run. So do lost focus, missing observations and execution errors. Cost estimates are recorded when usage is available, and missing usage prevents continued spending based on a guessed balance. Provider billing remains authoritative.

These controls bound the exercise to its fixture. The local viewer is for a trusted single user, not a public remote desktop service.

## Evidence a reader can inspect

Each attempt produces a standalone HTML report with its task, outcome, CSV preview, screenshots, event trace, timing and available usage information. Model completion text is displayed separately from independent verification. The runner also attempts to record the guest desktop as a video.

The [evaluation gallery](../examples/evaluation/index.html) contains the recorded attempts. Watch a [model-operated desktop run](../examples/evaluation/demo.mp4), open its [standalone evidence report](../examples/evaluation/sample-report.html), or inspect the [machine-readable results](../examples/evaluation/summary.json) and [artifact hashes](../examples/evaluation/manifest.json). The [source repository](https://github.com/HHuysamen/legacy-desktop-computer-use) contains the fixture, controller and verifier.

## Nine evaluated runs, nine verified exports

On 8 November 2026, I ran each task three times using `gpt-6.1-terra` and OpenAI Python SDK 3.31.0. Every attempt began in a fresh, seeded guest with blank parameter fields. All nine exports passed verification and a subsequent independent recheck.

| Task | Verified | Median elapsed | Estimated cost, three runs |
| --- | ---: | ---: | ---: |
| Monthly revenue | 3/3 | 27.853 s | USD 0.106752 |
| Overdue invoices | 3/3 | 25.875 s | USD 0.118259 |
| Reconciliation exceptions | 3/3 | 25.214 s | USD 0.107082 |

The nine-run median was **25.481 seconds**, with 7–8 desktop actions and 6–7 model requests per attempt. There were no failed or blocked attempts in this evaluation. The combined standard-rate API estimate was **USD 0.332093**. Cache read/write effects and provider billing may change the actual charge.

One overdue-invoice run scrolled the results table before exporting, accounting for its eighth action. The live input decisions came from model computer-tool calls, not a fixed macro.

A successful pilot, excluded from the table, added USD 0.035597: **USD 0.367690** estimated across ten funded runs. Earlier missing-key and quota blocks are retained separately; they were setup failures before agent interaction, not part of the nine-run evaluation. Their missing usage is not treated as zero cost.

The live environment was a Linux arm64/X11 guest at 1200×900, running Python 3.12 under Docker Engine 29.9.1 on macOS 26.6.2/Apple silicon, with Python 3.13 on the host. Separately, 96 automated tests passed locally, and the initial CI run passed on Python 3.11 and 3.13.

This is evidence of repeatability for one fixed dataset, layout and environment. It does not test unfamiliar applications, changing screen layouts or long workflows. Those are separate experiments.

## The business question behind the demo

The useful question is whether a constrained workflow can produce a result that another system can verify at an acceptable cost. For this experiment, CSV output gives us that verification boundary, and the small fixture lets readers understand every expected result.

Before extending the approach to a real application, I would examine its supported integrations, data exposure, operating permissions, failure recovery and the cost of human review. LedgerDesk provides a reproducible place to test the mechanics first—and a way to show exactly which parts succeeded when a live attempt is complete.
