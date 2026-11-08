# Website integration copy

## Project card

**Title:** Automating a legacy desktop app with Computer Use

**Summary:** A screenshot-driven OpenAI agent operates a native finance application and exports reports. Separate code verifies each CSV. All 24 evaluated attempts passed in a fixed synthetic environment, with a median elapsed time of 25.74 seconds.

**Links:** [Read the case study](/writing/ledgerdesk-computer-use/) · [View the 24-run evidence](/demos/ledgerdesk/evaluation-24/index.html) · [Watch the narrated demo](/demos/ledgerdesk/demo-narrated-v2.mp4) · [Source](https://github.com/HHuysamen/legacy-desktop-computer-use)

These routes belong to the approved public article release.

## Evidence and cost

Results derived from `output/evaluation-24.json`: eight attempts per report, 24 independently verified exports from 24 evaluated attempts. The separate pilot and setup checks are excluded.

| Report | Verified exports | Median elapsed time |
| --- | ---: | ---: |
| Monthly revenue | 8 of 8 | 26.72 seconds |
| Overdue invoices | 8 of 8 | 26.42 seconds |
| Reconciliation exceptions | 8 of 8 | 24.93 seconds |

The 24 runs used 7–8 desktop actions and 6–7 model requests each. Complete API usage was recorded for every run. Their total standard-rate estimate is **about US$0.88**, averaging **US$0.0366 per run**.

For **one similar simple report task per workday over 20 workdays**, the measured mean projects to **about US$0.73 per month**. This is an illustrative workload estimate, not a monthly subscription or a measured month of production use.

Keep the workload assumption beside any monthly estimate. Standard-rate API estimates exclude cache discounts and may differ from provider billing. These figures cover model use, not hosting, engineering or narration production.

The model is `gpt-6.1-terra` with OpenAI Python SDK 3.31.0. The recorded setup is a native Linux arm64/X11 desktop at 1200×900, running through Docker on macOS/Apple silicon. Synthetic data, a fixed layout and three tasks limit what these results establish; they do not measure general desktop reliability.

## Website integration

The article is published at [henryhuysamen.com](https://www.henryhuysamen.com/writing/ledgerdesk-computer-use/). Its source is `src/content/writing/ledgerdesk-computer-use.md` in the website repository, with `status: 'published'` and `publishedDate: 2026-11-08`.

Approved assets are in `public/demos/ledgerdesk/`, so normal production builds include them. Draft articles remain excluded from normal builds; an explicit `CONTENT_PREVIEW=1` build can include them but is noindex and must not be deployed to production.

| Asset | Public route |
| --- | --- |
| Article | `/writing/ledgerdesk-computer-use/` |
| Original silent video | `/demos/ledgerdesk/demo.mp4` |
| Narrated video | `/demos/ledgerdesk/demo-narrated-v2.mp4` |
| English captions | `/demos/ledgerdesk/demo-narrated-v2.vtt` |
| Poster | `/demos/ledgerdesk/poster-v2.png` |
| Narration provenance | `/demos/ledgerdesk/narration-manifest-v2.json` |
| Complete 24-run package | `/demos/ledgerdesk/evaluation-24/` |
| Original nine-run package | `/demos/ledgerdesk/` |

The narrated video is 24 seconds at 1200×1008. Speech and the footer were added afterward; the footer sits below the original 1200×900 application image. Retain the original recording and narration manifest. Both evidence archives must be copied intact so their relative links and artifact hashes remain valid.

The model controls the native app through screenshots and mouse/keyboard actions. The browser only displays the isolated desktop and supplies no DOM access to the model.

## Search and AI-search readiness

The website presents the six-step workflow as visible semantic HTML cards, with a single-column mobile layout. It also has a visible author byline, matching `BlogPosting` JSON-LD, and an article-specific social sharing image. Published structured data uses the actual publication date and video metadata; draft metadata does not invent publication. Existing canonical links, descriptive headings, captions and measured evidence remain.

For each release, verify the production canonical, sitemap, internal links and public asset URLs. Keep explicit draft previews noindex. Check the released URL in Google Search Console and Bing Webmaster Tools; verify intended crawler access through both robots.txt and the hosting layer.

The article includes `VideoObject` data with its publication date and permanent media URLs. The current video supports an article; this is not a dedicated watch page. Search-result inclusion is not guaranteed.

Google's AI features use the same SEO fundamentals: readable text, useful original information, crawlability and matching structured data. No special AI schema, `llms.txt` file or keyword-heavy FAQ is required. Keep the source code, verification method and 24-run evidence easy to inspect. For ChatGPT search, OAI-SearchBot access is separate from GPTBot training preferences; do not change either policy without an explicit publishing decision.

Sources: [Google AI features](https://developers.google.com/search/docs/appearance/ai-features), [Article structured data](https://developers.google.com/search/docs/appearance/structured-data/article), [video guidance](https://developers.google.com/search/docs/appearance/video), [OpenAI crawler documentation](https://developers.openai.com/api/docs/bots).
