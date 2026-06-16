# Dataset Notes

**Dataset Purpose**
This is a small manually reviewed benchmark based on actual public website evidence. It is not a comprehensive or statistically representative web dataset.

**Record Count**
50

**Methodology**
- Evidence Collection Date: 2026-06-16
- Review Method: Manual public web review (inspection of homepage, about pages, navigation, and article dates).
- No paid data, automated ranking feeds, or synthetic domains were used.
- Traffic and search rankings were strictly NOT used as relevance ground truth.

**Market Interpretation**
`target_market` represents the website's confirmed operating market based on its language, focus, or explicitly declared audience, not just the market in which the search was conducted.

**Class Distribution**
- `gaming_media`: 20
- `not_gaming_media`: 22
- `uncertain`: 8

**Website-Type Distribution**
- `gaming_publication`: 20
- `general_media_gaming_section`: 10
- `game_developer`: 2
- `game_publisher`: 3
- `gaming_retailer`: 5
- `esports_organization`: 1
- `forum_or_community`: 1
- `hardware_or_technology`: 1
- `creator_or_streaming_profile`: 1
- `single_game_site`: 1
- `inactive_or_archived_media`: 2
- `ambiguous`: 3

**Market Distribution**
- Japan: 19
- Canada: 19
- Global: 12

**Activity Distribution**
- `active`: 46
- `inactive`: 2
- `unknown`: 2

**Development/Test Split**
- `development`: 35
- `test`: 15

**Known Uncertain Cases**
- Websites completely blocked by Cloudflare or other anti-bot measures (e.g. `gamewith.jp`) or geo-blocked (e.g. `dmm.com`) were labeled "uncertain" as evidence could not be cleanly verified from a standard US location.
- Major tech sites or large portals with general gaming content (e.g. `news.yahoo.co.jp`, `lapresse.ca`, `theverge.com`) were labeled `uncertain` depending on the perceived independence and consistency of their gaming publication footprint.
