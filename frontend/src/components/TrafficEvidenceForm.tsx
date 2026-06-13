/* eslint-disable */
import React, { useState } from 'react';
import { api } from '../api/client';
import type { ManualTrafficCreate } from '../types/api';

interface Props {
  websiteId: string;
  jobId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export const TrafficEvidenceForm: React.FC<Props> = ({ websiteId, jobId, onSuccess, onCancel }) => {
  const [metricType, setMetricType] = useState<ManualTrafficCreate['metric_type']>('monthly_pageviews');
  const [monthlyPageviews, setMonthlyPageviews] = useState('');
  const [monthlyVisits, setMonthlyVisits] = useState('');
  const [pagesPerVisit, setPagesPerVisit] = useState('');
  const [evidenceUrl, setEvidenceUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const payload: ManualTrafficCreate = { metric_type: metricType };
      if (metricType === 'monthly_pageviews') {
        payload.monthly_pageviews = Number(monthlyPageviews);
      } else {
        payload.monthly_visits = Number(monthlyVisits);
        if (pagesPerVisit) payload.pages_per_visit = Number(pagesPerVisit);
      }
      if (evidenceUrl) payload.evidence_url = evidenceUrl;
      if (notes) payload.notes = notes;

      await api.submitTrafficEvidence(websiteId, jobId, payload);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to submit traffic evidence');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="traffic-form-container">
      <form onSubmit={handleSubmit} className="traffic-form">
        {error && <div className="error-text">{error}</div>}
        <div className="form-group">
          <label>Metric Type</label>
          <select value={metricType} onChange={(e) => setMetricType(e.target.value as any)}>
            <option value="monthly_pageviews">Monthly Pageviews (Direct)</option>
            <option value="estimated_monthly_pageviews">Estimated Monthly Pageviews</option>
            <option value="monthly_visits">Monthly Visits (No estimate)</option>
          </select>
        </div>

        {metricType === 'monthly_pageviews' && (
          <div className="form-group">
            <label>Monthly Pageviews *</label>
            <input type="number" required value={monthlyPageviews} onChange={(e) => setMonthlyPageviews(e.target.value)} />
          </div>
        )}

        {(metricType === 'estimated_monthly_pageviews' || metricType === 'monthly_visits') && (
          <>
            <div className="form-group">
              <label>Monthly Visits *</label>
              <input type="number" required value={monthlyVisits} onChange={(e) => setMonthlyVisits(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Pages per Visit {metricType === 'estimated_monthly_pageviews' ? '*' : '(Optional)'}</label>
              <input type="number" step="0.01" required={metricType === 'estimated_monthly_pageviews'} value={pagesPerVisit} onChange={(e) => setPagesPerVisit(e.target.value)} />
            </div>
          </>
        )}

        <div className="form-group">
          <label>Evidence URL</label>
          <input type="url" value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} />
        </div>

        <div className="form-group">
          <label>Notes</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        <div className="form-actions">
          <button type="button" onClick={onCancel} disabled={isSubmitting}>Cancel</button>
          <button type="submit" disabled={isSubmitting} className="primary-btn">Submit</button>
        </div>
      </form>
    </div>
  );
};
