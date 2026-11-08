# Validation snapshot — 8 November 2026

This snapshot separates code checks, real desktop checks and model evidence.

## Completed

- Editable installation succeeded; `pip check` found no broken requirements.
- 85 tests passed on host Python 3.13. Tests cover exact report rules, independent CSV validation, fixture reset, safe export, HTML escaping, driver bounds/focus/PID checks, operating limits, missing usage, safety stops and exclusive desktop ownership.
- The Linux arm64 guest built and became healthy under Docker Engine 29.9.1 on macOS 26.6.2/Apple silicon. It runs Python 3.12 and a real Tkinter window on X11.
- Screenshot and coordinate-input transport worked against the actual window. Parameters start blank. The confirmation controls and footer remain visible at the fixed window size.
- Scripted GUI smoke checks selected each report, typed its parameter, ran the report and used both export controls. The resulting CSVs independently matched 6 monthly revenue rows, 7 overdue rows and 4 reconciliation rows.
- A guest-only MP4 was recorded and checked with ffprobe. The final two-report smoke recording was 10.125 seconds. This is plumbing footage, not an AI demonstration.
- The localhost viewer served HTTP 200 and upgraded a WebSocket that delivered the VNC protocol handshake.
- An external socket attempt from the guest returned network-unreachable (101). The desktop uses an internal Docker network; no host directory or API key is mounted into it.
- A real CLI attempt without credentials stopped before any API request and generated the [setup-blocked report](../examples/setup-blocked-report.html).

Local raw smoke artifacts are kept under ignored `output/final-gui-check/`, including screenshots, CSVs, `validation.json` and recording. Earlier debugging captures are also retained under `output/`.

## Not yet completed

- No live OpenAI call has been made. The project has no configured API key in this environment. API cost incurred here: USD 0.
- Model access, end-to-end AI completion and the planned three attempts per report remain unverified.
- The article's live-results section, agent recording and successful standalone sample report remain pending those runs.
- GitHub Actions has not run. Other hosts, Linux x86-64 and direct macOS desktop control have not been tested.
- Repository publication and website integration have not occurred. Keep the project private until the live evidence is complete.

## Resume

Configure `OPENAI_API_KEY` in the ignored repository `.env` file, then run:

```bash
python -m ledgerdesk run --task monthly-revenue --budget-usd 2
python -m ledgerdesk evaluate --repeats 3 --budget-usd 20
```

Keep every attempt, including failures. After reviewing the nine outcomes, select one verified agent recording and report for the article. A scripted smoke run must never be relabelled as model evidence.
