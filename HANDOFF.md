---
status: published
updated: 2026-11-08
updated_by: codex
next_actions:
  - Recheck Google indexing after processing; both URLs were accepted into the priority crawl queue on 2026-11-08.
  - Optionally mirror the separate follow-up link to Medium; its canonical already points to the main site.
blockers: []
---
# Handoff

## Resume here
- Public repo: https://github.com/HHuysamen/legacy-desktop-computer-use. Follow-up PR #2 merged as cd3557a.
- Live follow-up: https://www.henryhuysamen.com/demos/ledgerdesk/follow-up/.
- Article: https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/.
- Website PR #4 merged as a4bf332; production Pages deployment 42497813444 succeeded.
- Website working clone: output/site-preview. Canonical: /Users/henryhuysamen/Projects/henryhuysamen.com.
- Canonical checkout has local Medium handoff commit ed36919; preserve that history and its notes when syncing.
- Sources: docs/follow-up-results.md, docs/robustness-methodology.md, docs/real-app-selection.md, docs/follow-up-reproduction.md.
- New immutable archives: examples/robustness-30, examples/gnucash-9, examples/gnucash-9-repaired.
- Raw ledgers: output/robustness-study, output/gnucash-study, output/gnucash-study-repaired; run evidence under output/runs.

## Decisions and limits
- Search Console: sitemap-index.xml submitted successfully with status Success on 2026-11-08; article and follow-up indexing requests both accepted into the priority crawl queue. Submission is not proof of indexing; do not resubmit repeatedly.
- Office variation: 24/24 positive tasks verified, 6/6 stopping controls passed separately. All12 input/instruction pairs passed both geometries.
- Original native GnuCash: 0/9 verified. Every attempt stopped at model key Tab versus the driver's uppercase TAB allowlist. All failures retained.
- Repaired native GnuCash: 9/9 verified, using the same fixtures after the observed bug; this is repair validation, not new held-out evidence.
- Original follow-up source7f269cd03b47dd83b62ca77a2aefba4b6058bf51; repair sourceab67ca3e7bded15c8137e60917ad2b86ec0ee69e. Both remain in main history.
- Repair normalizes ASCII key-name casing only, preserves raw/canonical traces and retains guest key restrictions. CLI now takes the global desktop lock; freeze helper supports a new output directory.
- Costs: Office positives USD1.936222, controls0.071808, original Gnu0.242528, repaired Gnu0.719760; total48 slots USD2.970318. All usage complete, zero recorded operator interventions.
- New manifests index446/105/152 files respectively; all saved outputs, original source hashes and copied artifacts rechecked. Older116/285/1292 hashes unchanged.
- GnuCash4.13 and LibreOffice7.4.7 run in Linux arm64/X11. GnuCash APIs are withheld from the model, not claimed nonexistent. No Windows or production-data result.
- Requested API identifier gpt-6.1-terra, medium reasoning, SDK3.31.0. No immutable provider-weight snapshot was verified.
- 363 Python tests passed locally; Python3.11/3.13 CI passed;22 website checks passed in production and preview. Desktop/mobile light/dark checked, no page overflow.
- Live article/follow-up/sitemap and all3 summaries return200; summaries match local hashes. Seven search/retrieval UA probes return200; not verified crawler IPs or indexing.
- Managed robots still disallows training crawlers. GPTBot UA returned200 on the new route; robots policy is distinct from HTTP enforcement. No crawler settings changed.
- Worker Git builds disconnected and UI verified Connect state on 2026-11-08; PR#1 is closed. Existing Worker, Pages workflow, DNS and routes retained. Old failed build checks are historical.
- Local test browser/server stopped; desktop containers stopped. Secrets remain in ignored local configuration, never guest or archives.
- Prior100 study remains99/100, including its original Calc failure. Narrated-v2 media unchanged.

## Open questions
- Actual search/AI-search indexing and generalization to unfamiliar applications, locales, Windows and production data remain unverified.
- Medium live settings verified: originally published elsewhere enabled; canonical is https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/. Visible links point back to the main site; no separate follow-up link observed.

## Recent sessions
- 2026-11-08 (codex): Closed session work; Worker Git builds disconnected, obsolete PR#1 closed, Medium canonical verified, sitemap accepted and both indexing requests queued. Only Google processing remains pending.
- 2026-11-08 (codex): Published separately frozen Office/control and original/repaired GnuCash evidence; retained all failures and complete costs.
- 2026-11-08 (claude-code, prior note): Published Medium syndication with the site article as canonical; preserved local handoff history.
- 2026-11-08 (codex): Published100-attempt study, including original Calc failure, with source-linked methods and evidence.
- 2026-11-08 (codex): Published original article and narrated media; tested sitemap and crawler access.
