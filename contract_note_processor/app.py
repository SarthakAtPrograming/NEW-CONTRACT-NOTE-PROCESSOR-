import streamlit as st
import pandas as pd
from io import BytesIO
from core.orchestrator import process_pdf

# 1. Page Configuration (Must be first)
st.set_page_config(
    page_title="Contract Note Processor | A.O. Mittal & Associates", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. High-Contrast Professional UI/UX Injection
st.markdown("""
    <style>
    /* Import professional typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Deep Corporate Navy Background */
    .stApp {
        background-color: #0B1121;
    }

    /* Force ALL text to Pure Bright White for perfect contrast */
    h1, h2, h3, h4, h5, h6, p, label, span, div, .stMarkdown {
        color: #FFFFFF !important;
    }

    /* Subtext for softer contrast (Bright Light Gray) */
    .subtext {
        color: #E2E8F0 !important;
    }

    /* Clean File Uploader - Navy background, Bright Blue Border */
    .stFileUploader > div > div {
        background-color: #1E293B !important;
        border: 2px dashed #0EA5E9 !important;
        border-radius: 8px;
        transition: all 0.2s ease-in-out;
    }
    .stFileUploader > div > div:hover {
        border-color: #38BDF8 !important;
        background-color: #0F172A !important;
    }

    /* Primary Action Button - Bright Sky Blue */
    button[kind="primary"] {
        background-color: #0EA5E9 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.6rem 2rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px rgba(14, 165, 233, 0.3);
    }
    button[kind="primary"]:hover {
        background-color: #38BDF8 !important;
        box-shadow: 0 6px 12px rgba(14, 165, 233, 0.5);
        transform: translateY(-2px);
    }

    /* Secondary Download Button - Bright Outline */
    button[kind="secondary"] {
        background-color: transparent !important;
        color: #38BDF8 !important;
        border: 2px solid #38BDF8 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
    }
    button[kind="secondary"]:hover {
        background-color: #38BDF8 !important;
        color: #0B1121 !important;
    }

    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Fixed Professional Footer (Slightly darker navy to anchor the app) */
    .custom-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #05080F;
        border-top: 2px solid #0EA5E9;
        padding: 16px 0;
        text-align: center;
        font-size: 15px;
        font-weight: 500;
        color: #FFFFFF;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 3vw;
        letter-spacing: 0.5px;
        z-index: 9999;
    }
    .footer-accent {
        color: #0EA5E9 !important;
        font-weight: 700;
    }
    
    /* Buffer for footer */
    .block-container {
        padding-bottom: 100px;
        padding-top: 3rem;
    }
    </style>
    
    <div class="custom-footer">
        <span>A.O. Mittal & Associates</span>
        <span class="footer-accent">|</span>
        <span>CA Akash Agarwal</span>
        <span class="footer-accent">|</span>
        <span>Sarthak Jain</span>
    </div>
    """, unsafe_allow_html=True)

# 3. Clean Header (High Contrast White)
st.markdown("<h1 style='text-align: center; font-weight: 700; font-size: 2.5rem; margin-bottom: 0.5rem;'>Contract Note Processor</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtext' style='text-align: center; margin-bottom: 3rem; font-size: 1.2rem;'>Automated Trade Extraction & Proportional Tax Allocation</p>", unsafe_allow_html=True)

# 4. Centered Interactive UI
left_spacer, center_col, right_spacer = st.columns([1, 2, 1])

with center_col:
    uploaded_files = st.file_uploader(
        "Upload Indian Stock Broker Contract Notes (PDF)", 
        type="pdf", 
        accept_multiple_files=True
    )

    st.write("") # Spacer

    if st.button("Process Contract Notes", type="primary", use_container_width=True):
        if not uploaded_files:
            st.warning("Please upload at least one PDF to begin.")
        else:
            all_trades = []
            error_files = []
            
            # Execution logic is completely untouched
            with st.spinner("Processing PDFs and allocating taxes..."):
                for file in uploaded_files:
                    try:
                        df = process_pdf(file)
                        all_trades.append(df)
                    except Exception as e:
                        error_files.append((file.name, str(e)))
            
            if all_trades:
                final_master_df = pd.concat(all_trades, ignore_index=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    final_master_df.to_excel(writer, index=False, sheet_name='Allocated Trades')
                excel_data = output.getvalue()
                
                st.success(f"Success: Processed {len(all_trades)} document(s) successfully.")
                
                st.download_button(
                    label="DOWNLOAD EXCEL WORKBOOK (.xlsx)",
                    data=excel_data,
                    file_name="Processed_Contract_Notes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.markdown("<br><h3 style='font-weight: 600;'>Data Preview</h3>", unsafe_allow_html=True)
                st.dataframe(final_master_df, use_container_width=True, hide_index=True)
                
            if error_files:
                st.error(f"Failed to process {len(error_files)} file(s).")
                for err in error_files:
                    st.write(f"- **{err[0]}**: {err[1]}")