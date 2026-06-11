# Gaming Media List Toolkit

A dual-module automation toolkit for gathering, qualifying, and presenting high-traffic gaming media publications.

This project was built to automatically filter global gaming and online media publications to find the top-tier targets (over 1,000,000 monthly pageviews), and dynamically present them in a premium glassmorphic React dashboard.

## Modules

The project is split into two distinct modules:

### 1. Media List Generator (Backend/Python)
Located in `/media-list-generator`, this Python automation script:
- Takes a seed list of media websites (`data/seed_sites.csv`) and extracts contact pages, socials, and contact emails.
- Pulls manually-verified traffic data (Visits, Pages Per Visit, Growth Rate, Traffic Source URL) from `data/manual_traffic_input.csv`.
- Calculates strict Pageview estimates (`Visits × Pages per Visit`).
- Categorizes the sites as "Qualified" (>1M pageviews) or "Upcoming" (<1M pageviews).
- Outputs the combined data into CSV and Excel formats, natively injecting the result into the dashboard folder.

**How to run:**
```bash
cd media-list-generator
pip install -r requirements.txt
python main.py
```

### 2. Media List Dashboard (Frontend/React)
Located in `/media-list-dashboard`, this React Vite application:
- Dynamically loads the `dashboard_data.csv` file exported by the backend script.
- Renders a visually stunning, glassmorphic dark-mode dashboard with micro-animations.
- Displays metrics, Growth Rate indicators (green/red), and Traffic Source links.
- Separates the sites cleanly into "Top Tier" and "Upcoming Media" tables.
- Includes native "Export to PDF" and "Export to Excel" buttons directly in the UI.

**How to run:**
```bash
cd media-list-dashboard
npm install
npm run dev
```

## Qualification Criteria
- Must be a gaming or online media publication (Headquarters / Target Market captured).
- Must have an Estimated Monthly Pageview count of **> 1,000,000** to be deemed "Qualified".

## Tech Stack
- **Backend**: Python, Pandas, Requests, BeautifulSoup4
- **Frontend**: React, Vite, PapaParse, jsPDF, SheetJS (xlsx), Lucide-React
- **Styling**: Vanilla CSS (Glassmorphism, CSS Variables, Keyframes)
