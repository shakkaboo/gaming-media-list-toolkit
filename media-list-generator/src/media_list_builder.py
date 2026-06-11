import pandas as pd
from src.utils import setup_logger
from src.scraper import WebScraper
from src.contact_extractor import ContactExtractor
from src.traffic_checker import TrafficChecker

logger = setup_logger(__name__)

class MediaListBuilder:
    def __init__(self, seed_file, output_csv, output_excel, raw_csv, dashboard_csv="data/dashboard_data.csv"):
        self.seed_file = seed_file
        self.output_csv = output_csv
        self.output_excel = output_excel
        self.raw_csv = raw_csv
        self.dashboard_csv = dashboard_csv
        self.scraper = WebScraper()
        self.extractor = ContactExtractor()
        self.traffic_checker = TrafficChecker()
        
    def run(self):
        logger.info(f"Starting Media List Generator with seeds from {self.seed_file}")
        
        # 1. Load seeds
        try:
            df = pd.read_csv(self.seed_file)
        except Exception as e:
            logger.error(f"Failed to load seeds: {e}")
            return
        
        results = []
        
        # 2. Process each site
        for index, row in df.iterrows():
            url = row.get('website_url')
            name = row.get('publication_name')
            target_market = row.get('target_market')
            category = row.get('category')
            
            logger.info(f"Processing ({index+1}/{len(df)}): {name} - {url}")
            
            # Scrape HTML
            html = self.scraper.fetch_html(url)
            
            # Extract contact info
            extracted_data = self.extractor.extract(html, url)
            
            # Get traffic data
            traffic_data = self.traffic_checker.get_traffic_for_url(url)
            
            if not traffic_data:
                traffic_data = {
                    "Monthly Visits": 0.0,
                    "Pages per Visit": 0.0,
                    "Growth Rate": "0%",
                    "Traffic Source URL": "Needs Verification"
                }
            
            # Calculate pageviews
            try:
                monthly_visits_val = float(traffic_data["Monthly Visits"])
                pages_per_visit_val = float(traffic_data["Pages per Visit"])
                if monthly_visits_val == 0 or pages_per_visit_val == 0:
                    raise ValueError
                est_pageviews = monthly_visits_val * pages_per_visit_val
                monthly_visits_out = monthly_visits_val
                pages_per_visit_out = pages_per_visit_val
                est_pageviews_out = est_pageviews
            except (ValueError, TypeError):
                est_pageviews = 0
                monthly_visits_out = "Needs Verification"
                pages_per_visit_out = "Needs Verification"
                est_pageviews_out = "Needs Verification"

            growth_rate = traffic_data["Growth Rate"]
            source_url = traffic_data["Traffic Source URL"]
            if not source_url:
                source_url = "Needs Verification"
            
            # Qualify
            qualification = "Qualified" if est_pageviews > 1000000 else "Upcoming"
            
            # Note about Canada
            notes = ""
            if target_market == "Canada":
                notes = "May include global audience. Traffic might not be solely Canadian."
            
            result_row = {
                "Target Market": target_market,
                "Publication Name": name,
                "Website URL": url,
                "Category": category,
                "Gaming Focus": "Yes" if "game" in str(category).lower() or "esports" in str(category).lower() else "Partial/Unverified",
                "Monthly Visits": monthly_visits_out,
                "Pages per Visit": pages_per_visit_out,
                "Growth Rate": growth_rate,
                "Estimated Monthly Pageviews": est_pageviews_out,
                "Traffic Source URL": source_url,
                "Contact Email": extracted_data["Contact Email"],
                "Advertising Email": extracted_data["Advertising Email"],
                "Editorial Contact Page": extracted_data["Editorial Contact Page"],
                "Media Kit URL": extracted_data["Media Kit URL"],
                "LinkedIn URL": extracted_data["LinkedIn URL"],
                "X/Twitter URL": extracted_data["X/Twitter URL"],
                "YouTube URL": extracted_data["YouTube URL"],
                "Notes": notes,
                "Qualification Status": qualification
            }
            results.append(result_row)
            
        results_df = pd.DataFrame(results)
        
        # 3. Save raw results
        results_df.to_csv(self.raw_csv, index=False)
        logger.info(f"Saved raw results to {self.raw_csv}")
        
        # 3.5 Save dashboard data (both Qualified and Upcoming)
        dashboard_df = results_df[results_df["Qualification Status"].isin(["Qualified", "Upcoming"])]
        dashboard_df.to_csv(self.dashboard_csv, index=False)
        logger.info(f"Saved dashboard data to {self.dashboard_csv}")
        
        # 4. Filter and save strictly qualified results (>1M)
        qualified_df = results_df[results_df["Qualification Status"] == "Qualified"]
        
        qualified_df.to_csv(self.output_csv, index=False)
        logger.info(f"Saved qualified CSV to {self.output_csv}")
        
        try:
            qualified_df.to_excel(self.output_excel, index=False)
            logger.info(f"Saved qualified Excel to {self.output_excel}")
        except Exception as e:
            logger.error(f"Failed to save to Excel (is openpyxl installed?): {e}")
        
        logger.info("Media list generation complete!")
