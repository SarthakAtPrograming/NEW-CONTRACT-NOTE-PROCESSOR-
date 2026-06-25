import pdfplumber
import pandas as pd
from brokers.suresh_rathi import SureshRathiBroker
from brokers.acml import ACMLCapitalBroker
from brokers.zerodha import ZerodhaBroker          # ← NEW
from core.allocator import process_allocation

def identify_broker(pdf_file) -> str:
    """
    Reads the PDF to identify the broker.
    Forcibly resets the Streamlit file buffer before and after reading.
    """
    pdf_file.seek(0)  # Reset cursor before reading
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Scan the first two pages to ensure we don't miss the header
            for page in pdf.pages[:2]:
                text = page.extract_text() or ""
                text_upper = text.upper()
                
                if "SURESH RATHI" in text_upper:
                    return "Suresh Rathi"
                if "ACML" in text_upper:
                    return "ACML Capital"
                if "CONTRACT NOTE CUM TAX INVOICE" in text_upper and "ZERODHA" in text_upper:  # ← NEW
                    return "Zerodha"                                                            # ← NEW
    except Exception as e:
        raise ValueError(f"Could not read PDF to identify broker: {str(e)}")
    finally:
        pdf_file.seek(0)  # Reset cursor again so the main extractor can read it
        
    return "Unknown"

def process_pdf(pdf_file) -> pd.DataFrame:
    """
    The main pipeline: Identify -> Extract -> Allocate -> Return Clean Data.
    """
    broker_name = identify_broker(pdf_file)
    
    # Route to the correct extraction engine
    if broker_name == "Suresh Rathi":
        extractor = SureshRathiBroker()
    elif broker_name == "ACML Capital":
        extractor = ACMLCapitalBroker()
    elif broker_name == "Zerodha":                  # ← NEW
        extractor = ZerodhaBroker()                  # ← NEW
    else:
        raise ValueError(f"Unsupported or unrecognized Broker in file: {pdf_file.name}")
        
    pdf_file.seek(0)  # Ensure cursor is at 0 before extracting trades
    trades_df = extractor.extract_trades(pdf_file)
    
    if trades_df.empty:
        raise ValueError(f"No valid trades found in file: {pdf_file.name}")
        
    pdf_file.seek(0)  # Ensure cursor is at 0 before extracting taxes
    total_taxes = extractor.extract_total_charges(pdf_file)
    
    # Run the Math Engine (Allocation & Net Value)
    final_df = process_allocation(trades_df, total_taxes)
    
    # Attach the source file name for audit trace
    final_df['Source PDF'] = pdf_file.name 
    
    return final_df