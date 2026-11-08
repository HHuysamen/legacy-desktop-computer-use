# When browser agents aren't enough: automating a native desktop application

Many useful business workflows still end with a person sitting in front of a desktop application: select a report, enter a date, inspect the preview and save a file. A supported integration can make that work straightforward. When an application exposes only its graphical interface, the automation problem changes.

I built LedgerDesk to investigate a narrow question: **can an AI agent generate and export the right business report using only what a person sees on screen?**

LedgerDesk is a small, fictional finance application built with Python and Tkinter. It has a report selector, date and tolerance fields, a results table and a CSV export confirmation. All its data is synthetic. The deliberately familiar interface makes the workflow easy to follow without introducing a real accounting system, customer information or production credentials.

The project separates three things that are often blurred in AI demonstrations: what the model decided, what the software actually did and what independent checks can establish.

## A native window, viewed through a browser

The application runs in an isolated Linux desktop inside Docker. A local noVNC viewer lets a person watch or operate that desktop from a browser. Tkinter still draws the actual application window.

That distinction matters. The agent has no DOM, browser selectors or application API. It receives screenshots and chooses coordinate-based clicks, typing, keypresses and scrolling through the OpenAI Responses computer tool. The implementation uses the SDK's `ComputerToolset` with a small desktop driver, following the official [computer-use integration](https://developers.openai.com/api/docs/guides/tools-computer-use-integration) and [driver guidance](https://developers.openai.com/api/docs/guides/tools-computer-use-sdk-drivers).

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

These controls give the exercise a defined boundary. They do not establish that arbitrary desktop automation is safe. The local viewer is intended for a trusted single user and is not a public remote desktop service.

## Evidence a reader can inspect

Each attempt produces a standalone HTML report with its task, outcome, CSV preview, screenshots, event trace, timing and available usage information. Model completion text is displayed separately from independent verification. The runner also attempts to record the guest desktop as a video.

The intended website presentation combines this article with a standalone evidence report and a short desktop recording. Those release assets must come from a captured model run before publication. A source repository accompanies the article so readers can inspect the controls and reproduce the experiment.

## Live results pending

At the time of this draft, **85 automated tests pass locally**. They exercise report rules, fixture reset, CSV verification, export behavior, evidence rendering and mocked computer-tool interactions. All three reports have also been exported through the actual native GUI and independently verified using scripted plumbing checks. Those checks establish that the application and driver work; they do not measure model performance. GitHub Actions is configured for Python 3.11 and 3.13 without an API key.

Live model results remain pending. This section will report the tested environment, model, number of attempts per task, verified outcomes, failures, timings and available cost estimates after execution. A successful run will show that this particular task completed correctly under its recorded conditions. Any broader claim will require further evidence.

## The business question behind the demo

The useful question is whether a constrained workflow can produce a result that another system can verify at an acceptable cost. For this experiment, CSV output gives us that verification boundary, and the small fixture lets readers understand every expected result.

Before extending the approach to a real application, I would examine its supported integrations, data exposure, operating permissions, failure recovery and the cost of human review. LedgerDesk provides a reproducible place to test the mechanics first—and a way to show exactly which parts succeeded when a live attempt is complete.
