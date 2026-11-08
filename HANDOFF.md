---
status: active
updated: 2026-11-08
updated_by: codex
next_actions:
  - Verify the approved production deployment and public repository release.
  - Record final public URLs and checks after deployment.
  - Monitor indexing after publication if requested.
blockers: []
---
# Handoff

## Resume here
- User approved public release of the article, reference assets and demo repository on 2026-11-08. Release work is prepared; verify remote deployment after pushing.
- Local branch: draft/narrated-article. Article: docs/article.md, Automating a legacy desktop app with Computer Use.
- Completed 15 additional real model attempts; all passed. Combined evaluation: output/evaluation-24.json, 24/24, eight per report.
- New evidence: examples/evaluation-24; 285 artifact hashes, plus manifest. All 24 CSVs independently rechecked.
- Original output/evaluation.json and examples/evaluation remain unchanged; all 116 original file hashes verified.
- Cost: USD 0.878374 total, USD 0.036598917 mean; one task per workday over 20 workdays projects to USD 0.731978, model API only.
- Website clone: output/site-preview, private branch preview/ledgerdesk-demo, draft PR #2.
- Preview: http://127.0.0.1:4321/writing/ledgerdesk-computer-use/; evidence under /demos/ledgerdesk/evaluation-24/.
- Active video: output/narration/round-03/demo-narrated-v2.mp4, with matching captions/poster/manifest. Media unchanged this session.

## Decisions and limits
- Website workflow is a semantic six-item HTML list styled as responsive cards; desktop/mobile and light/dark views checked.
- Visible byline, BlogPosting JSON-LD and article-specific sharing image added. Draft has no invented publication date; noindex remains. Eight website checks pass.
- Before publication, confirm real publish date, public media routes, crawler access and structured-data validation. SEO/GEO review is in docs/website-copy.md.
- User approved 24 evaluated runs; the separate pilot is excluded from statistics and projections.
- Same gpt-6.1-terra, SDK 3.31.0, synthetic fixture and native desktop setup; no failed or blocked evaluation attempts.
- Article section renamed Cost; requested reliability paragraph removed. Added monthly workload assumption and more-complex-task cost explanation.
- Standard input/output rates rechecked against OpenAI pricing on 2026-11-08. Costs are estimates; hosting and other operating costs excluded.
- Packager now accepts balanced positive multiples of three and retains safety/provenance checks. All 100 tests pass locally.
- Normal/preview website builds pass. Original nine-run archive remains separate from expanded evidence.
- Model-run desktop containers stopped after evaluation. Budget for the 15-run extension was USD 2; its estimate was USD 0.546281.
- Publication and merge to website main are explicitly authorized by the latest user request. Credentials remain local and ignored.
- Existing narration uses George/eleven_v4; only date cue was repaired previously. Footer lies below the original screen.
- Never put credentials in source, metadata, logs or handoffs.

## Open questions
- No publication decision is pending. Verify the deployed output and current remote commit.

## Recent sessions
- 2026-11-08 (codex): Restored visual six-step workflow as crawlable HTML cards, added author/search metadata and fixed cramped mobile navigation; kept private noindex.
- 2026-11-08 (codex): Extended evaluation to 24/24 verified runs, packaged new evidence without altering the original archive, and added Cost/monthly estimate to article and preview.
- 2026-11-08 (codex): Defined Computer Use with an official link; added AI Engineer and AI application to the introduction.
- 2026-11-08 (codex): Shortened article and reduced demo branding; applied generic caption and new closing.
- 2026-11-08 (codex): Added video footer, repaired date narration and updated poster/captions.
