# Validation snapshot — 8 November 2026

This snapshot separates code checks, real desktop checks and model evidence.

## Completed

- Editable installation succeeded; `pip check` found no broken requirements.
- 92 tests passed on host Python 3.13. Tests cover exact report rules, independent CSV validation, fixture reset, safe export, HTML escaping, driver bounds/focus/PID checks, operating limits, missing usage, safety stops, API error classification and exclusive desktop ownership.
- The Linux arm64 guest built and became healthy under Docker Engine 29.9.1 on macOS 26.6.2/Apple silicon. It runs Python 3.12 and a real Tkinter window on X11.
- Screenshot and coordinate-input transport worked against the actual window. Parameters start blank. The confirmation controls and footer remain visible at the fixed window size.
- Scripted GUI smoke checks selected each report, typed its parameter, ran the report and used both export controls. The resulting CSVs independently matched 6 monthly revenue rows, 7 overdue rows and 4 reconciliation rows.
- A guest-only MP4 was recorded and checked with ffprobe. The final two-report smoke recording was 10.125 seconds. This is plumbing footage, not an AI demonstration.
- The localhost viewer served HTTP 200 and upgraded a WebSocket that delivered the VNC protocol handshake.
- An external socket attempt from the guest returned network-unreachable (101). The desktop uses an internal Docker network; no host directory or API key is mounted into it.
- A real CLI attempt without credentials stopped before any API request and generated the [setup-blocked report](../examples/setup-blocked-report.html).
- The private [GitHub repository](https://github.com/HHuysamen/legacy-desktop-computer-use) was created and the source pushed. The [initial CI run](https://github.com/HHuysamen/legacy-desktop-computer-use/actions/runs/42456016582) passed on Python 3.11 and 3.13.

Local raw smoke artifacts are kept under ignored `output/final-gui-check/`, including screenshots, CSVs, `validation.json` and recording. Earlier debugging captures are also retained under `output/`.

## Not yet completed

- The first live monthly-revenue attempt made one request but was rejected with HTTP 429 before any desktop action. A separate minimal diagnostic confirmed `credit_balance_exhausted` / `insufficient_quota`. The configured API project needs credits. No response usage was supplied, so no numerical cost estimate is claimed. Raw evidence is retained in ignored `output/runs/20261108T064431-28cc89/` and `output/api-preflight.json`.
- Model access, end-to-end AI completion and the planned three attempts per report remain unverified.
- The article's live-results section, agent recording and successful standalone sample report remain pending those runs.
- Other desktop hosts, Linux x86-64 desktop execution and direct macOS desktop control have not been tested. CI's Python checks do not validate their native desktop behavior.
- Public repository publication and website integration have not occurred. Keep the repository private until the live evidence is complete.

## Resume

Fund the configured API project or replace `OPENAI_API_KEY` in the ignored repository `.env` with a funded project's key, then run:

```bash
python -m ledgerdesk run --task monthly-revenue --budget-usd 2
python -m ledgerdesk evaluate --repeats 3 --budget-usd 20
```

Keep every attempt, including failures. After reviewing the nine outcomes, select one verified agent recording and report for the article. A scripted smoke run must never be relabelled as model evidence.
