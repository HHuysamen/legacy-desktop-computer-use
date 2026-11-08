# LedgerDesk: computer use beyond the browser

A Python demo of an OpenAI agent operating native desktop applications through screenshots, mouse clicks and keyboard input. It covers reporting, record maintenance and import in a fictional finance app, plus spreadsheet and document tasks in LibreOffice. Separate verifiers check saved outputs and permitted state changes.

LedgerDesk is a real Tkinter desktop window inside an isolated Linux desktop. The browser viewer shows that desktop; it is not the application, and the agent receives no browser DOM or application API.

**Question:** When a business application has no usable integration, can an AI agent generate and export a correct report using only what a person sees on screen?

## Validation status

On 8 November 2026, the expanded evaluation completed **100 attempts across ten tasks: 99 passed and one failed**. Each task has ten attempts. This combines the original 24 reporting runs with 76 new runs. All 99 recorded successes passed an independent artifact recheck.

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

The first Calc attempt was stopped by a driver boundary check on a native format dropdown. It remains in the denominator. The boundary was corrected before the remaining 63 new attempts; the nine later Calc attempts passed. Source revisions and the change are recorded in the [methodology](docs/evaluation-methodology.md).

Total estimated model API cost: **USD 5.039898**; mean **USD 0.050399 per attempt**. The 76 new attempts cost USD 4.161524. A 20-workday month at the overall mean projects to about **USD 1.01**, excluding hosting and operating costs. The [cost calculation](examples/evaluation-100/cost-analysis.json) also reports cost per verified success and per task.

**[Read the article](https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/)** · **[Open the 100-run evaluation](examples/evaluation-100/index.html)** · [Research and methodology](docs/evaluation-methodology.md) · [Twenty use-case categories](docs/desktop-use-cases.md) · [Watch the narrated demo](examples/presentation/demo-narrated-v2.mp4)

The study uses `gpt-6.1-terra`, OpenAI Python SDK 3.31.0, a Linux arm64/X11 guest at 1200×900, the fictional Tkinter app, and unmodified LibreOffice Calc and Writer. Inputs and layouts are fixed, and there is no interactive operator correction during measured runs. This is an iterative system evaluation, not a general reliability benchmark.

The [original nine-run package](examples/evaluation/index.html) and [24-run package](examples/evaluation-24/index.html) remain unchanged. The earlier pilot is excluded from all 100-run statistics. See [validation](docs/validation.md), [independent recheck](examples/evaluation-100/independent-recheck.json) and [artifact hashes](examples/evaluation-100/manifest.json).

## Follow-up evidence

The separate follow-up adds input/layout variation, explicit stopping controls and native GnuCash tasks. These results do not replace or extend the denominator of the original 100-attempt study.

| Cohort | Verified outcomes | Estimated model cost |
| --- | ---: | ---: |
| Calc and Writer: new files, two window geometries | 24 / 24 business tasks | USD 1.936222 |
| Foreign focus, missing source, duplicate receipt | 6 / 6 expected control responses | USD 0.071808 |
| Original GnuCash | 0 / 9 business tasks | USD 0.242528 |
| Repaired GnuCash | 9 / 9 business tasks | USD 0.719760 |

Every original GnuCash attempt stopped when the model supplied `Tab` and the driver required `TAB`. A host-side correction normalizes ASCII key names while retaining the guest allowlist. The repaired cohort repeats the same nine fixtures after that observed failure; it is a repair validation, not new held-out evidence. All nine successful saved books passed an independent check of the requested transaction, balanced splits and preserved starting state.

All 12 Office input/instruction pairs passed at both window sizes. All follow-up attempts recorded zero operator interventions. Total model cost across these 48 slots was **USD 2.970318**, including controls and failed attempts. GnuCash runs as a native Linux application; no Windows or production-accounting reliability is claimed. The requested API model identifier is recorded, rather than a verified immutable provider-weight snapshot.

