# Website integration copy

## Project card

**Title:** LedgerDesk: AI computer use beyond the browser

**Summary:** A screenshot-driven OpenAI agent operates a native finance application to generate and export reports, with every CSV checked by an independent verifier. Nine of nine attempts passed in a fixed synthetic test environment, with a median elapsed time of 25.5 seconds.

**Links:** [Read the case study](article.md) · [View the evidence](../examples/evaluation/index.html) · [Watch the demo](../examples/evaluation/demo.mp4) · [Source on GitHub](https://github.com/HHuysamen/legacy-desktop-computer-use)

**Technologies:** Python · Tkinter · SQLite · OpenAI Responses API · Computer use · Docker · Independent verification

## Case-study facts

- Three business reports, with three attempts each: 9 verified exports out of 9 evaluated attempts.
- Median elapsed time: 25.481 seconds; 7–8 desktop actions and 6–7 model requests per attempt.
- Nine-run API estimate: USD 0.332093. A separate successful pilot adds USD 0.035597, giving USD 0.367690 across ten funded runs.
- Model: `gpt-6.1-terra`; OpenAI Python SDK 3.31.0.
- Native Linux arm64/X11 desktop at 1200×900, hosted by Docker on macOS/Apple silicon.
- Synthetic data and a fixed layout. These results show repeatability for this fixture, not general desktop reliability.
- Costs use standard-rate estimates; cache read/write effects and provider billing may differ.

Use [article.md](article.md) as the case-study body. Keep the result qualifications with the table, and preserve the separation between the nine evaluated attempts, the successful pilot and earlier setup blocks.

## Asset routes

The website has not been modified. A suggested route is `/projects/ledgerdesk/`, with the complete `examples/evaluation/` directory copied beneath `/projects/ledgerdesk/evidence/`. Preserve its `runs/` and `pilot/` subdirectories so the gallery's relative links continue to work.

| Source file | Suggested website route | Purpose |
| --- | --- | --- |
| `docs/article.md` | `/projects/ledgerdesk/` | Case-study body, converted through the site's usual renderer |
| `examples/evaluation/index.html` | `/projects/ledgerdesk/evidence/index.html` | Gallery and full evaluation |
| `examples/evaluation/demo.mp4` | `/projects/ledgerdesk/evidence/demo.mp4` | Model-operated recording |
| `examples/evaluation/poster.png` | `/projects/ledgerdesk/evidence/poster.png` | Video poster |
| `examples/evaluation/sample-report.html` | `/projects/ledgerdesk/evidence/sample-report.html` | Self-contained detailed report |
| `examples/evaluation/summary.json` | `/projects/ledgerdesk/evidence/summary.json` | Machine-readable results |
| `examples/evaluation/manifest.json` | `/projects/ledgerdesk/evidence/manifest.json` | Artifact hashes |

When adapting the article, rewrite its repository-relative evidence links to these site routes. Serve the video as `video/mp4`; offer the report as a regular page or download. Retain the complete evidence directory unchanged so the manifest continues to describe its files.

Use the [source repository](https://github.com/HHuysamen/legacy-desktop-computer-use) for the code link. Publishing the personal website is a separate step from releasing the repository and evidence.
