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
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'number' ? Number(value) : value,
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
        <div className="form-actions full-width">
          <button type="submit" disabled={isSubmitting} className="primary-btn">Create Discovery Job</button>
        </div>
      </form>
    </div>
  );
};
