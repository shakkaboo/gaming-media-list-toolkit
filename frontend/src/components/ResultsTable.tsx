/* eslint-disable */
import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { DiscoveryWebsiteResult } from '../types/api';
import { ErrorBanner } from './ErrorBanner';
import { TrafficEvidenceForm } from './TrafficEvidenceForm';

interface Props {
  jobId: string;
  triggerRefresh: number;
  onJobStateChanged: () => void;
}

export const ResultsTable: React.FC<Props> = ({ jobId, triggerRefresh, onJobStateChanged }) => {
  const [results, setResults] = useState<DiscoveryWebsiteResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Filters
  const [filterText, setFilterText] = useState('');
  const [verStatus, setVerStatus] = useState('');
  const [qualStatus, setQualStatus] = useState('');
  
  const [activeTrafficForm, setActiveTrafficForm] = useState<string | null>(null);

  const loadResults = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getJobResults(jobId, page, 100);
      setResults(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load results');
    } finally {
      setIsLoading(false);
    }
  }, [jobId, page]);

  useEffect(() => {
    loadResults();
  }, [loadResults, triggerRefresh]);

  const handleTrafficSuccess = () => {
    setActiveTrafficForm(null);
    loadResults();
    onJobStateChanged(); // refresh job counters
  };

  const handleExportCSV = () => {
    if (filteredResults.length === 0) return;
    
    const headers = ['name', 'domain', 'homepage_url', 'verification_status', 'qualification_status', 'estimated_pageviews', 'traffic_provider', 'confidence', 'source_queries'];
    const escapeCsv = (val: any) => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const rows = filteredResults.map(r => [
      escapeCsv(r.name),
      escapeCsv(r.domain),
      escapeCsv(r.homepage_url),
      escapeCsv(r.verification_status),
      escapeCsv(r.qualification_status),
      escapeCsv(r.estimated_monthly_pageviews),
      escapeCsv(r.traffic_provider),
      escapeCsv(r.confidence),
      escapeCsv(r.source_queries.join('; ')),
    ].join(','));

    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `gaming-media-results-${jobId}.csv`;
    link.click();
  };

  const filteredResults = results.filter((r) => {
    if (verStatus && r.verification_status !== verStatus) return false;
    if (qualStatus && r.qualification_status !== qualStatus) return false;
    if (filterText) {
      const lower = filterText.toLowerCase();
      const domainMatch = r.domain?.toLowerCase().includes(lower);
      const nameMatch = r.name?.toLowerCase().includes(lower);
      if (!domainMatch && !nameMatch) return false;
    }
    return true;
  });

  return (
    <div className="card">
      <div className="flex-between">
        <h2>Results ({total} total)</h2>
        <button onClick={handleExportCSV}>Export CSV</button>
      </div>
      <ErrorBanner error={error} />
      
      <div className="filters">
        <input 
          type="text" 
          placeholder="Search by name or domain..." 
          value={filterText} 
          onChange={(e) => setFilterText(e.target.value)} 
        />
        <select value={verStatus} onChange={(e) => setVerStatus(e.target.value)}>
          <option value="">All Verification Status</option>
          <option value="verified">Verified</option>
          <option value="uncertain">Uncertain</option>
          <option value="rejected">Rejected</option>
        </select>
        <select value={qualStatus} onChange={(e) => setQualStatus(e.target.value)}>
          <option value="">All Qualification Status</option>
          <option value="qualified">Qualified</option>
          <option value="upcoming">Upcoming</option>
          <option value="needs_review">Needs Review</option>
          <option value="traffic_missing">Traffic Missing</option>
        </select>
      </div>

      {isLoading && <div>Loading results...</div>}
      {!isLoading && filteredResults.length === 0 && <div>No results found.</div>}

      {!isLoading && filteredResults.length > 0 && (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>Name</th>
                <th>Verification</th>
                <th>Qualification</th>
                <th>Est. Pageviews</th>
                <th>Traffic Provider</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((r) => (
                <React.Fragment key={r.website_id}>
                  <tr>
                    <td><a href={r.homepage_url} target="_blank" rel="noopener noreferrer">{r.domain}</a></td>
                    <td>{r.name || '-'}</td>
                    <td><span className={`badge ${r.verification_status || 'none'}`}>{r.verification_status || 'N/A'}</span></td>
                    <td><span className={`badge ${r.qualification_status || 'none'}`}>{r.qualification_status || 'N/A'}</span></td>
                    <td>{r.estimated_monthly_pageviews != null ? Number(r.estimated_monthly_pageviews).toLocaleString() : '-'}</td>
                    <td>{r.traffic_provider || '-'}</td>
                    <td>
                      <button onClick={() => setActiveTrafficForm(activeTrafficForm === r.website_id ? null : r.website_id)}>
                        {activeTrafficForm === r.website_id ? 'Close' : 'Add traffic evidence'}
                      </button>
                    </td>
                  </tr>
                  {activeTrafficForm === r.website_id && (
                    <tr className="traffic-form-row">
                      <td colSpan={7}>
                        <TrafficEvidenceForm 
                          jobId={jobId} 
                          websiteId={r.website_id} 
                          onSuccess={handleTrafficSuccess}
                          onCancel={() => setActiveTrafficForm(null)}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
