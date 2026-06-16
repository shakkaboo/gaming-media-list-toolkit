# Phase 5D Input Leakage Audit

## Field Usage Classification

The following fields from the dataset were audited to determine their usage throughout the acquisition, scoring, and evaluation pipelines:

- **domain**: acquisition input, prediction input
- **homepage_url**: acquisition input, prediction input
- **expected_label**: comparison only
- **website_type**: unused
- **target_market**: request context, prediction input
- **language**: request context, prediction input
- **activity_status**: unused
- **label_reason**: unused
- **evidence_summary**: unused
- **reviewer_notes**: unused
- **dataset_split**: unused (except for filtering development vs. protected rows during loading)
- **evidence_url_1**: unused
- **evidence_url_2**: unused

## Target Market & Language Usage Audit

- **target_market**: Used as requested production context (`expected_market`). It helps identify regional evidence but does *not* create gaming relevance on its own. A market score alone cannot meet gaming or media component minimums.
- **language**: Used as request context (`expected_language`). It does *not* directly award gaming or editorial points.
- **GLOBAL**: Market matching explicitly handles `GLOBAL` properly. It does not automatically receive market confirmation without evidence.
- **Mapping**:
  - `JP`: Maps to `expected_language="ja"`, `expected_market="Japan"`
  - `CA`: Maps to `expected_language="en"`, `expected_market="Canada"`
  - `CA-FR`: Maps to `expected_language="fr"`, `expected_market="Canada"`
  - `GLOBAL`: Maps to `expected_language="en"`, `expected_market="GLOBAL"`

## Conclusion
No forbidden dataset fields leak into the acquisition or prediction processes. Ground-truth inputs like `expected_label`, `reviewer_notes`, `website_type`, and manual evidence URLs are strictly unused or only used during final evaluation for metric comparisons.
