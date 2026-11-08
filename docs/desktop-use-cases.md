# Business use cases for native desktop automation

Research checked 8 November 2026. Recommended expansion: **five synthetic business workflows in LedgerDesk plus two tasks in real LibreOffice applications**. Keep the existing monthly revenue, overdue invoice and reconciliation reports as separate tasks.

This is a catalogue of recurring workflow categories, not a statistically ranked “top 20.” Microsoft and UiPath document the broader business patterns; the concrete demo tasks and suitability judgments below are our proposed adaptations. Those sources do not establish that every installation lacks an API. Use desktop control when the particular system has no usable supported integration. LibreOffice has automation interfaces, but those must remain unavailable to the screenshot-only agent.

## Twenty recurring categories

“High” means a good fit for a bounded synthetic fixture and a deterministic result check. “Medium” means useful but requires additional state, applications or domain rules. The numbers identify categories; they do not rank business frequency.

| # | Workflow category | Representative GUI task | Demo fit | Basis |
| --- | --- | --- | --- | --- |
| 1 | Invoice lookup | Search an invoice number and inspect its details. | High; select | [ERP desktop work][M], [receivables][O] |
| 2 | Customer record maintenance | Update a named contact or address on the correct account. | High; select | [Customer setup and validation][O] |
| 3 | Invoice data entry | Enter supplied invoice fields and save a new draft. | High; select | [ERP data entry][M], [invoicing][O] |
| 4 | Cash receipt allocation | Record a received amount against the correct invoice. | High with synthetic data; select | [Cash application and payments reconciliation][O] |
| 5 | Batch data import | Import a prepared CSV and review accepted/rejected rows. | High; select | [Desktop data movement][M], [CSV exchange][C] |
| 6 | Spreadsheet sorting and export | Sort a business register in Calc and save the result. | High; select | [Calc sorting][CS], [CSV export][C] |
| 7 | Document template updates | Replace specified text in a Writer document and save a copy. | High; select | [Writer Find & Replace][W] |
| 8 | Filtered record extraction | Filter by customer, status, dates or amount; export the subset. | High; later | [Desktop workflows][M], [spreadsheet data operations][CS] |
| 9 | Purchase requisition/order entry | Enter a request with supplier, quantity and reference. | Medium | [Purchase-to-pay][F] |
| 10 | Supplier onboarding | Create or update supplier master details. | Medium | [Procurement and supplier onboarding][S] |
| 11 | Sales order processing | Enter or amend an order and review its status. | Medium | [Order processing][O] |
| 12 | Inventory record updates | Record a counted quantity or prepare a replenishment request. | Medium | [Inventory management][S] |
| 13 | Shipment and fulfillment updates | Locate an order and record a delivery-status change. | Medium | [Fulfillment and logistics][O], [S] |
| 14 | Expense claim preparation | Enter receipt details and assign a category for review. | Medium | [Expense claims][H] |
| 15 | Timesheet entry and validation | Enter hours and flag missing or inconsistent entries. | Medium | [Timesheet validation][H] |
| 16 | Payroll input preparation | Update approved attendance or incentive inputs. | Medium; use fictional data | [Payroll workflows][H] |
| 17 | Journal-entry preparation | Enter a balanced draft with account codes and references. | Medium; no posting | [General accounting][F] |
| 18 | Reconciliation exception handling | Open a mismatch and add a review note or classification. | Medium | [Reconciliations and exception handling][F] |
| 19 | Employee onboarding records | Populate a fictional employee's approved setup fields. | Medium; use fictional data | [HR onboarding][H] |
| 20 | Document/PDF production | Export an approved document or spreadsheet as a PDF. | High; later | [LibreOffice PDF export][P] |

## Recommended seven, in implementation order

This ordering prioritizes clear verification, interaction variety and manageable implementation effort. It is not a ranking of commercial importance.

| Priority / task ID | Proposed exercise | Independent success check | What it adds |
| --- | --- | --- | --- |
| 1 — `invoice-lookup` | Find one exact invoice and export its displayed details. | Exact identity, customer, dates and balance; database unchanged. | Search and navigation without changing records. |
| 2 — `customer-update` | Change one fictional customer's contact details. | Only the named record and authorized fields change. | Targeted form editing and save confirmation. |
| 3 — `invoice-entry` | Create one invoice draft from supplied fields. | Exactly one expected row added; totals/dates correct; existing records unchanged. | Multi-field entry, validation and new-record creation. |
| 4 — `payment-recording` | Record a synthetic received payment against one invoice. | Exact amount and allocation; correct remaining balance; no unrelated changes. | Linked records and partial-payment state. |
| 5 — `csv-import` | Import an allowlisted sample file through the app and review the outcome. | Exact imported rows; duplicates/invalid rows handled as specified. | File selection, import confirmation and batch validation. |
| 6 — `calc-sort-export` | In real Calc, sort a seeded register numerically and export CSV. | Header retained, complete row multiset preserved, correct order and values. | A second application's menus, dialogs and file formats. |
| 7 — `writer-find-replace` | In real Writer, replace specified text and save an edited document. | Expected replacement count; unrelated text retained in the saved ODT. | Document editing and a different native UI. |

