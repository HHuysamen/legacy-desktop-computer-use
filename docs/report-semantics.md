# Report semantics

These rules describe the synthetic fixture, not a complete accounting policy. All amounts are USD, net of tax. SQLite stores integer cents; exported amounts use two decimal places, without currency symbols or thousands separators. Date values are calendar dates without time zones.

The source is [`fixtures/seed.json`](../fixtures/seed.json): 6 customers, 25 invoices and 9 reconciliation transactions. Resetting the fixture restores the same rows. No record represents a real customer, employee or company.

## Monthly revenue

Default month: **September 2026** (`2026-09`).

- Include invoices whose `invoice_date` falls within the selected calendar month and whose status is `issued`.
- Exclude `void` invoices regardless of their amount or payment state.
- Sum `net_cents` per customer. Payments do not affect this report: “revenue” here means net invoiced value by invoice date, not cash receipts or a revenue-recognition engine.
- Include customers with at least one eligible invoice. Do not add customers without activity.
- Sort revenue descending, then customer name ascending for ties.

CSV columns, in order: `customer,revenue`.

Default expected result:

| Customer | Revenue (USD) |
| --- | ---: |
| Alder Robotics | 2400.00 |
| Beacon Paperworks | 2400.00 |
| Cedar Trail Foods | 2000.00 |
| Delta Quay Services | 1800.00 |
| Ember Loom Textiles | 1500.00 |
| Fernlight Design | 1500.00 |

The fixture includes invoices immediately outside September, invoices on September 1 and 30, voided September invoices, and equal customer totals. These expose incorrect date boundaries, status filtering and unstable sorting.

## Overdue invoices

Default as-of date: **October 15, 2026** (`2026-10-15`).

- Include `issued` invoices with `due_date < as_of` and `net_cents - paid_cents > 0`.
- Balance is the full net amount less the seeded paid amount. A partial payment reduces the balance; it does not remove the invoice.
- Exclude voided, fully paid and zero-balance invoices. An invoice due on the as-of date is not overdue.
- Days overdue is the integer calendar-day difference `as_of - due_date`.
- Sort due date ascending, then invoice number ascending for ties.

CSV columns, in order: `customer,invoice_number,balance,due_date,days_overdue`.

The default report contains **7 rows**, in this order:

| Invoice | Balance (USD) | Due date | Days overdue |
| --- | ---: | --- | ---: |
| INV-260801 | 500.00 | 2026-08-31 | 45 |
| INV-260831 | 9999.99 | 2026-09-15 | 30 |
| INV-260820 | 150.00 | 2026-09-19 | 26 |
| INV-260903 | 1750.00 | 2026-09-25 | 20 |
| INV-260916 | 400.00 | 2026-10-10 | 5 |
| INV-260918 | 800.00 | 2026-10-14 | 1 |
| INV-261014 | 400.00 | 2026-10-14 | 1 |

The fixture stores a payment snapshot rather than dated payment events. Changing `as_of` changes overdue eligibility and day counts; it does not reconstruct historical balances at that date.

## Reconciliation exceptions

Default tolerance: **USD 0.01**.

- Signed difference is `recorded_cents - expected_cents`.
- Include a transaction only when `abs(difference) > tolerance`. Equality does not count as an exception.
- Preserve the difference's sign in the export. Sort transaction ID ascending.
- Tolerance must be finite and non-negative. Comparisons use decimal amounts rather than binary floating-point approximations.

CSV columns, in order: `transaction_id,recorded_amount,expected_amount,difference`.

Default expected result:

| Transaction | Recorded (USD) | Expected (USD) | Difference (USD) |
| --- | ---: | ---: | ---: |
| TXN-004 | 1750.02 | 1750.00 | 0.02 |
| TXN-005 | 799.98 | 800.00 | -0.02 |
| TXN-006 | 1255.00 | 1250.00 | 5.00 |
| TXN-007 | 690.00 | 700.00 | -10.00 |

Zero differences and positive or negative one-cent differences are excluded at the default threshold. Two-cent differences exercise the first included cent value.

## What verification proves

The trusted verifier reads the fixture database and exported CSV after the agent run. It independently calculates expected rows using its own queries and formatting; it does not call `reports.build_report`.

A pass requires the exact expected column names and order, row count, row order, identifiers and string values. Duplicate identifiers, missing rows, unexpected columns and altered values fail. An empty result is valid only when the independent expectation is also empty and the CSV still has the correct header.

The controller additionally owns run isolation and export retrieval. The verifier alone does not establish who generated a file, whether it is fresh, whether model inputs were properly restricted, or whether the model used the GUI. Those claims require the run's controller checks and captured action evidence. Correct fixture output is evidence for that particular task and configuration, not for other applications or real accounting records.
