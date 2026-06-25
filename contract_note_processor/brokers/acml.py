import re
import pdfplumber
import pandas as pd
from brokers.base import BaseBroker

class ACMLCapitalBroker(BaseBroker):
    
    def extract_metadata(self, pdf_path: str) -> dict:
        return {}

    def extract_trades(self, pdf_path: str) -> pd.DataFrame:
        trades = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                curr_date, curr_cn, curr_settlement = "Unknown", "Unknown", "Unknown"
                current_isin, current_security = None, "Unknown Security"
                page_trades = []
                
                for line in text.split('\n'):
                    # 1. Capture Metadata for this specific bill
                    if "Trade Date" in line:
                        m = re.search(r"(\d{2}/\d{2}/\d{4})", line)
                        if m: curr_date = m.group(1)
                    if "Bill No" in line or "CAPOBL" in line:
                        m = re.search(r"(?:CAPOBL\s*)?(\d{5,})", line)
                        if m: curr_cn = m.group(1)
                    if "Settlement No" in line:
                        m = re.search(r"(\d{5,})", line)
                        if m: curr_settlement = m.group(1)
                        
                    # 2. Capture ISIN
                    isin_match = re.search(r"\b(INE[A-Z0-9]{9}|INF[A-Z0-9]{9})\b", line)
                    if isin_match:
                        current_isin = isin_match.group(1)
                        sec_name = line.replace(current_isin, "").replace("|", "").strip()
                        if sec_name: current_security = sec_name
                        continue
                        
                    # 3. Capture Trade Lines (Debit/Credit)
                    if re.search(r"^(NSE|BSE)\s*\|?\s*[DJ]", line.strip()):
                        floats = [float(n.replace(',', '')) for n in re.findall(r"\b\d+\.\d{2,4}\b", line.replace(',', ''))]
                        
                        i = 0
                        while i < len(floats) - 2:
                            qty = floats[i]
                            rate = floats[i+1]
                            gross = round(qty * rate, 2)
                            val3 = floats[i+2]
                            
                            # Identify if val3 is the Debit/Credit total
                            if abs(val3 - gross) < gross * 0.25: 
                                line_total = val3 
                                i += 3
                            else:
                                if i + 3 < len(floats):
                                    line_total = floats[i+3]
                                    i += 4
                                else:
                                    break
                                    
                            buy_sell = "BUY" if line_total > gross else "SELL"
                            if line_total == gross:
                                buy_sell = "SELL" if line.find(str(qty)) < (len(line) / 2) else "BUY"
                            
                            # YOUR LOGIC: Temp Brokerage Calculation
                            temp_brok = round(abs(line_total - gross), 2)
                            
                            page_trades.append({
                                'Trade Date': curr_date,
                                'Contract Note Number': curr_cn,
                                'Settlement Number': curr_settlement,
                                'Security Name': current_security,
                                'ISIN': current_isin,
                                'Buy / Sell': buy_sell,
                                'Quantity': qty,
                                'Rate': rate,
                                'Gross Value': gross,
                                'Temp Brokerage': temp_brok,
                                'Line Total': line_total
                            })
                            
                # --- BILL-SPECIFIC RECONCILIATION ---
                if not page_trades: continue
                
                # A. Brokerage Round-Off Logic
                calc_brok_sum = round(sum(t['Temp Brokerage'] for t in page_trades), 2)
                gt_brok = calc_brok_sum
                
                for line in text.split('\n'):
                    if "Grand Total" in line:
                        nums = [float(n.replace(',', '')) for n in re.findall(r"\b\d+\.\d{2}\b", line)]
                        if nums:
                            # Intelligently find the Brokerage number (the one closest to our Temp sum)
                            closest_num = min(nums, key=lambda x: abs(x - calc_brok_sum))
                            if abs(closest_num - calc_brok_sum) <= 5.0:
                                gt_brok = closest_num
                        break
                        
                diff = round(gt_brok - calc_brok_sum, 2)
                if diff != 0:
                    max_trade = max(page_trades, key=lambda x: x['Temp Brokerage'])
                    max_trade['Temp Brokerage'] += diff
                    
                for t in page_trades:
                    t['Brokerage'] = round(t['Temp Brokerage'], 2)
                    del t['Temp Brokerage']
                    
                # B. Total TAX/EXP Logic Per Bill
                total_amt = 0.0
                net_payable = 0.0
                for line in text.split('\n'):
                    if "Total Amount" in line:
                        nums = re.findall(r"[-]?\d+[\d,\.]*\b", line.replace("Total Amount", ""))
                        if nums: total_amt = abs(float(nums[0].replace(',', '')))
                    if "Net Total Payable" in line or "Receivable" in line:
                        nums = re.findall(r"[-]?\d+[\d,\.]*\b", line)
                        if nums: net_payable = abs(float(nums[-1].replace(',', '')))
                        
                # Your exact logic: difference between Net Payable and Grand Total Amount
                bill_tax = round(abs(net_payable - total_amt), 2)
                
                for t in page_trades:
                    t['Bill_Tax'] = bill_tax
                    trades.append(t)
                    
        return pd.DataFrame(trades)

    def extract_total_charges(self, pdf_path: str) -> float:
        # We handle this per-bill now inside extract_trades to prevent tax bleeding
        return 0.0