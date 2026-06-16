# Phase 5 Scoring Specification (v2_multilingual_explainable)

This document formally specifies the Version 2 verification scoring layer. The V2 classifier replaces keyword frequency counting with an explainable, bounded, deterministic, and multilingual (English, Japanese, French) structured evidence approach.

## Scoring Dimensions

The total possible base score is 100 points, broken into five distinct components. Contextual deductions are applied against the `component_sum`, with the `total_score` clamped between 0 and 100.

| Dimension | Minimum | Maximum | Description |
| :--- | :--- | :--- | :--- |
| Gaming Relevance | 0 | 30 | Evidence that the publication focuses on video games. |
| Media/Editorial | 0 | 25 | Evidence of journalism, reviews, or editorial structure. |
| Market Relevance | 0 | 20 | Explicit signals pointing to target countries or languages. |
| Activity/Freshness | 0 | 15 | Recency of published content. |
| Technical Confidence| 0 | 10 | Quality and depth of the acquired HTML. |
| **Total Base Score** | **0** | **100** | Before deductions |

---

## 1. Gaming Relevance (0 - 30 Points)

Evaluates whether the site's identity and content relate to gaming.

**Positive Signals:**
* **Gaming identity in title or site name (up to 5 pts)**: Matching terms (`video game`, `ゲーム`, `jeu vidéo`) in `page_title` or `og_site_name`.
* **Gaming metadata (up to 4 pts)**: Matching terms in `meta_description` or `og_description`.
* **Gaming navigation or categories (up to 6 pts)**: Matches in `navigation_labels` or headers (e.g., `PC games`, `PCゲーム`, `esports`).
* **Multiple gaming article titles (up to 8 pts)**: Article-like links matching game-specific terms (`review`, `レビュー`, `walkthrough`, `攻略`). 2 points per unique match.
* **Gaming evidence across multiple pages (up to 5 pts)**: If gaming keywords are found not just on the homepage but also in supporting pages (like sitemap articles).
* **Gaming structured metadata (up to 2 pts)**: `VideoGame` or `esports` in JSON-LD.

**Rationale:** Distributes points across structural locations so that a single repetitive keyword spam cannot max out the category.

---

## 2. Media/Editorial Evidence (0 - 25 Points)

Evaluates whether the site is a structured publication rather than a forum or store.

**Positive Signals:**
* **News/reviews/features sections (up to 6 pts)**: Navigation items like `News`, `ニュース`, `actualités`, `Reviews`, `レビュー`. 2 points per unique match.
* **Multiple article-like links (up to 5 pts)**: High volume of detected `article_links` (e.g., >5 links = 5 points).
* **Publication dates (up to 4 pts)**: Detection of explicit `<time>` tags or date structures on the page.
* **Author/byline evidence (up to 4 pts)**: Presence of `author_links` or terms like `written by`, `著者`, `auteur`.
* **Archive/category structure (up to 3 pts)**: Presence of year/month archive links or explicit category tags.
* **Publication/editorial identity (up to 3 pts)**: Terms like `editorial staff`, `編集部`, `journalism`.

**Rationale:** Does not fail sites purely missing bylines (common in corporate Japanese media), but rewards deep editorial structure.

---

## 3. Market Relevance (0 - 20 Points)

Evaluates explicit targeting of a specific country or language demographic.

**Positive Signals:**
* **Country-specific domain or subdomain (up to 4 pts)**: e.g., `.jp`, `.ca`, `.uk`, `.fr`, or `jp.ign.com`.
* **Target language consistency (up to 4 pts)**: `html_language` explicitly matches target (`ja`, `fr`, `en-CA`) or body text heavily matches target language scripts.
* **About/legal location evidence (up to 5 pts)**: Corporate addresses, terms like `Tokyo`, `Montreal`, `Japan` in the footer.
* **Recurring target-country editorial focus (up to 4 pts)**: E.g., `Japan esports`, `Canada gaming news` in headings.
* **Other explicit market evidence (up to 3 pts)**: Currency symbols (`¥`, `$CAD`) or regional rating boards (`CERO`, `ESRB`).

