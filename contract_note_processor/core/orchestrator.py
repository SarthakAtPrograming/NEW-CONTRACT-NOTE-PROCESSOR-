import pdfplumber
import pandas as pd
from brokers.suresh_rathi import SureshRathiBroker
from brokers.acml import ACMLCapitalBroker
from brokers.zerodha import ZerodhaBroker
from brokers.sihl import SIHLBroker                  # ← NEW
from core.allocator import process_allocation

def identify_broker(pdf_file) -> str:
    pdf_file.seek(0)
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages[:2]:
                text = page.extract_text() or ""
                text_upper = text.upper()
                
                if "SURESH RATHI" in text_upper:
                    return "Suresh Rathi"
                if "ACML" in text_upper:
                    return "ACML Capital"
                if "CONTRACT NOTE CUM TAX INVOICE" in text_upper and "ZERODHA" in text_upper:
                    return "Zerodha"
                if "CONTRACT NOTE CUM BILL" in text_upper and "SIHL" in text_upper:  # ← NEW
                    return "SIHL"                                                     # ← NEW
    except Exception as e:
        raise ValueError(f"Could not read PDF to identify broker: {str(e)}")
    finally:
        pdf_file.seek(0)
        
    return "Unknown"

def process_pdf(pdf_file) -> pd.DataFrame:
    broker_name = identify_broker(pdf_file)
    
    if broker_name == "Suresh Rathi":
        extractor = SureshRathiBroker()
    elif broker_name == "ACML Capital":
        extractor = ACMLCapitalBroker()
    elif broker_name == "Zerodha":
        extractor = ZerodhaBroker()
    elif broker_name == "SIHL":                      # ← NEW
        extractor = SIHLBroker()                       # ← NEW
    else:
        raise ValueError(f"Unsupported or unrecognized Broker in file: {pdf_file.name}")
        
    pdf_file.seek(0)
    trades_df = extractor.extract_trades(pdf_file)
    
    if trades_df.empty:
        raise ValueError(f"No valid trades found in file: {pdf_file.name}")
        
    pdf_file.seek(0)
    total_taxes = extractor.extract_total_charges(pdf_file)
    
    final_df = process_allocation(trades_df, total_taxes)
    final_df['Source PDF'] = pdf_file.name 
    
    return final_df
