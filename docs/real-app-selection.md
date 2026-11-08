# Selecting a real finance application

Research checked 8 November 2026. **Select GnuCash for the next native application study, with HomeBank as the fallback.** This is a feasibility assessment and task design, not evidence of completed agent runs.

## Why GnuCash

GnuCash provides a real accounting register, balanced transactions and split entries. It runs on Linux, macOS and Windows. Its Debian Bookworm package is a GTK3/X11 application available for arm64, which fits the existing Apple Silicon host and Linux desktop container without introducing a Windows environment. This would validate the Linux application only; availability on Windows does not establish Windows automation performance. [GnuCash features](https://code.gnucash.org/website/features.phtml), [Debian package](https://packages.debian.org/bookworm/gnucash)

The current [Dockerfile](../docker/Dockerfile) uses Debian Bookworm. Its packaged GnuCash version is `1:4.13-1`, so use the version 4 documentation and record the installed version and image digest. Package metadata confirms availability; dependency resolution, launch, dialogs and actual GUI operation still require a smoke test before measured attempts.

| Candidate | Fit for this study | Decision |
| --- | --- | --- |
| GnuCash 4.13 | Native GTK accounting application; registers, transfers and multiple-account splits; saved books permit independent checks. | First choice. |
| HomeBank 5.6.2 | Native GTK personal-finance application, with account management and CSV/OFX import; Bookworm arm64 package available. | Fallback if GnuCash cannot run reliably in the isolated desktop. |
| A Windows-only accounting application | Would require a separate Windows runtime and application-specific installation, licensing and verification work. | A later study; the existing container is Linux. |

HomeBank's package depends on GTK3 despite an older GTK2 statement in its description. Its personal-finance focus offers less accounting variety than GnuCash for this extension. [Debian HomeBank package](https://packages.debian.org/bookworm/homebank)

## Selected tasks

Use three task types with three different fixture variants each: **nine proposed measured attempts**. Vary dates, references and amounts rather than repeating identical inputs. Freeze the task definitions, verifier and driver after the manual smoke test. These attempts are separate from the [published 100-attempt study](evaluation-methodology.md) and the new variation/control study.

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

Before scoring, build a separately tagged image with GnuCash installed using `--no-install-recommends`, start a fresh synthetic book and test saving/reopening it manually. Keep startup/import preferences isolated between attempts. Confirm the driver permits GnuCash's process-owned windows, menus and save dialogs as titles change. The package depends on WebKit for some features; these selected tasks exercise native registers and dialogs, not an embedded report view. [Package dependencies](https://packages.debian.org/bookworm/gnucash)

Retain the source book, saved book, source hashes, screenshots, action trace, request usage and independent verdict for every measured attempt, including failures. Publish no success rate until the attempts and artifact checks exist. These small synthetic cases can demonstrate interaction with a real application; they cannot establish reliability across arbitrary accounting software, production books or Windows desktops.

The validation fixture uses GnuCash's displayed US short date format (MM/DD/YY). Task instructions include that representation alongside the ISO date to avoid ambiguity; this study does not test locale/date-format adaptation.
