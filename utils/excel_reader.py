import pandas as pd
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("ExcelReader")

def read_input_excel(file_path: str) -> Dict[str, List[str]]:
    """
    Reads an Excel file with columns 'Pincode' and 'Product_Url'.
    Returns a dictionary grouping Product URLs by Pincode.
    
    Format:
    {
        "560001": ["url1", "url2"],
        "110001": ["url3"]
    }
    """
    try:
        df = pd.read_excel(file_path)
        
        # Standardize column names (strip spaces, lowercase)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Check if required columns exist (flexible matching)
        pincode_col = next((c for c in df.columns if 'pincode' in c), None)
        url_col = next((c for c in df.columns if 'url' in c or 'link' in c), None)
        
        if not pincode_col or not url_col:
            raise ValueError(f"Excel file must contain 'Pincode' and 'Product_Url' columns. Found: {df.columns}")
            
        # Group by Pincode
        grouped_data = {}
        for _, row in df.iterrows():
            pincode = str(row[pincode_col]).split('.')[0] # Handle float conversion if any
            url = str(row[url_col]).strip()
            
            if pincode not in grouped_data:
                grouped_data[pincode] = []
            
            if url and url.lower() != 'nan':
                 grouped_data[pincode].append(url)
                 
        logger.info(f"Loaded {len(df)} rows from {file_path}. Found {len(grouped_data)} unique pincodes.")
        return grouped_data
        
    except Exception as e:
        logger.error(f"Failed to read Excel file: {e}")
        return {}
