export interface DiscoveryJobCreate {
  target_market: string;
  language: string;
  categories: string[];
  minimum_pageviews: number;
  maximum_queries: number;
  results_per_query: number;
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
