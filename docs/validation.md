# Validation snapshot — 8 November 2026

## Extended model evaluation

All **24 evaluated attempts** produced independently verified CSVs, with eight attempts per report and no failed or blocked attempts. The original nine were followed by 15 more using the same model, data and desktop configuration. A separate recheck of all 24 saved exports also passed.

| Task | Verified / attempted | Median elapsed | Desktop actions | Model requests | Estimated API cost, task total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Monthly revenue | 8/8 | 26.717 s | 7 | 6 | USD 0.284688 |
| Overdue invoices | 8/8 | 26.415 s | 7–8 | 6–7 | USD 0.308254 |
| Reconciliation exceptions | 8/8 | 24.931 s | 7 | 6 | USD 0.285432 |
| All evaluated runs | 24/24 | 25.740 s | 7–8 | 6–7 | USD 0.878374 |

The model was `gpt-6.1-terra`, with OpenAI Python SDK 3.31.0. Each attempt started a freshly seeded Linux arm64/X11 guest at 1200×900. The host was macOS 26.6.2 on Apple silicon with Docker Engine 29.9.1 and Python 3.13; the guest used Python 3.12.

## Evidence and cost basis

The [24-run gallery](../examples/evaluation-24/index.html), [summary](../examples/evaluation-24/summary.json) and [independent recheck](../examples/evaluation-24/independent-recheck.json) retain every outcome. The [manifest](../examples/evaluation-24/manifest.json) hashes all packaged files. The [original nine-run package](../examples/evaluation/index.html) remains unchanged; all 116 original file hashes were verified after the extension.

All 24 runs returned complete token usage. The estimate uses the published Standard short-context rates of US$1 per million input tokens and US$5 per million output tokens, checked on 8 November 2026. Cache discounts and provider billing adjustments are not applied; the estimate is not an invoice or a spending cap. The [pricing basis](../examples/evaluation-24/pricing-basis.md) and [cost calculation](../examples/evaluation-24/cost-analysis.json) record the assumptions.

Mean estimated model cost was USD 0.036598917 per run. At one similar task per workday, 20 runs project to USD 0.731978 for a month. This excludes desktop hosting, setup, and narration or video production. More complex tasks can require more screenshots and requests and cost more.

The earlier successful monthly-revenue pilot (`20261108T084740-fd252d`) cost an estimated USD 0.035597 and is excluded from the 24-run statistics and projections. Original evaluation cost was USD 0.332093; the 15-run extension cost USD 0.546281. Together with the pilot, all 25 funded runs total USD 0.913971 estimated.

Earlier missing-key and quota-blocked setup attempts remain separate. Their raw evidence is retained under ignored `output/`; the [credential-free setup report](../examples/setup-blocked-report.html) remains a distinct failure example. No zero-cost claim is made where usage was unavailable.

The [narrated presentation](../examples/presentation/README.md) is a documented derivative of the original recording. Its video, captions, poster and provenance are also retained in this repository.

## Code and desktop checks

- **100 tests passed locally**, covering reporting rules, CSV validation, fixture reset, exports, HTML escaping, desktop bounds/focus/PID checks, operating limits, API errors, exclusive desktop ownership and evidence packaging.
- New packaging tests cover a balanced 24-run evaluation, preservation of the original package, incomplete plans and unbalanced task counts.
- The [original GitHub Actions run](https://github.com/HHuysamen/legacy-desktop-computer-use/actions/runs/42456016582) passed on Python 3.11 and 3.13. The release includes the new 100-test local result; the public repository workflow reruns the suite on Python 3.11 and 3.13.
- Each CSV was checked against independently computed fixture results. The model cannot call the verifier or query its expected answers.
- The desktop containers were stopped after the additional runs. Original recordings and evaluation artifacts were preserved.

## Scope and publication

These results describe one synthetic application, fixture and desktop layout. Other applications, layouts, operating systems and production workflows have not been assessed.

Publication was approved on 8 November 2026. The article is released at [henryhuysamen.com](https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/), with narrated video, captions and both evidence archives. The code and expanded evidence are released in the public demo repository.
