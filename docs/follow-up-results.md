# Follow-up results

## Office input and layout study

The 8 November 2026 Office campaign completed all 30 planned slots: **24 of 24 positive tasks passed**, and **six of six negative controls showed their expected behavior**. All 30 outcomes passed the offline evidence recheck. Controls are expected refusals, not successful business tasks.

The [evidence package](../examples/robustness-30/index.html), [summary](../examples/robustness-30/summary.json), [independent rechecks](../examples/robustness-30/recheck.json) and [frozen protocol](../examples/robustness-30/protocol.json) retain the full record. The [methodology](robustness-methodology.md) describes the design; [reproduction instructions](follow-up-reproduction.md) describe a separate new campaign.

| Positive task group | Verified / attempted | Mean elapsed time | Median elapsed time | Model cost, USD | Cost per verified success, USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| LibreOffice Calc | 12 / 12 | 71.2225 s | 69.557 s | 1.488362 | 0.124030167 |
| LibreOffice Writer | 12 / 12 | 35.6955 s | 37.3565 s | 0.447860 | 0.037321667 |
| All positive tasks | 24 / 24 | 53.459 s | 43.880 s | 1.936222 | 0.080675917 |

The positive tasks used 438 executed input actions and 216 model requests. All 24 recorded zero operator interventions. Timing includes setup, the agent loop and verification, but excludes final container teardown. Costs are model API estimates from complete recorded usage, excluding hosting and other operating costs.

### Paired inputs and geometry

All 12 development cases and all 12 held-out cases passed. All 12 normal-layout cases and all 12 changed-layout cases passed. Each of the 12 matched input/instruction pairs passed under both geometries, and every pair's saved input hashes matched its frozen fixture.

| Group | Verified / attempted | Model cost, USD | Mean elapsed time |
| --- | ---: | ---: | ---: |
| Development | 12 / 12 | 0.967410 | 52.4112 s |
| Held-out | 12 / 12 | 0.968812 | 54.5068 s |
| Normal geometry | 12 / 12 | 0.967884 | 51.7023 s |
| Changed geometry | 12 / 12 | 0.968338 | 55.2157 s |

Across matched pairs, changed-minus-normal elapsed time averaged +3.5133 seconds, with a median of +1.791 seconds and a range from −33.630 to +37.933 seconds. Changed geometry used two more input actions in total, the same number of model requests, and USD 0.000454 more estimated model cost. These are descriptive comparisons of this small set; they do not isolate the cause of latency differences or estimate general desktop reliability.

### Controls and retained evidence

| Negative control | Expected behavior rechecked | Model cost, USD |
| --- | ---: | ---: |
| Foreign focus | 2 / 2 | 0.000000 |
| Missing source | 2 / 2 | 0.000000 |
| Duplicate receipt | 2 / 2 | 0.071808 |

Foreign-focus evidence records refusal with no foreign input events or changed sentinel value. Missing-source evidence is consistent with preflight refusal before a model request; the offline recheck does not make a new observation of the former guest. Both duplicate-receipt cases retain the expected rejected audit event and unchanged canonical database state.

Total cost for all 30 slots is **USD 2.008030**, comprising USD 1.936222 for positive tasks and USD 0.071808 for controls. All 30 recorded zero operator interventions. Positive cost per verified success uses only the positive-task total and its 24 verified successes; control costs are reported separately.

All 24 positive source-preservation checks pass: saved starting-file hashes match the frozen inputs and the controller's recorded post-run hashes. This combines retained input bytes with historical controller evidence, rather than a new live observation.

The package contains 30 reports and 28 recordings. The two missing-source controls stop before recording starts and retain their preflight markers instead. All 446 files indexed by the [manifest](../examples/robustness-30/manifest.json) were checked for matching byte lengths and SHA-256 hashes. All 440 copied per-run files were also compared byte-for-byte with the originals; campaign protocol, ledger and status copies match their originals.

Measured runtime identity: source `7f269cd03b47dd83b62ca77a2aefba4b6058bf51`, image `sha256:9a83a615fe1441b1e88e7f7f7f04af52aa454b9223c2a14cb11bf2bb3f7c46d9`, model `gpt-6.1-terra` with medium reasoning, Linux arm64/X11 at 1200×900. The study covers fixed synthetic task families in Calc and Writer; it does not establish Windows performance or reliability across arbitrary applications. The original demonstration archives remain separate.

