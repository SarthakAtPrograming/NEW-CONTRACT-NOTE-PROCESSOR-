from abc import ABC, abstractmethod
import pandas as pd

class BaseBroker(ABC):
    
    @abstractmethod
    def extract_metadata(self, pdf_path: str) -> dict:
        """
        Must return a dictionary with:
        {'Trade Date': str, 'Contract Note Number': str, 'Settlement Number': str}
        """
        pass

    @abstractmethod
    def extract_trades(self, pdf_path: str) -> pd.DataFrame:
        """
        Must return a pandas DataFrame containing EXACTLY these columns:
        ['Trade Date', 'Contract Note Number', 'Settlement Number', 
        'Security Name', 'ISIN', 'Buy / Sell', 'Quantity', 'Rate', 'Brokerage']
        """
        pass

    @abstractmethod
    def extract_total_charges(self, pdf_path: str) -> float:
        """
        Extracts the sum total of all statutory taxes and expenses.
        Excludes Brokerage.
        Must return a single float value.
        """
        pass