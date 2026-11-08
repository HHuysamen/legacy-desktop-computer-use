# Evidence examples

## Verified model runs

The [evaluation gallery](evaluation/index.html) presents nine real OpenAI computer-use attempts: three each for monthly revenue, overdue invoices and reconciliation exceptions. All nine exported CSVs passed independent verification and a later recheck. The fixture, layout and environment were fixed across attempts.

- [Desktop recording](evaluation/demo.mp4): the actual model-operated monthly-revenue run `20261108T084829-36a77a`, included in the nine-run evaluation.
- [Standalone evidence report](evaluation/sample-report.html): that run's task, screenshots, action trace, CSV preview and verification.
- [Evaluation summary](evaluation/summary.json): all nine runs, aggregate statistics and a separate successful pilot excluded from the evaluation denominator.
- [Artifact manifest](evaluation/manifest.json): packaged paths, byte counts and SHA-256 hashes.
- [Poster image](evaluation/poster.png): a captured frame for the recording.

The package contains per-run metadata, events, screenshots, CSVs and verification results. The estimate for the nine evaluation runs is USD 0.332093; including the separate pilot, the ten funded runs total USD 0.367690 estimated. These standard-rate estimates may differ from provider billing because of cache read/write effects and other billing rules.

## Separate fixture and failure examples

- [ledgerdesk.png](ledgerdesk.png): the native fixture before a task, captured from the isolated Linux desktop on 8 November 2026.
- [setup-blocked-report.html](setup-blocked-report.html): an earlier credential-free attempt, with no model activity. It is a setup failure example, excluded from evaluation statistics.

Scripted GUI smoke footage and quota-rejection evidence remain in ignored local output. They are distinct from the verified model-run evidence above. See [validation details](../docs/validation.md) for tested configurations and limitations.
