#!/usr/bin/env python3
"""Build a TallyPrime Sales Order import envelope from a JSON order.

Usage: python3 build_sales_order.py order.json > sales-order.xml

The JSON shape is shown in examples/order.json. Names (company, party, items,
units, ledgers) must match the masters in Tally exactly.
"""
import json
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWO = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def esc(value: str) -> str:
    value = str(value)
    if any(ord(c) < 32 and c not in "\t\n\r" for c in value):
        raise ValueError(f"control character in text: {value!r}")
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def esc_item(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("empty stock item name")
    return esc(value).replace("\r", "&#13;").replace("\n", "&#10;").replace("\t", "&#9;")


def tag(name: str, value) -> str:
    return f"<{name}>{esc(value)}</{name}>"


def build(order: dict) -> str:
    company = order["company"]
    ref = order["reference"]
    vtype = order.get("voucherType", "Sales Order")
    order_date = date.fromisoformat(order["orderDate"])
    due_date = date.fromisoformat(order.get("dueDate", order["orderDate"]))
    days = (due_date - order_date).days
    if days < 0:
        raise ValueError("dueDate is before orderDate")
    period = f"{days} {'Day' if days == 1 else 'Days'}"
    jd = (due_date - date(1899, 12, 30)).days
    ymd = order_date.strftime("%Y%m%d")
    ledgers = order["ledgers"]
    godown = order.get("godown", "Main Location")
    batch = order.get("batch", "Primary Batch")

    taxable = Decimal("0")
    lines_xml = []
    for line in order["lines"]:
        qty = Decimal(str(line["quantity"]))
        rate = money(line["rate"])
        disc = Decimal(str(line.get("discountPercent", 0)))
        amount = money(qty * rate * (Decimal(100) - disc) / Decimal(100))
        taxable += amount
        unit = esc(line["unit"])
        q = f" {qty.normalize():f} {unit}"
        gst = ""
        if line.get("taxability"):
            gst += tag("GSTOVRDTAXABILITY", line["taxability"])
        if line.get("hsn"):
            gst += tag("HSNNAME", line["hsn"])
        lines_xml.append(
            "<ALLINVENTORYENTRIES.LIST>"
            f"<STOCKITEMNAME>{esc_item(line['item'])}</STOCKITEMNAME>"
            f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>{gst}"
            f"<RATE>{rate}/{unit}</RATE><DISCOUNT>{disc.normalize():f}</DISCOUNT>"
            f"<AMOUNT>{amount}</AMOUNT><ACTUALQTY>{q}</ACTUALQTY><BILLEDQTY>{q}</BILLEDQTY>"
            "<BATCHALLOCATIONS.LIST>"
            f"{tag('GODOWNNAME', godown)}{tag('BATCHNAME', batch)}{tag('ORDERNO', ref)}"
            f'<ORDERDUEDATE JD="{jd}" P="{period}">{period}</ORDERDUEDATE>'
            f"<AMOUNT>{amount}</AMOUNT><ACTUALQTY>{q}</ACTUALQTY><BILLEDQTY>{q}</BILLEDQTY>"
            "</BATCHALLOCATIONS.LIST>"
            "<ACCOUNTINGALLOCATIONS.LIST>"
            f"{tag('LEDGERNAME', ledgers['sales'])}<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
            f"<AMOUNT>{amount}</AMOUNT>"
            "</ACCOUNTINGALLOCATIONS.LIST>"
            "</ALLINVENTORYENTRIES.LIST>")

    taxes = []
    for key in ("cgst", "sgst", "igst"):
        pct = order.get("taxPercent", {}).get(key)
        if pct:
            if key not in ledgers:
                raise ValueError(f"ledgers.{key} is required when taxPercent.{key} is set")
            taxes.append((ledgers[key], money(taxable * Decimal(str(pct)) / 100)))
    gross = taxable + sum((a for _, a in taxes), Decimal("0"))
    total = gross.quantize(Decimal("1"), rounding=ROUND_HALF_UP) if order.get("roundToRupee") else gross
    round_off = money(total - gross)

    def ledger(name, amount):
        return (f"<LEDGERENTRIES.LIST>{tag('LEDGERNAME', name)}<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>{amount}</AMOUNT></LEDGERENTRIES.LIST>")

    ledger_xml = "".join(ledger(n, a) for n, a in taxes if a != 0)
    if round_off != 0:
        if "roundOff" not in ledgers:
            raise ValueError("ledgers.roundOff is required when the total is rounded")
        ledger_xml += ledger(ledgers["roundOff"], round_off)

    if money(taxable + sum((a for _, a in taxes), Decimal("0")) + round_off) != money(total):
        raise ValueError("totals do not add up")

    narration = tag("NARRATION", order["narration"]) if order.get("narration") else ""
    party = esc(order["party"])
    return (
        "<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST>"
        "<TYPE>Data</TYPE><ID>Vouchers</ID></HEADER><BODY><DESC><STATICVARIABLES>"
        f"{tag('SVCURRENTCOMPANY', company)}</STATICVARIABLES></DESC><DATA>"
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<VOUCHER VCHTYPE="{esc(vtype)}" ACTION="Create" OBJVIEW="Invoice Voucher View">'
        f"<DATE>{ymd}</DATE><EFFECTIVEDATE>{ymd}</EFFECTIVEDATE>{tag('REFERENCE', ref)}{narration}"
        f"<PARTYLEDGERNAME>{party}</PARTYLEDGERNAME>{tag('VOUCHERTYPENAME', vtype)}"
        "<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW><ISINVOICE>No</ISINVOICE>"
        f"<LEDGERENTRIES.LIST><LEDGERNAME>{party}</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
        "<ISPARTYLEDGER>Yes</ISPARTYLEDGER><ISLASTDEEMEDPOSITIVE>Yes</ISLASTDEEMEDPOSITIVE>"
        f"<AMOUNT>-{money(total)}</AMOUNT></LEDGERENTRIES.LIST>"
        f"{ledger_xml}{''.join(lines_xml)}"
        "</VOUCHER></TALLYMESSAGE></DATA></BODY></ENVELOPE>")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        print(build(json.load(f)))
