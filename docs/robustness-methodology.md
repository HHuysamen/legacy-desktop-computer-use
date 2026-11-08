# Follow-up protocol: input and layout variation

This study is separate from the published 100-attempt demonstration. Its plan is frozen before model calls. It tests variation, operational stopping rules and a real accounting application; it does not replace any original outcome.

## Office variation study

Twenty-four positive cases: two applications (LibreOffice Calc and Writer), two input sets (development and held-out), three distinct files per set, and two window geometries. Each exact file and instruction is paired across both geometries. The two input sets have matched size and structure. There are no repeated identical-state trials in this small exploratory design.

Development fixtures may be used for unscored GUI setup checks. The held-out set is reserved from model and GUI tuning; its data is synthetic, not claimed to be unknown to the model's training process. Calc uses eight rows with numeric ties, zero and cent values. Writer uses five exact replacements plus near-matches, headings and a table.

The display remains 1200×900. The normal application is maximized; the changed application is positioned at (120,80) with a920×660 client area. Actual client geometry is recorded before each model call. An unexpected geometry is a setup failure, not a valid layout trial.

Six negative controls are scored separately, two each:

- Foreign focus: a separate process takes focus, then a driver input is attempted. The driver must refuse before any input reaches the foreign window. Both mouse and keyboard events are monitored. This tests the driver, with no model call.
- Missing source: a prepared source file is removed before the shared launch preflight. Startup must be refused. This tests controller validation, with no model call.
- Duplicate receipt: the database already contains the requested receipt. The model attempts the task through the native form. Application rejection must be recorded, and all database tables must remain unchanged. This tests application validation and the resulting workflow outcome, not payment initiation.

A successful control is an expected refusal, not a completed business task. These controls do not establish general recovery or prompt-injection resistance.

## Native GnuCash study

Nine positive cases: expense entry, a three-account split expense, and a Checking-to-Savings transfer, each with three distinct dates, descriptions and amounts. GnuCash4.13 runs as an unmodified native GTK/X11 application in the Linux guest. No Windows result is claimed. A manual development smoke check must demonstrate that the generated native book opens, an expense can be entered, and the saved book passes semantic verification.

All books contain synthetic USD accounts and a balanced opening transaction. The agent must add exactly one requested transaction and save an XML-format copy, preserving the original file. Independent checks compare book identity, accounts, the opening transaction, exact new splits and their balance. The model receives no GnuCash API, SQL, shell or file-reading tool. The displayed short-date format is supplied with each date; locale adaptation is outside this study.

## Freeze, execution and reporting

- Pin the source commit, source/configuration file hashes, container image ID, application versions, model and medium reasoning setting, fixture bytes, instructions, expected-output hashes, limits and randomized case order in a protocol file before execution.
- Use the existing OpenAI computer tool and screenshot/input driver. No operator correction is allowed during measured attempts.
- Each attempt starts from a fresh guest. Positive cases retain the input/output and before/after source hashes. State controls retain database snapshots or input-event sentinels.
- Record a durable start event before each attempt. An interrupted started slot is retained with unknown outcome/cost, never silently retried. A code, prompt, fixture or image change requires a separately identified study.
- Keep completion, safe refusal, failure and unavailable evidence distinct. Never convert a model completion message into a verified pass.
- Report per-case results, paired layout differences, actual executed inputs, requests, setup/agent/verification/total time, human intervention and model API cost per verified success. Include failed attempts in costs. Missing usage stays unknown.
- The Office campaign has aUSD20 allowance; GnuCash has aUSD10 ceiling, within the previously authorized project budget. Each attempt is bounded by USD1,30 requests,80 inputs and420 seconds. These are local guards, not provider billing caps.

The [OSWorld](https://arxiv.org/abs/2404.07972) and [Windows Agent Arena](https://microsoft.github.io/WindowsAgentArena/) designs support defined starting states and execution-based checks. This smaller experiment is not a result on either benchmark. A later study can add end-to-end application handoffs or a human baseline without confounding this input/layout comparison.
