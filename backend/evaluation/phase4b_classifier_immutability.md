# Phase 4B Classifier Immutability Record

This document confirms that the classifier logic, rules, and scoring thresholds remain strictly unchanged from the Phase 3 baseline prior to running the Phase 4B evaluation.

## Phase 3 Baseline State

* **Last Phase 3 Commit Hash**: `6966dcad083610d5aa05d9c0c0485ba834c599d3`

## File Hashes

The following SHA256 hashes confirm that the core classification files have not been modified since the Phase 3 baseline:

* `backend/app/verification/classifier.py`: `E6138A11F1A52A2BE649066448BB44B83B6985F427AE351730B897B5E65B21BF`
* `backend/app/verification/rules.py`: `DBF6129103F593EDA1DC84715E4486EA8BC0F1008CC2E8B5CC6AC67DA9DC07EB`
* `backend/app/verification/html_analyzer.py`: `F30F201B813AEE041443133B70597A1F69714117485E065A176DBA8EDBCFBDF3`

*Note: `git diff 6966dcad083610d5aa05d9c0c0485ba834c599d3 -- backend/app/verification/classifier.py backend/app/verification/rules.py backend/app/verification/html_analyzer.py` returns no differences.*

## Verification of Unchanged Parameters

The classifier parameters remain identical to the Phase 3 configuration:

### Thresholds
* **Verified Threshold**: `70` (`GAMING_MEDIA_VERIFIED_THRESHOLD` in `app/config.py`)
* **Uncertain Threshold**: `40` (`GAMING_MEDIA_UNCERTAIN_THRESHOLD` in `app/config.py`)
* **Minimum Gaming Score**: `18` (Enforced in `classifier.py`)
* **Minimum Editorial Score**: `18` (Enforced in `classifier.py`)

### Component Weights
* **Gaming Score**: Maximum `35`
    * `gaming_meta`: Up to `15`
    * `platform_nav`: Up to `15`
    * `gaming_structured_data`: `5`
* **Editorial Score**: Maximum `35`
    * `editorial_nav`: Up to `20`
    * `article_links`: Up to `10`
    * `editorial_schema`: `10`
* **Activity Score**: Maximum `15`
    * `active_recently` (<= 90 days): `15`
    * `possibly_active` (<= 365 days): `7`
    * `stale` (> 365 days): `0`
* **Identity Score**: Maximum `15`
    * `og_site_name`: `2`
    * `author_links`: Up to `4`
    * `about_links`: `3`
    * `publication_text`: `6`

### Negative Penalties
* **Total Negative Penalty**: Maximum `80`
    * `store_signals`: Up to `-40`
    * `developer_signals`: Up to `-40`
    * `casino_signals`: `-80`
    * `hardware_signals`: Up to `-30`

These values strictly preserve the production classifier's ruleset. Phase 4B evaluates only the impact of improved evidence acquisition on this immutable classifier.
