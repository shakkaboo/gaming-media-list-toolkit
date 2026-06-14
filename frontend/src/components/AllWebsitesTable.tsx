/* eslint-disable */
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { WebsiteListResponse } from '../types/api';
import { ErrorBanner } from './ErrorBanner';

export const AllWebsitesTable: React.FC = () => {
  const [data, setData] = useState<WebsiteListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [page, setPage] = useState(1);
  const pageSize = 50;

  const [filters, setFilters] = useState({
    search: '',
    verification_status: '',
    qualification_status: '',
    country: '',
    language: ''
  });

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.getWebsites({
        page,
        page_size: pageSize,
        search: filters.search,
        verification_status: filters.verification_status,
        qualification_status: filters.qualification_status,
        country: filters.country,
        language: filters.language
      });
      setData(response);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load websites');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, filters]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleFilterChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleApplyFilters = () => {
    setPage(1);
    // Explicit call not needed if loadData depends on page and filters, 
    // but the effect relies on loadData. To avoid double fetch on apply:
    // the state changes will trigger the effect. 
  };

  const handleClearFilters = () => {
    setFilters({
      search: '',
      verification_status: '',
      qualification_status: '',
      country: '',
      language: ''
    });
    setPage(1);
  };

  const formatNumber = (num?: number) => {
    if (num === undefined || num === null) return '—';
    return Number(num).toLocaleString();
  };

  const formatText = (text?: string) => {
    if (!text) return '—';
    return text;
  };

  const exportCSV = () => {
    if (!data || !data.items) return;
    
    const headers = [
      'Name', 'Domain', 'Country', 'Language', 
      'Verification', 'Qualification', 'Monthly Visits', 
      'Pages / Visit', 'Monthly Pageviews', 'Estimated Pageviews', 
      'Traffic Source', 'Last Checked'
    ];
    
    const escapeCSV = (val: any) => {
      if (val === null || val === undefined || val === '—') return '""';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const rows = data.items.map(w => [
      w.name,
      w.domain,
      w.country,
      w.language,
      w.current_verification_status,
      w.current_qualification_status,
      w.latest_monthly_visits,
      w.latest_pages_per_visit,
      w.latest_monthly_pageviews,
      w.latest_estimated_pageviews,
      w.latest_traffic_provider,
      w.last_checked_at
    ].map(escapeCSV).join(','));

    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `all-websites-page-${data.pagination.page}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <div className="flex-between">
        <h2>All Websites</h2>
        <div>
          <button onClick={loadData} disabled={isLoading}>Refresh</button>
          <button onClick={exportCSV} disabled={!data || data.items.length === 0} style={{ marginLeft: '10px' }}>Export current page to CSV</button>
        </div>
      </div>
      <ErrorBanner error={error} />

      <div className="filters-bar" style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '15px', alignItems: 'center' }}>
        <input 
          type="text" 
          name="search" 
          placeholder="Search domain/name..." 
          value={filters.search} 
          onChange={handleFilterChange} 
        />
        <select name="verification_status" value={filters.verification_status} onChange={handleFilterChange}>
          <option value="">Any Verification</option>
          <option value="pending">Pending</option>
          <option value="fetching">Fetching</option>
          <option value="verified">Verified</option>
          <option value="rejected">Rejected</option>
          <option value="uncertain">Uncertain</option>
        </select>
        <select name="qualification_status" value={filters.qualification_status} onChange={handleFilterChange}>
          <option value="">Any Qualification</option>
          <option value="pending">Pending</option>
          <option value="qualified">Qualified</option>
          <option value="unqualified">Unqualified</option>
          <option value="needs_review">Needs Review</option>
        </select>
        <input 
          type="text" 
          name="country" 
          placeholder="Country (e.g. US)" 
          value={filters.country} 
          onChange={handleFilterChange} 
          style={{ width: '120px' }}
        />
        <input 
          type="text" 
          name="language" 
          placeholder="Language (e.g. en)" 
          value={filters.language} 
          onChange={handleFilterChange} 
          style={{ width: '120px' }}
        />
        <button onClick={handleApplyFilters} className="primary-btn">Apply Filters</button>
        <button onClick={handleClearFilters}>Clear</button>
      </div>

      {isLoading ? (
        <div>Loading websites...</div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%', minWidth: '1000px' }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Domain</th>
                <th>Country</th>
                <th>Language</th>
                <th>Verification</th>
                <th>Qualification</th>
                <th>Monthly Visits</th>
                <th>Pages / Visit</th>
                <th>Monthly Pageviews</th>
                <th>Estimated Pageviews</th>
                <th>Traffic Source</th>
                <th>Last Checked</th>
              </tr>
            </thead>
            <tbody>
              {data && data.items.map(site => (
                <tr key={site.id}>
                  <td>{formatText(site.name)}</td>
                  <td>
                    <a href={site.homepage_url} target="_blank" rel="noopener noreferrer">
                      {site.domain}
                    </a>
                  </td>
                  <td>{formatText(site.country)}</td>
                  <td>{formatText(site.language)}</td>
                  <td><span className={`badge ${site.current_verification_status}`}>{site.current_verification_status}</span></td>
                  <td><span className={`badge ${site.current_qualification_status}`}>{site.current_qualification_status}</span></td>
                  <td>{formatNumber(site.latest_monthly_visits)}</td>
                  <td>{formatNumber(site.latest_pages_per_visit)}</td>
                  <td>{formatNumber(site.latest_monthly_pageviews)}</td>
                  <td>{formatNumber(site.latest_estimated_pageviews)}</td>
                  <td>{formatText(site.latest_traffic_provider)}</td>
                  <td>{site.last_checked_at ? new Date(site.last_checked_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
              {(!data || data.items.length === 0) && (
                <tr>
                  <td colSpan={12} style={{ textAlign: 'center' }}>No websites found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {data && data.pagination && (
        <div className="pagination flex-between" style={{ marginTop: '15px', alignItems: 'center' }}>
          <button 
            onClick={() => setPage(p => p - 1)} 
            disabled={!data.pagination.has_previous}
          >
            Previous
          </button>
          <span>Page {data.pagination.page} of {data.pagination.total_pages || 1}</span>
          <button 
            onClick={() => setPage(p => p + 1)} 
            disabled={!data.pagination.has_next}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