**Negative Market Evidence:**
* **Strong evidence of a different market (up to -8 pts)**: E.g., `.uk` domain when targeting Japan.
* **Language conflict (up to -4 pts)**: `html_language="de"` when targeting `ja`.

**Rationale:** Separates target audience from traffic metrics. A global site might score 0 here but still be verified as media, while a targeted query requires high market scores.

---

## 4. Activity/Freshness (0 - 15 Points)

Evaluates the recency of the publication.

**Positive Signals:**
* **Recent article within 30 days (up to 7 pts)**: At least one parsed date is within the last 30 days.
* **Several recent articles (up to 4 pts)**: More than 3 parsed dates within the last 30 days.
* **Active RSS/archive evidence (up to 2 pts)**: Feed entries detected within 30 days.
* **Homepage visibly updated (up to 2 pts)**: 'Updated at' or 'Modified' metadata in JSON-LD within 30 days.

**Deductions / Uncertain Treatment:**
* **Content older than six months (-5 pts from Activity)**: Stale content reduces activity score.
* **No confirmed dates (0 pts, unknown status)**: We do not penalize, but we award 0 points.
* **Fetch limitation (0 pts, unknown status)**: We do not assume inactivity if we couldn't parse dates due to access control.

**Rationale:** Rejects definitively abandoned sites while avoiding punishing actively updated sites that use non-standard date formats.

---

## 5. Technical Confidence (0 - 10 Points)

Evaluates the depth and reliability of the fetched evidence.

**Positive Signals:**
* **Usable primary HTML (up to 3 pts)**: The main page was fetched and is >10KB.
* **Meaningful content extracted (up to 2 pts)**: We successfully extracted headings, links, and text.
* **Multiple evidence pages (up to 2 pts)**: Supporting pages (like articles from sitemaps) were successfully fetched.
* **Structured metadata (up to 1 pt)**: JSON-LD or OpenGraph is present.
* **Evidence from more than one source type (up to 2 pts)**: e.g., both HTTP HTML and Playwright, or HTML + Sitemap.

**Rationale:** Low technical confidence drives the classifier toward `uncertain` rather than `rejected`, preventing fetch errors from masquerading as negative relevance.

---

## Contextual Deductions

Deductions are subtracted from the sum of the five component scores. Isolated words do not trigger deductions.

1.  **Store / Retailer Deductions (up to -40 pts)**:
    *   Requires combinations: e.g., `cart` + `price` + `buy now` + `product schema`.
    *   Single instances of "buy" inside a review do not penalize.
2.  **Developer / Publisher Deductions (up to -40 pts)**:
    *   Requires corporate identity: e.g., `careers` + `investor relations` + `our games`.
    *   Mentions of developers inside articles do not penalize.
3.  **Hardware Deductions (up to -30 pts)**:
    *   Requires manufacturer/retail identity. Tech journalism discussing hardware is safe.
4.  **Casino / Betting Deductions (up to -80 pts)**:
    *   Triggered heavily by explicit, dominant gambling terminology.

---

## Hard Rejections

A hard rejection immediately sets the decision to `rejected`, overriding any total score.

**Conditions:** Requires at least two independent supporting identity signals, OR one highly definitive structured identity signal (e.g., `OrganizationType: GameDeveloper`).

**Allowed Types:**
*   `dominant_ecommerce_store`
*   `game_developer_corporate_site`
*   `game_publisher_marketing_site`
*   `single_game_marketing_site`
*   `forum_without_editorial_structure`
*   `creator_or_streaming_profile`
*   `esports_team_or_tournament`
*   `hardware_manufacturer_or_retailer`
*   `casino_or_betting_site`
*   `unrelated_corporate_site`
