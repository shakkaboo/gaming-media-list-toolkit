import React, { useEffect, useState } from 'react';
import Papa from 'papaparse';
import DashboardMetrics from './components/DashboardMetrics';
import RankingTable from './components/RankingTable';
import ExportButtons from './components/ExportButtons';
import { Activity } from 'lucide-react';

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch and parse the CSV
    const loadCSV = async () => {
      try {
        const response = await fetch('/dashboard_data.csv');
        if (!response.ok) {
          throw new Error('Could not fetch CSV file. Please make sure dashboard_data.csv is in the public folder.');
        }
        const text = await response.text();
        
        Papa.parse(text, {
          header: true,
          dynamicTyping: true,
          skipEmptyLines: true,
          complete: (results) => {
            const parsedData = results.data;
            // Sort by Estimated Monthly Pageviews descending
            const sorted = parsedData.sort((a, b) => 
              (b['Estimated Monthly Pageviews'] || 0) - (a['Estimated Monthly Pageviews'] || 0)
            );
            setData(sorted);
            setLoading(false);
          },
          error: (err) => {
            setError(err.message);
            setLoading(false);
          }
        });
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    loadCSV();
  }, []);

  const qualifiedMedia = data.filter(item => item['Qualification Status'] === 'Qualified');
  const upcomingMedia = data.filter(item => item['Qualification Status'] === 'Upcoming');

  return (
    <div className="app-container">
      <header className="header animate-fade-in">
        <h1>Global Gaming Media Rankings</h1>
        <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-color)'}}>
          <Activity size={20} />
          <span style={{fontWeight: 600, letterSpacing: '0.05em'}}>LIVE DASHBOARD</span>
        </div>
      </header>

      {error ? (
        <div className="glass-panel" style={{borderColor: 'red', color: 'red'}}>
          <h3>Error loading data</h3>
          <p>{error}</p>
        </div>
      ) : (
        <>
          <ExportButtons data={data} />
          <DashboardMetrics data={data} />
          <RankingTable data={qualifiedMedia} title="Top Qualified Media (>1M Pageviews)" />
          {upcomingMedia.length > 0 && (
            <RankingTable data={upcomingMedia} title="Upcoming Media (<1M Pageviews)" />
          )}
        </>
      )}
    </div>
  );
}

export default App;
