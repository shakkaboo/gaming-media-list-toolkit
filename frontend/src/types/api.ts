export interface DiscoveryJobCreate {
  target_market: string;
  language: string;
  categories: string[];
  minimum_pageviews: number;
  maximum_queries: number;
  results_per_query: number;
  new_websites_only: boolean;
}

export interface DiscoveryJobSummary {
  id: string;
  status: string;
  target_market: string;
  language: string;
  categories: string[];
  minimum_pageviews: number;
  attempt_number: number;
  queries_generated: number;
  queries_completed: number;
  candidates_found: number;
  sites_verified: number;
  websites_uncertain: number;
  sites_rejected: number;
  sites_qualified: number;
  sites_upcoming: number;
  sites_traffic_missing: number;
  contacts_found: number;
  errors_count: number;
  known_domains_skipped: number;
  duplicate_candidates_skipped: number;
  new_websites_only: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface DiscoveryJobDetail extends DiscoveryJobSummary {
  maximum_queries: number;
  results_per_query: number;
  search_provider: string;
  traffic_provider: string;
  duplicates_removed: number;
  candidates_filtered: number;
  sites_fetched: number;
  failure_message?: string;
  updated_at: string;
}

export interface DiscoveryRunSummary {
  job_id: string;
  attempt_number: number;
  final_status: string;
  queries_total: number;
  queries_executed: number;
  queries_skipped: number;
  websites_discovered: number;
  websites_processed: number;
  websites_verified: number;
  websites_uncertain: number;
  websites_rejected: number;
  sites_qualified: number;
  sites_upcoming: number;
  sites_traffic_missing: number;
  errors_count: number;
  known_domains_skipped: number;
  duplicate_candidates_skipped: number;
  new_websites_only: boolean;
}

export interface DiscoveryWebsiteResult {
  website_id: string;
  name?: string;
  domain: string;
  homepage_url: string;
  canonical_key: string;
  is_multitenant: boolean;
  verification_status?: string;
  verification_score?: number;
  confidence?: number;
  activity_status?: string;
  detected_categories: string[];
  classifier_version?: string;
  qualification_status?: string;
  estimated_monthly_pageviews?: number;
  traffic_provider?: string;
  traffic_confidence?: number;
  source_count: number;
  source_queries: string[];
  latest_verified_at?: string;
}

export interface DiscoveryResultsResponse {
  job_id: string;
  job_status: string;
  page: number;
  page_size: number;
  total: number;
  items: DiscoveryWebsiteResult[];
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface WebsiteSummary {
  id: string;
  domain: string;
  homepage_url: string;
  name?: string;
  country?: string;
  language?: string;
  categories?: string[];
  current_verification_status: string;
  current_qualification_status: string;
  manual_review_status: string;
  is_active: boolean;
  last_checked_at?: string;
  created_at: string;
  updated_at: string;

  latest_metric_type?: string;
  latest_monthly_visits?: number;
  latest_pages_per_visit?: number;
  latest_monthly_pageviews?: number;
  latest_estimated_pageviews?: number;
  latest_growth_rate?: number;
  latest_traffic_provider?: string;
  latest_evidence_url?: string;
  latest_traffic_recorded_at?: string;

  best_contact_email?: string;
  best_contact_type?: string;
  effective_review_decision?: string;
}

export interface WebsiteListResponse {
  items: WebsiteSummary[];
  pagination: PaginationMeta;
}

export interface ManualTrafficCreate {
  metric_type: 'monthly_pageviews' | 'monthly_visits' | 'estimated_monthly_pageviews';
  monthly_visits?: number;
  pages_per_visit?: number;
  monthly_pageviews?: number;
  growth_rate?: number;
  measurement_month?: string;
  confidence?: number;
  evidence_url?: string;
  notes?: string;
}

export interface TrafficMetricResponse {
  id: string;
  website_id: string;
  discovery_job_id?: string;
  provider: string;
  metric_type: string;
  monthly_visits?: number;
  pages_per_visit?: number;
  monthly_pageviews?: number;
  estimated_pageviews?: number;
  growth_rate?: number;
  measurement_month?: string;
  confidence?: number;
  is_manual: boolean;
  retrieved_at: string;
  evidence_url?: string;
  notes?: string;
}
