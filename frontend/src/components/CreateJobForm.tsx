/* eslint-disable */
import React, { useState } from 'react';
import { api } from '../api/client';
import type { DiscoveryJobCreate } from '../types/api';
import { ErrorBanner } from './ErrorBanner';

interface Props {
  onJobCreated: (jobId: string) => void;
}

export const CreateJobForm: React.FC<Props> = ({ onJobCreated }) => {
  const [formData, setFormData] = useState({
    target_market: 'US',
    language: 'en',
    categories: 'gaming news',
    minimum_pageviews: 1000000,
    maximum_queries: 1,
    results_per_query: 10,
    new_websites_only: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const payload: DiscoveryJobCreate = {
        ...formData,
        categories: formData.categories.split(',').map((c) => c.trim()).filter(Boolean),
      };
      const job = await api.createJob(payload);
      onJobCreated(job.id);
    } catch (err: any) {
      setError(err.message || 'Failed to create job');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? Number(value) : value,
    }));
  };

  return (
    <div className="card">
      <h2>Create Job</h2>
      <ErrorBanner error={error} />
      <form onSubmit={handleSubmit} className="form-grid">
        <div className="form-group">
          <label>Target Market</label>
          <input name="target_market" value={formData.target_market} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Language</label>
          <input name="language" value={formData.language} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Categories (comma-separated)</label>
          <input name="categories" value={formData.categories} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Minimum Pageviews</label>
          <input name="minimum_pageviews" type="number" value={formData.minimum_pageviews} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Maximum Queries</label>
          <input name="maximum_queries" type="number" value={formData.maximum_queries} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Results Per Query</label>
          <input name="results_per_query" type="number" value={formData.results_per_query} onChange={handleChange} required />
        </div>
        <div className="form-group full-width" style={{ gridColumn: '1 / -1' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" name="new_websites_only" checked={formData.new_websites_only} onChange={handleChange} />
            Only show newly discovered websites
          </label>
          <small style={{ color: '#666', display: 'block', marginTop: '4px' }}>
            Skip domains that were already discovered in earlier jobs.
          </small>
        </div>
        <div className="form-actions full-width" style={{ gridColumn: '1 / -1' }}>
          <button type="submit" disabled={isSubmitting} className="primary-btn">Create Discovery Job</button>
        </div>
      </form>
    </div>
  );
};
