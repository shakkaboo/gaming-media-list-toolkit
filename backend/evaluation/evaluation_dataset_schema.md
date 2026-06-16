# Evaluation Dataset Schema

| Column | Description | Allowed Values |
| --- | --- | --- |
| domain | The canonical registered domain | |
| homepage_url | The main URL of the website | |
| expected_label | The assigned classification label | `gaming_media`, `not_gaming_media`, `uncertain` |
| website_type | The recognized type taxonomy | `gaming_publication`, `general_media_gaming_section`, `game_developer`, `game_publisher`, `gaming_retailer`, `esports_organization`, `forum_or_community`, `hardware_or_technology`, `creator_or_streaming_profile`, `single_game_site`, `inactive_or_archived_media`, `unrelated`, `ambiguous` |
| target_market | Primary market or region | |
| language | Primary content language | |
| activity_status | Current publishing activity | `active`, `inactive`, `unknown` |
| label_reason | A concise evidence-based reason | |
| evidence_summary | Key evidence found on the site | |
| reviewer_notes | Additional notes from the reviewer | |
| dataset_split | Partition for evaluation | `development`, `test` |
