import React from 'react';
import { ExternalLink, TrendingUp, TrendingDown, Minus, Link as LinkIcon } from 'lucide-react';

const RankingTable = ({ data, title }) => {
  const formatViews = (val) => {
    if (val === 'Needs Verification') {
      return <span style={{fontSize: '0.8rem', color: '#f87171'}}>Needs Verification</span>;
    }
    if (typeof val === 'number') {
      return new Intl.NumberFormat('en-US').format(val);
    }
    return val;
  };

  const getRankClass = (index) => {
    if (index === 0) return 'rank-1';
    if (index === 1) return 'rank-2';
    if (index === 2) return 'rank-3';
    return '';
  };

  const getGrowthDisplay = (growthStr) => {
    if (!growthStr || growthStr === '0%') {
      return <span style={{color: 'var(--text-main)'}}><Minus size={14} style={{display:'inline'}}/> 0%</span>;
    }
    const isPositive = growthStr.startsWith('+');
    const isNegative = growthStr.startsWith('-');
    if (isPositive) {
      return <span style={{color: '#4ade80', fontWeight: '600'}}><TrendingUp size={14} style={{display:'inline', marginRight:'2px'}}/> {growthStr}</span>;
    } else if (isNegative) {
      return <span style={{color: '#f87171', fontWeight: '600'}}><TrendingDown size={14} style={{display:'inline', marginRight:'2px'}}/> {growthStr}</span>;
    }
    return <span>{growthStr}</span>;
  };

  const getSourceDisplay = (sourceUrl) => {
    if (!sourceUrl || sourceUrl === 'Needs Verification') {
      return <span style={{fontSize: '0.8rem', color: '#f87171'}}>Needs Verification</span>;
    }
    return (
      <a href={sourceUrl} target="_blank" rel="noreferrer" style={{color: 'var(--accent-color)'}} title="View Traffic Source">
        <LinkIcon size={16} />
      </a>
    );
  };

  return (
    <div className="glass-panel animate-fade-in delay-3" style={{marginBottom: '2rem'}}>
      <h2 style={{marginTop: 0, marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem'}}>
        {title}
      </h2>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Publication</th>
              <th>Category</th>
              <th>Target Market</th>
              <th>Growth Rate</th>
              <th style={{textAlign: 'center'}}>Traffic Source</th>
              <th style={{textAlign: 'right'}}>Est. Monthly Pageviews</th>
            </tr>
          </thead>
          <tbody>
            {data.map((site, index) => (
              <tr key={index}>
                <td>
                  <span className={`rank-badge ${getRankClass(index)}`}>
                    #{index + 1}
                  </span>
                </td>
                <td>
                  <a href={site['Website URL']} target="_blank" rel="noreferrer" className="site-name">
                    {site['Publication Name']} <ExternalLink size={14} style={{display: 'inline', marginLeft: '4px'}}/>
                  </a>
                </td>
                <td>
                  <span className="badge">{site['Category']}</span>
                </td>
                <td>{site['Target Market'] || site['Country']}</td>
                <td>{getGrowthDisplay(site['Growth Rate'])}</td>
                <td style={{textAlign: 'center'}}>{getSourceDisplay(site['Traffic Source URL'])}</td>
                <td style={{textAlign: 'right', fontWeight: '600', color: 'var(--text-bright)'}}>
                  {formatViews(site['Estimated Monthly Pageviews'])}
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan="7" style={{textAlign: 'center', padding: '3rem'}}>
                  No media found in this category.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RankingTable;
