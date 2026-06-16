# Official Labelling Guidelines

A gaming-media website is a website whose primary or recurring activity is publishing organized gaming-related news, reviews, analysis, features, interviews, guides, or industry coverage for an audience.

The website must satisfy both:
1. Meaningful gaming relevance
2. Meaningful editorial or publication structure

Gaming terminology alone is not sufficient.

## Evaluation Labels

Exactly one of the following three evaluation labels must be assigned:

### gaming_media

Assign when there is sufficient evidence that the website regularly publishes organized gaming-related editorial content.

Expected signals may include:
- gaming-focused navigation;
- repeated gaming articles;
- news, reviews, analysis, features, interviews, or guides;
- publication dates;
- author or editorial attribution;
- archive or category structure;
- active publishing.

### not_gaming_media

Assign when the primary site type is not a gaming-media publication.

Examples:
- game developer;
- game publisher marketing site;
- gaming retailer or marketplace;
- single-game landing page;
- hardware manufacturer;
- esports team or tournament;
- forum or community without meaningful editorial publishing;
- social-media or streaming profile;
- unrelated company or organization;
- general website with only incidental gaming coverage.

### uncertain

Assign only when available evidence is insufficient or genuinely conflicting.

Examples:
- fetch blocked;
- JavaScript content unavailable;
- unclear publication structure;
- mixed general-media and gaming focus;
- inactive or partially archived website;
- ambiguous market relevance.

Do not use uncertain merely because the reviewer is unsure. The reason must be documented.

## Website-Type Taxonomy

| Website type                 | Normal expected label                                                            |
| ---------------------------- | -------------------------------------------------------------------------------- |
| gaming_publication           | gaming_media                                                                     |
| general_media_gaming_section | uncertain or not_gaming_media, depending on substantial recurring coverage       |
| game_developer               | not_gaming_media                                                                 |
| game_publisher               | not_gaming_media                                                                 |
| gaming_retailer              | not_gaming_media                                                                 |
| esports_organization         | not_gaming_media                                                                 |
| forum_or_community           | not_gaming_media unless it has a genuine editorial publication function          |
| hardware_or_technology       | not_gaming_media unless gaming media is a primary recurring publication function |
| creator_or_streaming_profile | not_gaming_media                                                                 |
| single_game_site             | not_gaming_media                                                                 |
| inactive_or_archived_media   | uncertain                                                                        |
| unrelated                    | not_gaming_media                                                                 |
| ambiguous                    | uncertain                                                                        |

## Evidence Hierarchy

### Strong evidence
- multiple recent gaming articles;
- gaming-focused primary navigation;
- article dates and bylines;
- archives or categories;
- clear publication identity;
- recurring editorial output.

### Supporting evidence
- gaming terms in metadata;
- Open Graph site name;
- JSON-LD article schemas;
- About or editorial-team page;
- RSS or sitemap evidence.

### Weak evidence
- one gaming keyword;
- one gaming article;
- appearance in gaming search results;
- gaming term in the URL;
- one country mention.

### Contradictory evidence
- shopping cart or product catalogue dominates;
- developer/publisher product promotion dominates;
- team roster or tournament schedule dominates;
- forum threads dominate;
- static game marketing content dominates;
- site purpose is clearly unrelated.

Weak evidence alone must never produce `gaming_media`.

## Market Relevance

Market relevance is a separate evidence dimension and does not by itself determine whether a site is gaming media.

Possible market evidence:
- country-specific domain or subdomain;
- consistent target language;
- About/legal-page location;
- recurring target-country coverage;
- geographic audience evidence when available.

Search-result ranking for a country query is weak evidence only.

## Activity Expectations

- active: recent relevant publication evidence exists
- inactive: clear evidence that publishing has stopped or is substantially outdated
- unknown: publication dates or content could not be evaluated

Do not automatically classify an inactive publication as unrelated. It may receive `uncertain` depending on the business requirement.

## Reviewer Procedure

1. Open the homepage.
2. Inspect primary navigation.
3. Inspect at least three recent content items where available.
4. Check publication dates.
5. Check author or editorial evidence.
6. Inspect About or publication-identity information.
7. Identify exclusion signals.
8. Determine website type.
9. Assign label.
10. Write a concise evidence-based reason.

Do not use traffic metrics to decide whether the site is gaming media.

## Disagreement Handling

When reviewers disagree:
- both labels are retained temporarily;
- evidence and reasons are compared;
- the disagreement is resolved using the written definition;
- unresolved cases become `uncertain`;
- the final adjudicated label is recorded separately.
