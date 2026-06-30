import re
import pdfplumber
import pandas as pd
from brokers.base import BaseBroker


class SIHLBroker(BaseBroker):
    """
    Shah Investor's Home Ltd (SIHL) 'CONTRACT NOTE CUM BILL' statements.

    Like Zerodha, a single SIHL PDF can contain MANY independent contract
    notes (one per trading day), each a self-contained block of 1-2 pages
    (page count varies; some blocks overflow a "Page 1 of 2" continuation
    page). This extractor segments the PDF into those blocks dynamically.

    Unlike Zerodha, trades are NOT in a separate annexure — they sit
    directly in the main table on the contract note itself. A known
    pdfplumber quirk: very long Order Numbers wrap onto an orphan line by
    themselves (e.g. "B-\\n1766719800164820363"). Rather than fight that,
    the trade-row regex deliberately does NOT anchor on Order Number at
    all — it anchors on Order Time onward, which is reliably on one line
    even when the Order Number above/around it wraps.
    """

    TRADE_PATTERN = re.compile(
        r"(\d{2}:\d{2})\s+(\d+)\s+(\d{2}:\d{2})\s+"        # Order Time, Trade No, Trade Time
        r"([A-Z0-9&.]+)-EQ\s+D\s+(Buy|Sell)\s+"              # Security-EQ  D  Buy/Sell
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"  # Qty, Price, Brokerage/unit, NetRate, NetTotal
    )

    # Captures the 10 values in the "Total" row of the Transaction Summary:
    # PayIn/PayOut, CGST, SGST, IGST, STT, Demat, Turnover, StampDuty, Others, Rounding
    # (UTT column is always blank/N.A. in this broker's template, so it's
    # never present as a printed number — confirmed against multiple samples).
    TAX_ROW_PATTERN = re.compile(r"Total\s+((?:\(?[\d,]+\.\d+\)?\s*){10})")

    def extract_metadata(self, pdf_path: str) -> dict:
        # Not used — SIHL is multi-bill-per-PDF, metadata extracted per-block.
        return {}

    def _segment_blocks(self, pdf):
        """Return list of (start_idx, end_idx) page ranges, one per contract note."""
        starts = [
            i for i, page in enumerate(pdf.pages)
            if "CONTRACT NOTE CUM BILL" in (page.extract_text() or "")
        ]
        blocks = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(pdf.pages)
            blocks.append((start, end))
        return blocks

    def _extract_block_tax(self, block_text: str) -> float:
        m = self.TAX_ROW_PATTERN.search(block_text)
        if not m:
            return 0.0
        raw_values = m.group(1).split()
        if len(raw_values) < 10:
            return 0.0

        def parse(v):
            cleaned = v.replace(",", "").replace("(", "").replace(")", "")
            try:
                val = float(cleaned)
            except ValueError:
                return 0.0
            return -val if "(" in v else val

        parsed = [parse(v) for v in raw_values]
        # Indices: [0]=PayIn [1]=CGST [2]=SGST [3]=IGST [4]=STT [5]=Demat
        #          [6]=Turnover [7]=StampDuty [8]=Others [9]=Rounding
        # Statutory charges are always a real cost regardless of how the
        # PDF signs them (paren convention varies by Buy/Sell context), so
        # they're summed as absolute values. Rounding is signed and small
        # (a few paise) — it must be netted in with its actual sign or the
        # final reconciliation drifts by that amount on every single bill.
        statutory_abs = sum(abs(x) for x in parsed[1:9])
        rounding_signed = parsed[9]
        return round(statutory_abs - rounding_signed, 2)

    def extract_trades(self, pdf_path: str) -> pd.DataFrame:
        trades = []

        with pdfplumber.open(pdf_path) as pdf:
            blocks = self._segment_blocks(pdf)

            for start, end in blocks:
                page_texts = [(p.extract_text() or "") for p in pdf.pages[start:end]]
                block_text = "\n".join(page_texts)

                date_match = re.search(r"Trade Date\s*:\s*(\d{2}-\d{2}-\d{4})", block_text)
                settle_match = re.search(r"Settlement No:\s*(\S+)", block_text)
                cn_match = re.search(r"Contract No:\s*(\S+)", block_text)

                trade_date = date_match.group(1) if date_match else "Unknown"
                settlement_no = settle_match.group(1) if settle_match else "Unknown"
                contract_no = cn_match.group(1) if cn_match else "Unknown"

                raw_matches = self.TRADE_PATTERN.findall(block_text)
                if not raw_matches:
                    continue

                # ISIN mapping: zip unique securities (first-seen order)
                # against ISINs found in the block (also first-seen order).
                seen_securities = []
                for m in raw_matches:
                    sec = m[3]
                    if sec not in seen_securities:
                        seen_securities.append(sec)
                isins_found = re.findall(r"\b(INE[A-Z0-9]{9})\b", block_text)
                isin_map = {
                    sec: (isins_found[i] if i < len(isins_found) else "Unknown")
                    for i, sec in enumerate(seen_securities)
                }

                block_trades = []
                for (order_time, trade_no, trade_time, sec, bs, qty_str,
                     price_str, brok_unit_str, net_rate_str, net_total_str) in raw_matches:

                    qty = float(qty_str)
                    rate = float(price_str)
                    brok_per_unit = float(brok_unit_str)

                    block_trades.append({
                        'Trade Date': trade_date,
                        'Contract Note Number': contract_no,
                        'Settlement Number': settlement_no,
                        'Security Name': sec,
                        'ISIN': isin_map.get(sec, "Unknown"),
                        'Buy / Sell': "BUY" if bs == "Buy" else "SELL",
                        'Quantity': qty,
                        'Rate': rate,
                        'Brokerage': round(qty * brok_per_unit, 2),
                    })

                if not block_trades:
                    continue

                bill_tax = self._extract_block_tax(block_text)
                for t in block_trades:
                    t['Bill_Tax'] = bill_tax
                    trades.append(t)

        return pd.DataFrame(trades)

    def extract_total_charges(self, pdf_path: str) -> float:
        return 0.0