# Validation snapshot — 8 November 2026

This snapshot separates code checks, real desktop checks and live model evidence.

## Live model evaluation

All **9 planned evaluation attempts completed and produced independently verified CSVs**, with three attempts per task. No attempt failed or was blocked within this evaluation. A subsequent independent recheck of all nine saved exports also passed.

| Task | Verified / attempted | Median elapsed | Desktop actions | Model requests | Estimated API cost, task total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Monthly revenue | 3/3 | 27.853 s | 7 | 6 | USD 0.106752 |
| Overdue invoices | 3/3 | 25.875 s | 7–8 | 6–7 | USD 0.118259 |
| Reconciliation exceptions | 3/3 | 25.214 s | 7 | 6 | USD 0.107082 |
| All evaluated runs | 9/9 | 25.481 s | 7–8 | 6–7 | USD 0.332093 |

The model was `gpt-6.1-terra`, using OpenAI Python SDK 3.31.0. Each attempt used a freshly seeded guest, the same synthetic records and the same layout at 1200×900. The host was macOS 26.6.2 on Apple silicon with Docker Engine 29.9.1 and Python 3.13. The native Tkinter window ran in a Linux arm64/X11 guest using Python 3.12.

These results establish repeatability within that fixed setup. They do not establish reliability across applications, layouts, datasets or platforms.

## Evidence and costs

The [evaluation gallery](../examples/evaluation/index.html) links to all nine reports, exported CSVs and recorded metadata. The [summary](../examples/evaluation/summary.json) includes every evaluated run and the separate pilot; the [manifest](../examples/evaluation/manifest.json) records SHA-256 hashes for packaged artifacts. The selected [video](../examples/evaluation/demo.mp4) and [standalone report](../examples/evaluation/sample-report.html) come from monthly-revenue run `20261108T084829-36a77a`, which is one of the nine evaluated attempts.

The earlier successful monthly-revenue pilot, `20261108T084740-fd252d`, is excluded from evaluation statistics. It passed independently and has a standard-rate API estimate of USD 0.035597. The nine evaluation runs total USD 0.332093, so the ten funded runs together total **USD 0.367690 estimated**.

All ten funded runs returned complete token usage. Estimates apply the configured standard input/output rates to reported usage. Cache reads, cache writes and provider billing rules may change the actual charge; these figures are not an invoice or a provider-enforced spending cap.

Earlier setup attempts are retained separately: a missing-key attempt made no API request, and quota-rejected attempts stopped before agent desktop interaction. A diagnostic returned `credit_balance_exhausted` / `insufficient_quota` before the key was replaced. These setup blocks are excluded from the nine-run denominator. No zero-cost claim is made for requests whose usage was unavailable. Their raw evidence remains in ignored local `output/`; the [credential-free setup report](../examples/setup-blocked-report.html) is included as a distinct failure example.

## Code and desktop checks

- Editable installation succeeded; `pip check` found no broken requirements.
- **96 tests passed locally** on host Python 3.13, covering reporting rules, independent CSV validation, fixture reset, safe export, HTML escaping, driver bounds/focus/PID checks, operating limits, missing usage, safety stops, API error classification, exclusive desktop ownership and evidence packaging.
- The [initial GitHub Actions run](https://github.com/HHuysamen/legacy-desktop-computer-use/actions/runs/42456016582) passed on Python 3.11 and 3.13. That earlier CI run is distinct from the final local 96-test result.
- The Linux guest built and became healthy, with a real Tkinter window on X11. Parameters started blank; export controls remained visible at the fixed size.
- Before model evaluation, scripted GUI smoke checks exported all three reports. Their CSVs matched 6 monthly revenue rows, 7 overdue rows and 4 reconciliation rows. Those smoke checks tested plumbing and are not counted as AI evidence.
- A guest-only MP4 was recorded and checked with ffprobe. The localhost viewer served HTTP 200 and completed a WebSocket/VNC handshake.
- An external socket attempt from the guest returned network-unreachable (101). The desktop uses an internal Docker network with no host directory or API key mounted into it.

Raw smoke artifacts remain under ignored `output/final-gui-check/`; the packaged model evidence is under `examples/evaluation/`.

## Release and scope boundaries

The [GitHub repository](https://github.com/HHuysamen/legacy-desktop-computer-use) and captured evidence are ready for public release. The personal website has not been modified; [website copy and asset instructions](website-copy.md) are ready for integration.

Other desktop hosts, Linux x86-64 desktop execution and direct macOS desktop control have not been tested. CI's Python tests do not validate native desktop operation on those platforms. No layout-variation or real-application study was performed.
