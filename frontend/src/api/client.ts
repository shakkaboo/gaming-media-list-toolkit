/* eslint-disable */
import type { DiscoveryJobCreate, DiscoveryJobDetail, DiscoveryRunSummary, DiscoveryResultsResponse, ManualTrafficCreate, TrafficMetricResponse, WebsiteListResponse } from '../types/api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          message = errorData.detail.map((e: any) => `${e.loc?.join('.')} ${e.msg}`).join(', ');
        } else {
          message = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } else if (errorData.message) {
        message = errorData.message;
      }
    } catch (e) {
      // Ignore JSON parse errors
    }
    throw new Error(message);
  }

  return response.json();
}

export const api = {
  createJob: (payload: DiscoveryJobCreate): Promise<DiscoveryJobDetail> => 
    request('/api/discovery/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
    
  runJob: (jobId: string): Promise<DiscoveryRunSummary> => 
    request(`/api/discovery/jobs/${jobId}/run`, {
      method: 'POST',
    }),
    
  getJob: (jobId: string): Promise<DiscoveryJobDetail> => 
    request(`/api/discovery/jobs/${jobId}`),
    
  getJobResults: (jobId: string, page = 1, pageSize = 100): Promise<DiscoveryResultsResponse> => 
    request(`/api/discovery/jobs/${jobId}/results?page=${page}&page_size=${pageSize}`),
    
  submitTrafficEvidence: (websiteId: string, jobId: string, payload: ManualTrafficCreate): Promise<TrafficMetricResponse> => 
    request(`/api/websites/${websiteId}/traffic-evidence?discovery_job_id=${jobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getWebsites: (params: Record<string, string | number | boolean>): Promise<WebsiteListResponse> => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    return request(`/api/websites?${searchParams.toString()}`);
  }
};
