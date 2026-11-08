# Selecting a real finance application

Research checked 8 November 2026. **GnuCash was selected and installed for the native application study, with HomeBank retained as the fallback.** A manual development smoke check succeeded. The original nine measured agent attempts all failed at a driver key-name boundary; a separately frozen repair cohort passed all nine checks on the same fixtures. These are separate results, not a single uninterrupted success series; see the [follow-up results](follow-up-results.md).

## Why GnuCash

GnuCash provides a real accounting register, balanced transactions and split entries. It runs on Linux, macOS and Windows. Its Debian Bookworm package is a GTK3/X11 application available for arm64, which fits the existing Apple Silicon host and Linux desktop container without introducing a Windows environment. The study covers the Linux application only; availability on Windows does not establish Windows automation performance. [GnuCash features](https://code.gnucash.org/website/features.phtml), [Debian package](https://packages.debian.org/bookworm/gnucash)

The [Dockerfile](../docker/Dockerfile) uses Debian Bookworm. The frozen image records GnuCash `1:4.13-1`; its protocol retains the installed version and image identity. Package availability was followed by a manual GUI smoke check before measurement, rather than treated as proof that the agent could complete the tasks.

| Candidate | Fit for this study | Decision |
| --- | --- | --- |
| GnuCash 4.13 | Native GTK accounting application; registers, transfers and multiple-account splits; saved books permit independent checks. | First choice. |
| HomeBank 5.6.2 | Native GTK personal-finance application, with account management and CSV/OFX import; Bookworm arm64 package available. | Fallback if GnuCash cannot run reliably in the isolated desktop. |
| A Windows-only accounting application | Would require a separate Windows runtime and application-specific installation, licensing and verification work. | A later study; the existing container is Linux. |

HomeBank's package depends on GTK3 despite an older GTK2 statement in its description. Its personal-finance focus offers less accounting variety than GnuCash for this extension. [Debian HomeBank package](https://packages.debian.org/bookworm/homebank)

## Selected tasks

The selected design uses three task types with three different fixture variants each: **nine measured attempts in the original cohort**. Dates, references and amounts vary rather than repeating identical inputs. The task definitions, verifier and driver were frozen after the manual development smoke test. These attempts are separate from the [published 100-attempt study](evaluation-methodology.md) and the variation/control study.

| Task | GUI operation | Required saved result |
| --- | --- | --- |
| `gnucash-expense` | Enter one supplies expense paid from Checking. | One new transaction, with the exact date, description and equal/opposite Checking and ExpenseSupplies splits. |
| `gnucash-split` | Enter one payment divided between travel and meals. | One new transaction with exactly three splits: Checking, ExpenseTravel and ExpenseMeals; exact amounts and a zero sum. |
| `gnucash-transfer` | Record a transfer from Checking to Savings. | One new transaction moving the specified amount between the two bank accounts, without changing expenses. |

Seed a synthetic USD book containing Checking, Savings, ExpenseTravel, ExpenseMeals, ExpenseSupplies and EquityOpening, plus a balanced opening transaction giving Checking USD 10,000. Every task saves a new `.gnucash` file through the application's controls. No task connects a bank or initiates a payment.

CSV import remains a useful follow-up, but is deferred from these first nine attempts. The version 4 importer includes column/account mapping and history-based matching. It introduces additional state and more complicated failure diagnosis than the register tasks. A future import study must reset both the book and importer preferences and verify exact transactions, including duplicates. [GnuCash 4 import manual](https://code.gnucash.org/website/docs/v4/C/gnucash-help/trans-import.html)

## Verification and runtime boundary

Use the native XML backend. GnuCash documents it as built in, usually gzip-compressed, and saved explicitly; SQL backends have packaging-dependent availability. Trusted setup may generate the small starting book, and a separate verifier may read the saved XML. Compare financial content rather than whole-file output bytes: application metadata and generated identifiers can change during saving. Check the exact new transaction, preserve the original accounts and opening transaction, reject extra records or imbalance accounts, and compare the source file's before/after hash. [GnuCash 4 storage guide](https://www.gnucash.org/docs/v4/C/gnucash-guide/basics-files1.html)

The model receives instructions and screenshots, with the existing bounded mouse/keyboard driver. It receives no file reader, SQL access, GnuCash bindings, shell or browser DOM. GnuCash does have programming interfaces; the claim is that those interfaces are unavailable to the agent, not that the application has no API. [GnuCash API documentation](https://www.wiki.gnucash.org/wiki/Using_the_API)

A manual development smoke check opened a generated synthetic book, entered a supplies expense and saved a copy through the GUI. The retained `output/gnucash-preflight` artifact passes the independent semantic verifier, including its original-source check. This established one prepared GUI path; it did not test every key spelling the model might choose. The package depends on WebKit for some features; these selected tasks exercise native registers and dialogs, not an embedded report view. [Package dependencies](https://packages.debian.org/bookworm/gnucash)

The original measured cohort retained all nine failures and their complete USD 0.242528 model-cost estimate. In every trace the driver rejected the model's `Tab` key spelling while accepting `TAB`. None produced a verified requested result: six outputs were missing and three retained outputs failed semantic checks. All original source-preservation checks passed.

After correcting host key-name handling, a separately frozen repair cohort passed all nine task and source-preservation checks, costing USD 0.719760. It uses the same fixture manifest and is not independent held-out evidence. The [original archive](../examples/gnucash-9/index.html) and [repair archive](../examples/gnucash-9-repaired/index.html) retain their own source/image identities and outcomes. Total model cost across both cohorts is USD 0.962288, including the original failures; the repaired results do not erase them.

Retain source books, available saved books, source hashes, screenshots, action traces, usage and independent verdicts for every cohort. These small synthetic cases cannot establish reliability across arbitrary accounting software, production books or Windows desktops.

The validation fixture uses GnuCash's displayed US short date format (MM/DD/YY). Task instructions include that representation alongside the ISO date to avoid ambiguity; this study does not test locale/date-format adaptation.
