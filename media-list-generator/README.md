# AI-Powered Media List Generator

## 1. What the project does
This project generates a qualified media list of gaming and online media websites in Japan and Canada. It visits seed websites, extracts contact information (emails, social media links, contact pages, advertising pages), integrates manually provided traffic data, calculates estimated monthly pageviews, and filters out sites that have less than 1,000,000 estimated monthly pageviews. 

The final output is both a CSV and an Excel file containing highly qualified gaming media contacts.

## 2. How to install
First, ensure you have Python 3.8+ installed.

1. Clone or download this repository.
2. Open a terminal/command prompt in the project folder.
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. (Optional) Copy `.env.example` to `.env` if you plan to add API keys later.

## 3. How to run
Run the main script from the root directory:
```bash
python main.py
```
This will:
- Read `data/seed_sites.csv`.
- Read `data/manual_traffic_input.csv`.
- Process each URL and output results to `data/raw_results.csv`, `data/qualified_media_list.csv`, and `data/qualified_media_list.xlsx`.
- Execution logs are saved to `logs/app.log`.

## 4. How to add seed websites
Open `data/seed_sites.csv` and add a new row with the following columns:
- `country`: e.g., Japan, Canada
- `publication_name`: The name of the publication.
- `website_url`: The URL (e.g., https://example.com).
- `category`: e.g., Gaming news, Game guides.

## 5. How to add traffic data
Traffic tools (like Similarweb or Semrush) strictly prohibit scraping. To ensure accurate data and compliance:
1. Go to a traffic analysis tool (e.g., [Similarweb](https://www.similarweb.com/)).
2. Look up the website URL.
3. Open `data/manual_traffic_input.csv`.
4. Add the URL, Monthly Visits, Pages per Visit, and the traffic source URL.

Example:
```csv
website_url,monthly_visits,pages_per_visit,traffic_source_url
https://example.com/,2500000,3.2,https://www.similarweb.com/website/example.com/
```

## 6. How pageviews are calculated
The formula used is:
**Estimated Monthly Pageviews = Monthly Visits × Pages per Visit**

## 7. Why traffic data should be verified manually
Scraping tools like Similarweb and Semrush violates their Terms of Service and often leads to immediate IP bans or legal issues. By manually sourcing this specific metric or utilizing an official API (which is often expensive), you ensure the tool remains functional and compliant.

## 8. Limitations
- The contact extractor relies on standard regex and keyword matching. It may miss emails obfuscated by JavaScript or contact forms.
- Traffic data is not dynamically scraped, so it must be periodically updated in the manual CSV.

## 9. Future improvements
- Integration with ScrapeGraphAI or OpenAI for more intelligent "reading" of contact and advertising pages.
- Official API integration with Similarweb/Semrush to automate traffic fetching legally.
- Support for more countries and specific gaming sub-niches.
