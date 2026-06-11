import os
from src.media_list_builder import MediaListBuilder
from src.utils import setup_logger

logger = setup_logger(__name__)

def main():
    SEED_FILE = "data/seed_sites.csv"
    RAW_CSV = "data/raw_results.csv"
    QUALIFIED_CSV = "data/qualified_media_list.csv"
    QUALIFIED_EXCEL = "data/qualified_media_list.xlsx"

    # Ensure data directory exists
    if not os.path.exists('data'):
        os.makedirs('data')
        
    builder = MediaListBuilder(
        seed_file=SEED_FILE,
        output_csv=QUALIFIED_CSV,
        output_excel=QUALIFIED_EXCEL,
        raw_csv=RAW_CSV
    )
    
    try:
        builder.run()
    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
