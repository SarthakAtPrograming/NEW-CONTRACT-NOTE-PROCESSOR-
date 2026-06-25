import re
import pdfplumber
import pandas as pd
from brokers.base import BaseBroker

class SureshRathiBroker(BaseBroker):
    
    def extract_metadata(self, pdf_path: str) -> dict:
        metadata = {
            'Trade Date': 'Unknown',
            'Contract Note Number': 'Unknown',
            'Settlement Number': 'Unknown'
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
                
            date_match = re.search(r"Trade Date\s*:\s*(\d{2}/\d{2}/\d{4})|Trade Date\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            cn_match = re.search(r"Contract Note No\.\s*:\s*([A-Z0-9/-]+)", text, re.IGNORECASE)
            settlement_match = re.search(r"Settlement Number[\s:]*([A-Z0-9/-]+)", text, re.IGNORECASE)
            
            if date_match: 
                metadata['Trade Date'] = date_match.group(1) if date_match.group(1) else date_match.group(2)
            if cn_match: 
                metadata['Contract Note Number'] = cn_match.group(1).strip()
            if settlement_match: 
                metadata['Settlement Number'] = settlement_match.group(1).strip()
            
        return metadata

    def extract_trades(self, pdf_path: str) -> pd.DataFrame:
        trades = []
        temp_trades = []
        metadata = self.extract_metadata(pdf_path)
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                for line in lines:
                    # Match Trade Execution Lines
                    trade_pattern = re.search(r"\b([BS])\s+([\d,]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([-]?[\d,\.]+)", line)
                    
                    if trade_pattern:
                        buy_sell = "BUY" if trade_pattern.group(1) == 'B' else "SELL"
                        qty = float(trade_pattern.group(2).replace(',', ''))
                        rate = float(trade_pattern.group(3).replace(',', ''))
                        brok_per_unit = float(trade_pattern.group(4).replace(',', ''))
                        
                        prefix = line[:trade_pattern.start()].strip()
                        sec_name = re.sub(r"^(NSE|BSE|ICCL)\s+\d*\s*\d{2}:\d{2}:\d{2}\s*\d*\s*\d{2}:\d{2}:\d{2}\s*", "", prefix).strip()
                        
                        if not sec_name:
                            sec_name = "Unknown Security"
                            
                        temp_trades.append({
                            'Trade Date': metadata['Trade Date'],
                            'Contract Note Number': metadata['Contract Note Number'],
                            'Settlement Number': metadata['Settlement Number'],
                            'Security Name': sec_name,
                            'ISIN': None, 
                            'Buy / Sell': buy_sell,
                            'Quantity': qty,
                            'Rate': rate,
                            'Brokerage': qty * brok_per_unit
                        })
                        
                    # Match ISIN and assign to pending trades
                    isin_match = re.search(r"\b(INE[A-Z0-9]{9})\b", line)
                    if isin_match and temp_trades:
                        current_isin = isin_match.group(1)
                        for t in temp_trades:
                            t['ISIN'] = current_isin
                            trades.append(t)
                        temp_trades = []

        return pd.DataFrame(trades)

    def extract_total_charges(self, pdf_path: str) -> float:
        total_taxes = 0.0
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # The summary tables have borders, so we can use extract_tables() safely here
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                        
                    # Flatten the header row to identify which summary table this is
                    header_row = [str(c).replace('\n', ' ').strip().upper() for c in table[0] if c]
                    header_text = " ".join(header_row)
                    
                    is_tax_table_1 = "SECURITIES TRANSACTION TAX" in header_text or "SEBI TURNOVER" in header_text
                    is_tax_table_2 = "CGST" in header_text and "IGST" in header_text
                    
                    if is_tax_table_1 or is_tax_table_2:
                        for row in table:
                            # Isolate the 'Total (Net)' row at the bottom of the tables
                            if row[0] and "Total (Net)" in str(row[0]):
                                
                                # Table 1 columns: 2(STT), 3(CTT), 4(Exch Trans), 5(SEBI), 6(Stamp Duty), 7(Other)
                                if is_tax_table_1:
                                    target_cols = [2, 3, 4, 5, 6, 7]
                                    
                                # Table 2 columns: 2(CGST), 3(SGST), 4(IGST), 5(UTT)
                                elif is_tax_table_2:
                                    target_cols = [2, 3, 4, 5]
                                    
                                # Sum the targeted columns
                                for col_idx in target_cols:
                                    if col_idx < len(row) and row[col_idx]:
                                        val_str = str(row[col_idx]).replace(',', '').strip()
                                        if val_str and val_str not in ['-', 'NA', '']:
                                            try:
                                                total_taxes += float(val_str)
                                            except ValueError:
                                                pass
                                                
        return round(total_taxes, 2)