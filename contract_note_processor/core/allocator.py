import pandas as pd
import numpy as np

def process_allocation(trades_df: pd.DataFrame, total_taxes: float) -> pd.DataFrame:
    
    if 'Gross Value' not in trades_df.columns:
        trades_df['Gross Value'] = trades_df['Quantity'] * trades_df['Rate']

    # YOUR LOGIC: Allocate based on the Debit/Credit value
    if 'Line Total' in trades_df.columns:
        trades_df['Allocation Base'] = trades_df['Line Total']
    else:
        trades_df['Allocation Base'] = trades_df['Gross Value']

    trades_df['Allocated Taxes & Expenses'] = 0.0
    
    # --- BRANCH 1: ACML (Multi-Bill / Per-Settlement Allocation) ---
    if 'Bill_Tax' in trades_df.columns:
        for settle in trades_df['Settlement Number'].unique():
            mask = trades_df['Settlement Number'] == settle
            subset = trades_df[mask]
            
            bill_tax = subset['Bill_Tax'].iloc[0]
            total_base = subset['Allocation Base'].sum()
            
            if total_base == 0:
                trades_df.loc[mask, 'Allocated Taxes & Expenses'] = 0.0
            else:
                allocated = (subset['Allocation Base'] / total_base) * bill_tax
                trades_df.loc[mask, 'Allocated Taxes & Expenses'] = allocated
                
                # Penny park differences locally per bill
                alloc_sum = allocated.sum()
                tax_diff = round(bill_tax - alloc_sum, 2)
                
                if tax_diff != 0:
                    max_idx = subset['Allocation Base'].idxmax()
                    trades_df.loc[max_idx, 'Allocated Taxes & Expenses'] += tax_diff

    # --- BRANCH 2: Suresh Rathi (Single-Bill / Global Allocation) ---
    else:
        total_base = trades_df['Allocation Base'].sum()
        if total_base == 0:
            trades_df['Allocated Taxes & Expenses'] = 0.0
        else:
            trades_df['Allocated Taxes & Expenses'] = (trades_df['Allocation Base'] / total_base) * total_taxes
            
            alloc_sum = trades_df['Allocated Taxes & Expenses'].sum()
            tax_diff = round(total_taxes - alloc_sum, 2)
            
            if tax_diff != 0:
                max_idx = trades_df['Allocation Base'].idxmax()
                trades_df.loc[max_idx, 'Allocated Taxes & Expenses'] += tax_diff

    is_buy = trades_df['Buy / Sell'].astype(str).str.upper().str.strip() == 'BUY'
    
    # Final Net Value Construction
    if 'Line Total' in trades_df.columns:
        trades_df['Net Value'] = np.where(
            is_buy,
            trades_df['Line Total'] + trades_df['Allocated Taxes & Expenses'],
            trades_df['Line Total'] - trades_df['Allocated Taxes & Expenses']
        )
    else:
        trades_df['Net Value'] = np.where(
            is_buy,
            trades_df['Gross Value'] + trades_df['Brokerage'] + trades_df['Allocated Taxes & Expenses'],
            trades_df['Gross Value'] - trades_df['Brokerage'] - trades_df['Allocated Taxes & Expenses']
        )
    
    columns_to_round = ['Quantity', 'Rate', 'Gross Value', 'Brokerage', 'Allocated Taxes & Expenses', 'Net Value']
    trades_df[columns_to_round] = trades_df[columns_to_round].round(2)
    
    final_columns = [
        'Trade Date', 'Contract Note Number', 'Settlement Number', 
        'Security Name', 'ISIN', 'Buy / Sell', 'Quantity', 'Rate', 
        'Gross Value', 'Brokerage', 'Allocated Taxes & Expenses', 'Net Value'
    ]
    
    return trades_df[final_columns]
