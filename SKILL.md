---
name: tally-sales-order
description: Create, look up and verify Sales Order vouchers in TallyPrime through its XML/HTTP interface. Use when an order (from WhatsApp, a PO, a spreadsheet or a chat) must become a Sales Order in Tally, or when checking whether a Sales Order already exists and matches.
---

# Tally Sales Order

Turn a confirmed customer order into a Sales Order voucher in TallyPrime, then prove it landed correctly. Built from production experience running AI ordering agents for distributors on Tally.

## When to use

- An order has been agreed (customer, items, quantities, prices) and must be recorded in Tally as a Sales Order.
- You need to check whether a Sales Order with a given reference already exists, before creating it again.
- An import "succeeded" but someone doubts what Tally stored.

Do not use it for Sales invoices, receipts or masters (ledgers, stock items). Those use different voucher shapes.

## How Tally is reached

TallyPrime answers XML requests over HTTP when its server is on (F1 Help > Settings > Connectivity: "TallyPrime acts as" Server or Both, default port 9000). Every request is a `POST` of an `<ENVELOPE>` to `http://<host>:9000`. The company named in `SVCURRENTCOMPANY` must be open in Tally, and its name must match exactly, including any year suffix such as `ABC TRADERS - (26-27)`.

## Workflow

Follow these steps in order. Never skip step 2 or step 5.

1. **Resolve masters by exact name.** The party ledger, every stock item and every item's base unit must already exist in Tally. Read them first (see `references/lookup-masters.xml`). Use the names Tally returns, not the names the customer typed. If any item cannot be resolved to exactly one master, stop and ask.
2. **Check for an existing order.** Look up Sales Orders with the same `REFERENCE` on the order date (`references/lookup-sales-order.xml`). If one exists, verify it (step 5) instead of creating a duplicate. Treat an error, a truncated reply or a missing `STATUS` as "unknown", never as "not found".
3. **Build the import envelope.** Use `scripts/build_sales_order.py` (input: one JSON order) or follow `references/sales-order-template.xml`. Rules for the voucher are below.
4. **Import and read the response.** A clean import has `CREATED` = 1, `ERRORS` = 0, `EXCEPTIONS` = 0 and no `LINEERROR`. Anything else is a failure; report `LINEERROR` text verbatim.
5. **Read the voucher back and verify.** Look it up again by reference and date. Check: exactly one voucher, not cancelled, not optional, party matches, line count matches, and each line's item, quantity, unit, rate, discount and amount match what you sent. Only then report the order as created, with Tally's voucher number.

## Voucher rules

- **Voucher type and view.** `VCHTYPE` and `VOUCHERTYPENAME` = the company's Sales Order voucher type (usually `Sales Order`). Use `OBJVIEW="Invoice Voucher View"`, `PERSISTEDVIEW` = `Invoice Voucher View`, `ISINVOICE` = `No`.
- **Dates.** `YYYYMMDD`, with `DATE` and `EFFECTIVEDATE` equal to the order date.
- **Reference.** Put your own order ID in `REFERENCE` and in every batch row's `ORDERNO`. That is your key for step 2 and step 5.
- **Party line.** The party ledger entry has `ISDEEMEDPOSITIVE` = Yes, `ISPARTYLEDGER` = Yes and a negative `AMOUNT` equal to the full order total (taxable + taxes + round off).
- **Item lines** (`ALLINVENTORYENTRIES.LIST`): `ISDEEMEDPOSITIVE` = No, `RATE` written as `120.00/Pcs` (rate, slash, base unit), `ACTUALQTY` and `BILLEDQTY` written as ` 10 Pcs` (leading space, quantity, space, unit), `AMOUNT` positive, `DISCOUNT` as a percent number.
- **Batch row inside each item.** One `BATCHALLOCATIONS.LIST` with `GODOWNNAME` (default `Main Location`), `BATCHNAME` (default `Primary Batch`), `ORDERNO` = reference, the same amount and quantities, and `ORDERDUEDATE` with `P="7 Days"` style due period (use "1 Day" for one).
- **Sales ledger.** Each item carries one `ACCOUNTINGALLOCATIONS.LIST` to the sales ledger for the line amount.
- **GST.** For intra-state sales add CGST and SGST ledger entries; for inter-state, one IGST entry. Ledger amounts are positive with `ISDEEMEDPOSITIVE` = No. Add a round-off ledger only when round off is not zero (it can be negative). Taxable + taxes + round off must equal the party total to the paisa; check this before sending.
- **Decimals.** Do money arithmetic with decimals, never floats, and write amounts with two decimal places.

## Gotchas learned in production

- **Escape every text value** for XML (`& < > " '`). Stock item names can contain line breaks or tabs at the end; encode them as `&#13;`, `&#10;`, `&#9;` so the name still matches the master exactly.
- **Control characters in replies.** Tally prefixes some system values with `&#4;` (for example `&#4; Not Applicable`). Strip those references before parsing; keep tab, line feed and carriage return.
- **Quantities come back padded and may carry an alternate unit**, like ` 10.000 Pcs = 1 Box`. Compare only the part before `=`, as a decimal, with the unit normalised for spaces.
- **Ledger names can come back as an alias** ("Roundedoff" instead of "Round Off"). Compare ledger names ignoring case, spaces and punctuation, and identify each ledger by its amount too.
- **An empty collection may contain an empty `<VOUCHER>` placeholder.** Ignore vouchers with no GUID, number, reference, date, party or lines.
- **Never send customer data in the URL**, and don't log full request or response XML where customer details could leak; keep the status fields only.

## Files

- `scripts/build_sales_order.py` builds the import XML from a JSON order and validates totals. Run `python3 scripts/build_sales_order.py order.json > so.xml`. `examples/order.json` shows the input shape.
- `references/sales-order-template.xml` is a filled example of the import envelope.
- `references/lookup-sales-order.xml` finds Sales Orders by reference and date.
- `references/lookup-masters.xml` reads a ledger or stock item with its unit.

To post XML to Tally: `curl -s -X POST --data-binary @so.xml http://localhost:9000`.