## Original GnuCash study

The original nine-case campaign completed with **zero of nine verified successes, nine failures and no unverified slots**. The [original GnuCash archive](../examples/gnucash-9/index.html), [summary](../examples/gnucash-9/summary.json) and [rechecks](../examples/gnucash-9/recheck.json) retain every attempt. These outcomes are separate from the Office figures above.

| Task | Verified / attempted | Model cost, USD |
| --- | ---: | ---: |
| `gnucash-expense` | 0 / 3 | 0.076417 |
| `gnucash-split` | 0 / 3 | 0.128634 |
| `gnucash-transfer` | 0 / 3 | 0.037477 |
| Original cohort total | 0 / 9 | 0.242528 |

All nine raw traces contain the same immediate stop: a requested `keypress` with `keys: ["Tab"]` is followed by `ValueError: Unsupported keys`. The frozen driver accepted the spelling `TAB`; the host passed through `Tab` without canonicalizing it. This is an observed driver compatibility failure, not evidence that GnuCash itself cannot perform the task. Six attempts produced no saved output. Three saved files were retained, but each failed the independent check for the exact requested new transaction.

The attempts used 93 completed input actions and 42 model requests. Mean elapsed time was 26.7062 seconds and median elapsed time 23.162 seconds. All usage records are complete; the full **USD 0.242528** estimate includes the nine failures. Cost per verified success is not applicable because there were no verified successes. All nine recorded zero operator interventions, and all nine saved-input plus recorded post-run source-hash checks pass.

The [manifest](../examples/gnucash-9/manifest.json) indexes 105 files; all byte lengths and SHA-256 hashes were verified. All 99 copied per-run files match the originals, as do the protocol, ledger and status copies. The archive retains nine reports and nine recordings. It uses the same original source revision and image identified above; no original outcome has been replaced.

### Completed repair cohort

The separately frozen repair cohort completed with **nine of nine verified successes, no failures and no unverified slots**. All nine outputs and source-preservation checks pass the offline recheck. The [repair archive](../examples/gnucash-9-repaired/index.html), [summary](../examples/gnucash-9-repaired/summary.json) and [rechecks](../examples/gnucash-9-repaired/recheck.json) are separate from the original archive.

| Task | Verified / attempted | Model cost, USD |
| --- | ---: | ---: |
| `gnucash-expense` | 3 / 3 | 0.183937 |
| `gnucash-split` | 3 / 3 | 0.323920 |
| `gnucash-transfer` | 3 / 3 | 0.211903 |
| Repair cohort total | 9 / 9 | 0.719760 |

The repair used 179 completed input actions and 83 model requests, with zero recorded operator interventions. Mean elapsed time was 51.0219 seconds and median elapsed time 49.769 seconds. Its complete model-cost estimate is **USD 0.719760**, or USD 0.079973333 per verified success within the repair cohort.

The original and repair protocols contain exactly the same fixture manifest. The repair follows a host-side key-name correction and uses source revision `ab67ca3e7bded15c8137e60917ad2b86ec0ee69e`, with image `sha256:b3935bd320422c6e786f3a71846ee004e46544e9ce7f41b6411d252a35a1432e`. It is a repair check selected after observing the original failures, **not independent held-out evidence**. The original zero-of-nine result remains unchanged; the repair does not replace it or prove reliability on new tasks.

All 152 files indexed by the repair [manifest](../examples/gnucash-9-repaired/manifest.json) passed byte-length and SHA-256 checks. Its 146 copied per-run files match the originals; protocol, ledger and status copies also match. All nine reports and recordings are retained.

### Cost accounting across the follow-ups

The two GnuCash cohorts together cost **USD 0.962288**: USD 0.242528 for the original failed cohort plus USD 0.719760 for the repair cohort. Including the separate Office tasks and controls, the three follow-up campaigns cost **USD 2.970318**. These totals include known costs from the original failures; outcome denominators remain separate. They exclude the earlier 100-attempt study, setup work, hosting and media production.
