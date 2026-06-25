import re
import pdfplumber
import pandas as pd
from brokers.base import BaseBroker


class ZerodhaBroker(BaseBroker):
    """
    Zerodha 'CONTRACT NOTE CUM TAX INVOICE' consolidated statements.

    Unlike Suresh Rathi / ACML, a single Zerodha PDF can contain MANY
    independent contract notes (one per trading day), each a self-contained
    block of pages. This extractor segments the PDF into those blocks
    dynamically (no hardcoded page-count per block, since Annexure A can
    overflow onto extra pages on heavy trading days), then parses each
    block's Annexure A for trade-level rows and its tax-summary page for
    the bill-level statutory charges.
    """

    ANNEXURE_LINE_PATTERN = re.compile(
        r"\d+\s+\d{2}:\d{2}:\d{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+"   # Order/Trade no + times
        r"([A-Z0-9&.]+)-[A-Z]{1,3}/([A-Z0-9]{12})\s+"               # Security-<suffix>/ISIN (EQ on NSE, B on BSE, etc.)
        r"([BS])\s+(?:NSE|BSE)\s+"                                  # Buy/Sell + Exchange
        r"([\d,]+)\s+([\d.]+)\s+([\d.]+)\s+"                       # Qty, Brokerage(line total), Rate/unit
        r"\(?([\d,]+\.\d+)\)?"                                      # Net Total (paren = negative/buy)
    )

    TAX_LINE_KEYWORDS = [
        "Exchange transaction charges",
        "Clearing charges",
        "CGST",
        "SGST",
        "IGST",
        "Securities transaction tax",
        "SEBI turnover fees",
        "Stamp duty",
    ]
    # Deliberately EXCLUDED: "Taxable value of Supply (Brokerage)" — this is
    # the brokerage amount restated for GST purposes, not a statutory tax.
    # It's already captured per-trade in the Brokerage column, so including
    # it here would double-count brokerage as if it were a tax/expense.

    def extract_metadata(self, pdf_path: str) -> dict:
        # Not used — Zerodha is multi-bill-per-PDF, so metadata is
        # extracted per-block inside extract_trades() instead.
        return {}

    def _segment_blocks(self, pdf):
        """Return list of (start_idx, end_idx) page ranges, one per contract note."""
        starts = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "CONTRACT NOTE CUM TAX INVOICE" in text:
                starts.append(i)

        blocks = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(pdf.pages)
            blocks.append((start, end))
        return blocks

    def _extract_block_tax(self, block_text: str) -> float:
        total = 0.0
        for line in block_text.split("\n"):
            stripped = line.strip()
            if any(stripped.startswith(k) for k in self.TAX_LINE_KEYWORDS):
                nums = re.findall(r"\(?[\d,]+\.\d+\)?", stripped)
                if nums:
                    # Last number on the line = NET TOTAL column
                    last = nums[-1].replace(",", "").replace("(", "").replace(")", "")
                    try:
                        total += float(last)
                    except ValueError:
                        pass
        return round(total, 2)

    def extract_trades(self, pdf_path: str) -> pd.DataFrame:
        trades = []

        with pdfplumber.open(pdf_path) as pdf:
            blocks = self._segment_blocks(pdf)

            for start, end in blocks:
                block_pages = pdf.pages[start:end]
                page_texts = [(p.extract_text() or "") for p in block_pages]
                block_text = "\n".join(page_texts)

                # --- Metadata for this specific contract note ---
                date_match = re.search(r"Trade Date:\s*(\d{2}/\d{2}/\d{4})", block_text)
                settle_match = re.search(r"Settlement No:\s*(\S+)", block_text)
                cn_match = re.search(r"Contract Note No:\s*(\S+)", block_text)

                trade_date = date_match.group(1) if date_match else "Unknown"
                settlement_no = settle_match.group(1) if settle_match else "Unknown"
                contract_no = cn_match.group(1) if cn_match else "Unknown"

                # --- Annexure A may span multiple pages within the block ---
                annexure_text = ""
                in_annexure = False
                for t in page_texts:
                    if "Annexure A" in t:
                        in_annexure = True
                    if in_annexure:
                        annexure_text += t + "\n"

                block_trades = []
                for line in annexure_text.split("\n"):
                    m = self.ANNEXURE_LINE_PATTERN.search(line)
                    if not m:
                        continue

                    sec_name, isin, bs, qty_str, brok_total_str, rate_str, _net_total = m.groups()

                    qty = float(qty_str.replace(",", ""))
                    brokerage_amt = float(brok_total_str)  # already a line total, NOT per-unit
                    rate = float(rate_str)

                    block_trades.append({
                        'Trade Date': trade_date,
                        'Contract Note Number': contract_no,
                        'Settlement Number': settlement_no,
                        'Security Name': sec_name,
                        'ISIN': isin,
                        'Buy / Sell': "BUY" if bs == "B" else "SELL",
                        'Quantity': qty,
                        'Rate': rate,
                        'Brokerage': round(brokerage_amt, 2),
                    })

                if not block_trades:
                    continue  # no trades in this block, skip silently

                # --- Bill-level tax pool for this block only ---
                bill_tax = self._extract_block_tax(block_text)
                for t in block_trades:
                    t['Bill_Tax'] = bill_tax
                    trades.append(t)

        return pd.DataFrame(trades)

    def extract_total_charges(self, pdf_path: str) -> float:
        # Handled per-block inside extract_trades() (via Bill_Tax) to avoid
        # bleeding one day's taxes into another day's trades.
        return 0.0