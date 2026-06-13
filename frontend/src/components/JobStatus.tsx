/* eslint-disable */
import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { DiscoveryJobDetail, DiscoveryRunSummary } from '../types/api';
import { ErrorBanner } from './ErrorBanner';

interface Props {
  jobId: string;
  onRunFinished: () => void;
  triggerRefresh: number;
}

export const JobStatus: React.FC<Props> = ({ jobId, onRunFinished, triggerRefresh }) => {
  const [job, setJob] = useState<DiscoveryJobDetail | null>(null);
  const [runSummary, setRunSummary] = useState<DiscoveryRunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const loadJob = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getJob(jobId);
      setJob(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load job');
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadJob();
  }, [loadJob, triggerRefresh]);

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const summary = await api.runJob(jobId);
      setRunSummary(summary);
      await loadJob();
      onRunFinished();
    } catch (err: any) {
      setError(err.message || 'Failed to run job');
    } finally {
      setIsRunning(false);
    }
  };

  if (!job) return <div>Loading job status...</div>;

  return (
    <div className="card">
      <div className="flex-between">
        <h2>Job Status</h2>
        <div>
          <button onClick={loadJob} disabled={isLoading || isRunning}>Refresh</button>
          <button onClick={handleRun} disabled={isRunning || job.status === 'completed'} className="primary-btn" style={{ marginLeft: '10px' }}>
            {isRunning ? 'Running...' : 'Run Discovery'}
          </button>
        </div>
      </div>
      <ErrorBanner error={error} />
      
      <div className="status-grid">
        <div className="stat-box"><strong>ID:</strong> {job.id}</div>
        <div className="stat-box"><strong>Status:</strong> <span className={`badge ${job.status}`}>{job.status}</span></div>
        <div className="stat-box"><strong>Generated Queries:</strong> {job.queries_generated}</div>
        <div className="stat-box"><strong>Candidates Found:</strong> {job.candidates_found}</div>
        <div className="stat-box"><strong>Verified:</strong> {job.sites_verified}</div>
        <div className="stat-box"><strong>Uncertain:</strong> {job.websites_uncertain}</div>
        <div className="stat-box"><strong>Rejected:</strong> {job.sites_rejected}</div>
        <div className="stat-box"><strong>Qualified:</strong> {job.sites_qualified}</div>
        <div className="stat-box"><strong>Upcoming:</strong> {job.sites_upcoming}</div>
        <div className="stat-box"><strong>Traffic Missing:</strong> {job.sites_traffic_missing}</div>
        <div className="stat-box"><strong>Errors:</strong> {job.errors_count}</div>
        <div className="stat-box"><strong>Known domains skipped:</strong> {job.known_domains_skipped ?? 0}</div>
        <div className="stat-box"><strong>Duplicate candidates skipped:</strong> {job.duplicate_candidates_skipped ?? 0}</div>
        <div className="stat-box"><strong>New websites only:</strong> {job.new_websites_only ? 'Yes' : 'No'}</div>
      </div>

      {runSummary && (
        <div className="run-summary">
          <h3>Last Run Summary</h3>
          <p>Status: {runSummary.final_status}</p>
          <p>Discovered: {runSummary.websites_discovered} | Processed: {runSummary.websites_processed}</p>
          <p>known_domains_skipped: {runSummary.known_domains_skipped ?? 0}</p>
          <p>duplicate_candidates_skipped: {runSummary.duplicate_candidates_skipped ?? 0}</p>
        </div>
      )}
    </div>
  );
};