**[Read the follow-up report](https://www.henryhuysamen.com/demos/ledgerdesk/follow-up/)** · [Office archive](examples/robustness-30/index.html) · [Original GnuCash archive](examples/gnucash-9/index.html) · [Repaired GnuCash archive](examples/gnucash-9-repaired/index.html) · [Detailed results](docs/follow-up-results.md) · [Reproduction](docs/follow-up-reproduction.md)

![The native LedgerDesk fixture, before a task starts](examples/ledgerdesk.png)

## What the demo does

| Task | Required result |
| --- | --- |
| `monthly-revenue` | September 2026 net invoiced revenue by customer, descending, excluding voided invoices. |
| `overdue-invoices` | Outstanding invoice balances due before the supplied date, including partial payments. |
| `reconciliation-exceptions` | Transactions whose absolute recorded-versus-expected difference exceeds USD 0.01. |
| `invoice-lookup` | Exact invoice details, without changing records. |
| `customer-update` | Only the specified contact fields change. |
| `invoice-entry` | Create one correct draft invoice; existing records stay unchanged. |
| `payment-entry` | Record one synthetic receipt and its remaining balance; no transfer. |
| `csv-import` | Import three drafts while preserving leading-zero references. |
| `calc-sort-export` | Sort an actual Calc sheet numerically and export all rows as CSV. |
| `writer-find-replace` | Replace specified text in Writer and save an ODT copy. |

All companies, invoices and transactions are synthetic. The seed contains 6 customers, 25 invoices and 9 reconciliation transactions. See [report semantics](docs/report-semantics.md) for exact definitions and edge cases.

## Quick start

Requirements: Python 3.11 or newer, Docker with Docker Compose v2, and an OpenAI API account with access to the configured computer-use model for agent runs. Opening and using the fixture manually does not require an API key.

The supported distribution is a source clone with an editable installation, so the Docker files remain available beside the Python package. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ledgerdesk desktop
```

The first desktop start builds the Linux image and installs its GUI dependencies. Open the printed viewer URL:

<http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale>

Try the app manually: choose a report, enter its parameters, click **Run Report**, then **Export CSV…** and **Save CSV**. The native window and its export confirmation remain inside the guest desktop.

The viewer is bound to localhost and intentionally has no authentication. It is for a trusted single user on the local machine; do not expose its port through a tunnel or public interface.

## Run the agent

Copy the configuration example and add your own API key locally:

```bash
cp .env.example .env
```

Keep `.env` private. The host runner reads it; the desktop container does not receive the key. The default model is `gpt-6.1-terra`; model access is checked by the actual API request, and an unavailable model is recorded as a blocked or failed attempt rather than replaced with a scripted demonstration.

```bash
python -m ledgerdesk run --task monthly-revenue
python -m ledgerdesk run --task overdue-invoices --as-of 2026-10-15
python -m ledgerdesk run --task reconciliation-exceptions
python -m ledgerdesk run --task customer-update
python -m ledgerdesk run --task calc-sort-export --max-requests 30 --max-actions 80 --timeout 420
python -m ledgerdesk run --task writer-find-replace --max-requests 30 --max-actions 80 --timeout 420
```

Each attempt starts a fresh seeded guest. Keep the viewer open to watch; avoid sending your own mouse or keyboard input during the run.

For explicit operating limits:

```bash
python -m ledgerdesk run \
  --task monthly-revenue \
  --model gpt-6.1-terra \
  --budget-usd 2 \
  --max-actions 40 \
  --max-requests 20 \
  --timeout 300
```

The budget is an estimated API-cost guard, not a provider billing cap. Standard rates were checked against [OpenAI pricing](https://developers.openai.com/api/docs/pricing) on 8 November 2026. The estimate applies those rates to reported input and output tokens; cache reads, cache writes and provider billing rules can change the actual charge. An in-flight request can complete after the estimate approaches its limit. The time limit is cooperative: an already-running desktop operation can take up to its 30-second transport timeout; subsequent actions are refused.

Every attempt produces a directory under `output/runs/`. Open its `report.html` to review the task, independent verification, CSV preview, captured screenshots, action trace, timing and available usage information. The HTML embeds its images and can be shared as one file after reviewing its contents.

To recheck an existing run and regenerate its evidence report:

```bash
python -m ledgerdesk verify --run-dir output/runs/<run-id>
```

To collect repeated attempts across the three original reporting tasks:

```bash
python -m ledgerdesk evaluate --repeats 3 --budget-usd 20
```

A run's budget applies to that attempt. The evaluation budget applies to the whole suite, with each attempt limited to the smaller of USD 2 or the estimated remaining suite budget.

The published study is retained in `examples/evaluation-100/`. Local campaign files under `output/` are ignored by Git. The fixed extension script, `scripts/extend_evaluation.py`, expects the original local 24-run campaign and resumes its remaining slots without replacing completed ones. Fresh clones can reproduce individual tasks with the CLI above; preserve those new results as a separate campaign.

A verified successful attempt establishes that the exported CSV was correct for that fixture and configuration. Repeated runs provide a small, visible sample; they do not establish general reliability across applications, operating systems or model versions. Preserve failed attempts when reporting results.

Stop the local desktop when finished:

```bash
python -m ledgerdesk stop
```

## How it is separated

```text
Host: task + OpenAI Responses API / ComputerToolset
                      │
           screenshots ↕ allowed mouse/keyboard actions
                      │
Guest: native LedgerDesk window → CSV export
                                      │
Host: independent CSV verifier ← copied export
                      │
             HTML report + event trace
```

- **Fixture:** Tkinter, SQLite and seeded business rules create the visible reports. The app deliberately has no report-export API for the agent.
- **Agent:** The configured OpenAI computer tool makes visual decisions. Its only computer actions go through the fixed desktop driver. It cannot query the database, inspect Tk widgets, read files, execute a shell or use the verifier.
- **Trusted controller:** Starts the guest, captures screenshots, executes allowed inputs, enforces limits and retrieves the exported file. Its fixed infrastructure commands are not model-selected tools.
- **Verifier:** Independently queries the seeded records and compares CSV columns, row count, values, ordering and uniqueness. It does not call the app's report-generation function. A model's completion message never counts as a pass.

The guest runs as a non-root user, without host bind mounts or API credentials, with a read-only container filesystem and temporary writable data. Its desktop network is configured as internal. Window identity and focus are checked before and after actions; out-of-window coordinates and unsupported actions or key combinations are rejected. These controls bound this demonstration to the included applications. LibreOffice has automation APIs, but none are exposed to the agent.

One host process owns the desktop at a time; competing lifecycle commands fail rather than reset an active run. At startup the controller binds Tk's X11 window to the process it launched, because Tk does not supply that property itself. The agent cannot change that binding.

The viewer is only a way for a person to observe the native desktop. The agent does not control it with Playwright, Selenium or DOM selectors.

## Development and tests

```bash
python -m pytest
```

The deterministic tests require no API access. They cover fixture reset, reporting rules, CSV verification, export behavior, evidence rendering and applicable driver boundaries. A passing test suite is separate from live model validation.

GitHub Actions is configured to run these tests on Python 3.11 and 3.13, without an API key. Installing dependencies requires network access; the tests themselves use local data and mocked API responses.

The optional host-native fixture can be opened with:

```bash
python -m tkinter
python -m ledgerdesk fixture
```

This requires a Python installation with Tk support and a graphical session. It is for manual inspection. The supported agent path uses the isolated Linux desktop; direct macOS agent control is not claimed, and Windows support has not been validated.

## Troubleshooting

- **Docker cannot connect:** Start your Docker engine, then retry `python -m ledgerdesk desktop`. The first image build needs network access to download dependencies.
- **Docker subnet collision:** The demo uses `10.239.20.0/24` and `10.239.21.0/24` to avoid exhausting Docker's automatic address pools. Override `LEDGERDESK_DESKTOP_SUBNET` and `LEDGERDESK_VIEWER_SUBNET` in your shell if those ranges overlap local networks.
- **Viewer is blank:** Wait for the desktop health check to pass and refresh the viewer. Inspect `docker compose logs desktop viewer` if startup fails.
- **The run stops after a click or keypress:** Check the evidence trace. Closing the app, changing focus or sending unsupported inputs intentionally stops execution. Start a fresh attempt.
- **Authentication, model or quota error:** Check the local `.env`, your API account's model access and quota. Never paste the key into an issue or a saved report.
- **The model reports success but verification fails:** Treat the run as failed. Inspect the exported CSV and trace; do not substitute a deterministic export and label it an agent result.
- **The optional native fixture reports a Tk error:** Use the container desktop or a Python build with Tk support. Native host setup is not needed for the container agent path.

## Source map and references

`desktop_app.py` owns the fixture window and GUI export; `computer_agent.py` owns the model loop; `desktop_driver.py` and `guest_control.py` own the fixed transport and bounded inputs; `verify.py` owns the independent oracle; `html_report.py` renders saved evidence. `fixtures/seed.json` is the canonical synthetic dataset.

The implementation follows the current official [computer-use guide](https://developers.openai.com/api/docs/guides/tools-computer-use), [integration guide](https://developers.openai.com/api/docs/guides/tools-computer-use-integration) and [SDK driver guide](https://developers.openai.com/api/docs/guides/tools-computer-use-sdk-drivers). Recheck model availability and pricing before rerunning published examples.

Licensed under [MIT](LICENSE). Copyright © 2026 Henry Huysamen.
