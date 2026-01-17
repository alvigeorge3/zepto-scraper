import pandas as pd
import glob
import os
import logging
from database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Zepto_Uploader")

def main():
    # 1. Find latest Zepto CSV
    files = glob.glob("zepto_*.csv")
    if not files:
        logger.error("No Zepto CSV files found to upload.")
        return

    latest_file = max(files, key=os.path.getctime)
    logger.info(f"Read latest file: {latest_file}")
    
    # 2. Read Data
    try:
        df = pd.read_csv(latest_file)
        if df.empty:
            logger.warning("CSV is empty.")
            return
            
        logger.info(f"Loaded {len(df)} rows.")
        
        # 3. Upload
        logger.info("Starting upload to Supabase...")
        db.upsert_products(df, platform="zepto")
        logger.info("Upload process completed.")
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
