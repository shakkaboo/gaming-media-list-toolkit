import pandas as pd
import os
from src.utils import setup_logger, clean_url

logger = setup_logger(__name__)

class TrafficChecker:
    """Loads manual traffic input data and merges it with existing data."""
    
    def __init__(self, manual_file_path="data/manual_traffic_input.csv"):
        self.manual_file_path = manual_file_path
        self.traffic_data = pd.DataFrame()
        self.load_traffic_data()

    def load_traffic_data(self):
        if os.path.exists(self.manual_file_path):
            try:
                self.traffic_data = pd.read_csv(self.manual_file_path)
                # Clean URLs for merging
                if 'website_url' in self.traffic_data.columns:
                    self.traffic_data['clean_url'] = self.traffic_data['website_url'].apply(
                        lambda x: clean_url(x).rstrip('/')
                    )
                logger.info(f"Loaded manual traffic data from {self.manual_file_path}")
            except Exception as e:
                logger.error(f"Error loading traffic data: {e}")
        else:
            logger.warning(f"Traffic input file not found: {self.manual_file_path}")

    def get_traffic_for_url(self, url):
        """Returns traffic stats for a specific URL."""
        if self.traffic_data.empty or 'clean_url' not in self.traffic_data.columns:
            return None

        c_url = clean_url(url).rstrip('/')
        match = self.traffic_data[self.traffic_data['clean_url'] == c_url]
        
        if not match.empty:
            row = match.iloc[0]
            try:
                visits = float(row.get('monthly_visits', 0))
            except (ValueError, TypeError):
                visits = 0
            try:
                ppv = float(row.get('pages_per_visit', 0))
            except (ValueError, TypeError):
                ppv = 0
                
            growth_rate = str(row.get('growth_rate', '0%'))
            if growth_rate == 'nan':
                growth_rate = '0%'
            
            return {
                "Monthly Visits": visits,
                "Pages per Visit": ppv,
                "Growth Rate": growth_rate,
                "Traffic Source URL": str(row.get('traffic_source_url', ''))
            }
        
        return None
