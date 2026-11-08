---
status: published
updated: 2026-11-08
updated_by: codex
next_actions:
  - Monitor search indexing if requested.
  - Keep future article changes in a draft or reviewed branch before publication.
blockers: []
---
# Handoff

## Resume here
- User approved public release on 2026-11-08. Demo repository is public: https://github.com/HHuysamen/legacy-desktop-computer-use.
- Current branch is main; release commit 9429683 contains the 24-run evaluation, current article and narrated presentation.
- Live article: https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/.
- Live evidence: https://www.henryhuysamen.com/demos/ledgerdesk/evaluation-24/index.html.
- Website PR #2 merged as e1958f9 and initial production deployment 42480423926 succeeded.
- Website working clone: output/site-preview; canonical checkout: /Users/henryhuysamen/Projects/henryhuysamen.com.
- Active media: examples/presentation/demo-narrated-v2.mp4, captions, poster and manifest. Raw production files remain under ignored output/narration/round-03.
- Publishing/writing lessons are in the website repository at docs/WRITING_AND_PUBLISHING.md; demo integration notes are in docs/website-copy.md.

## Decisions and limits
- All 24 actual model runs passed and all CSVs passed a separate recheck; eight runs per report. Separate pilot excluded.
- Cost estimate: USD 0.878374 total; USD 0.036598917 per run; one task per workday over 20 workdays projects to USD 0.731978, model API only.
- Original 116-file nine-run archive preserved; expanded evidence has 285 hashed files. Both archives and narrated assets are public.
- Public demo CI passed 100 tests on Python 3.11 and 3.13. Website normal and preview builds passed all 11 checks.
- Verified 11 public URLs with browser-compatible requests; article has no noindex, media hashes match, RSS/sitemap include the article.
- Cloudflare browser-integrity rules reject some bare HTTP clients. Real Chrome and browser-compatible requests succeeded; security settings were not weakened.
- Cloudflare-managed robots rules retain training-crawler restrictions while allowing generic search crawling.
- Article uses the site's fonts, theme tokens, author metadata and responsive semantic workflow cards. VideoObject metadata and actual publication date are set.
- Production assets are in website public/demos/ledgerdesk. Explicit draft-preview builds remain noindex.
- No credentials are committed. Desktop containers stopped after evaluation.

## Open questions
- None blocking publication. Search-engine indexing is an external follow-up, not verified inclusion.

## Recent sessions
- 2026-11-08 (codex): Published the approved article, narrated media and full reference archives; updated the public demo repo and transferred writing/publishing lessons to the website repo.
- 2026-11-08 (codex): Added responsive workflow cards, author/SEO metadata and mobile navigation fix.
- 2026-11-08 (codex): Extended evaluation to 24/24 verified runs and added monthly cost estimate.
- 2026-11-08 (codex): Defined Computer Use and added AI Engineer / AI application wording.
- 2026-11-08 (codex): Shortened article, reduced demo branding and repaired narrated video.
