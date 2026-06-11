import React from 'react';
import { Globe, BarChart2, Hash } from 'lucide-react';

const DashboardMetrics = ({ data }) => {
  const totalSites = data.length;
  const totalViews = data.reduce((acc, curr) => acc + (Number(curr['Estimated Monthly Pageviews']) || 0), 0);
  
  // Format huge numbers
  const formatNumber = (num) => {
    if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const uniqueCountries = new Set(data.map(item => item['Target Market'] || item['Country'])).size;

  return (
    <div className="metrics-grid">
      <div className="glass-panel metric-card animate-fade-in delay-1">
        <div className="metric-icon">
          <Hash size={24} />
        </div>
        <div className="metric-content">
          <h3>Qualified Sites</h3>
          <p>{totalSites}</p>
        </div>
      </div>
      
      <div className="glass-panel metric-card animate-fade-in delay-2">
        <div className="metric-icon">
          <BarChart2 size={24} />
        </div>
        <div className="metric-content">
          <h3>Total Est. Pageviews</h3>
          <p>{formatNumber(totalViews)}</p>
        </div>
      </div>

      <div className="glass-panel metric-card animate-fade-in delay-3">
        <div className="metric-icon">
          <Globe size={24} />
        </div>
        <div className="metric-content">
          <h3>Target Markets</h3>
          <p>{uniqueCountries}</p>
        </div>
      </div>
    </div>
  );
};

export default DashboardMetrics;