For payment recording, demonstrate **recording money already received**, not initiating a transfer. Keep invoice entry as draft creation. Customer updates should use fictional contact/address fields, not bank details. These definitions make the actions concrete and inspectable without connecting real financial systems.

The CSV import file is prepared by trusted setup. The model selects it through the GUI; it does not get a filesystem reader. Include a duplicate or invalid row so that “import finished” alone cannot satisfy the task.

Calc should use a small fixed register with a header, numeric sort values and a tie-break key. Verify whole rows, not just the sorted column: an incorrectly selected range can scramble relationships. Its CSV export contains only the current sheet and does not preserve workbook formatting. [CSV behavior][C]

Writer should use an unambiguous placeholder with several occurrences and at least one near-match that must remain unchanged. Check document text after saving, rather than accepting a closed dialog or a changed filename. Saved ODT metadata may vary, so compare the intended content rather than whole-file byte equality. [Replacement controls][W]

## How the sources inform the design

Microsoft explicitly describes desktop flows for legacy applications, ERP entry, invoice information and interactions using UI elements, images or coordinates. This supports the relevance of the underlying workflow categories; it does not imply that this demo uses Power Automate. [Microsoft desktop flows][M]

UiPath's finance, order-to-cash, supply-chain and HR pages identify business areas where data entry, account maintenance, reconciliation, imports and cross-system handoffs recur. Their product pages discuss several automation methods, including APIs. We use them to motivate task selection, not as proof that screenshot-only control is the preferred integration or that vendor performance claims apply here. [Finance][F], [order-to-cash][O], [supply chain][S], [HR][H]

OSWorld and Microsoft's Windows Agent Arena provide precedents for evaluating desktop agents with defined starting states and checks of resulting work. They justify adding a real native application and checking saved artifacts, rather than expanding only the fictional fixture. They are research benchmarks, not surveys of business frequency; results from our small suite must not be described as an OSWorld or Windows Agent Arena score. [OSWorld][B1], [Windows Agent Arena][B2]

## Evaluation boundaries

- Reset the fixture or documents before each attempt. Preserve the original 24-run report evaluation as its own evidence set.
- Keep all new tasks marked as proposed until their implementation and real agent runs have been verified. Unit tests and scripted GUI smoke checks are separate evidence.
- For mutations, verify the exact permitted state change and check that unrelated records stayed unchanged. Treat duplicate creation, wrong-account edits and incorrect payment allocation as failures.
- For LibreOffice, constrain the driver to the launched application processes and approved dialogs. Do not expose UNO, macros, shell execution or direct document reads to the model. Trusted setup and verification may read files independently.
- Add variations in IDs, amounts, source rows and document text. Report each task's attempts and failures separately; passing several similar reports does not demonstrate all seven new skills.

## Primary references

[M]: https://learn.microsoft.com/en-us/power-automate/desktop-flows/introduction
[F]: https://www.uipath.com/solutions/department/finance-and-accounting-automation
[O]: https://www.uipath.com/solutions/department/finance-and-accounting-automation/order-to-cash
[S]: https://www.uipath.com/solutions/department/supply-chain-automation
[H]: https://www.uipath.com/solutions/department/hr-automation
[C]: https://help.libreoffice.org/latest/en-US/text/scalc/guide/csv_files.html
[CS]: https://books.libreoffice.org/en/CG262/CG26202-EnteringandEditingData.html
[W]: https://help.libreoffice.org/latest/en-US/text/swriter/guide/finding.html
[P]: https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export.html
[B1]: https://github.com/xlang-ai/OSWorld
[B2]: https://github.com/microsoft/WindowsAgentArena

- [Microsoft: Introduction to desktop flows][M]
- [UiPath: Finance and accounting automation][F]
- [UiPath: Order-to-cash automation][O]
- [UiPath: Supply chain automation][S]
- [UiPath: HR automation][H]
- [LibreOffice: Opening and saving CSV files][C]
- [LibreOffice Calc Guide 26.2: Entering and editing data, including sorting][CS]
- [LibreOffice Writer: Finding and replacing][W]
- [LibreOffice: Export as PDF][P]
- [OSWorld: source and evaluation framework][B1]
- [Microsoft Windows Agent Arena: source and task framework][B2]
