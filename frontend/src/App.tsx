import { useState } from 'react';
import { CreateJobForm } from './components/CreateJobForm';
import { JobStatus } from './components/JobStatus';
import { ResultsTable } from './components/ResultsTable';
import { AllWebsitesTable } from './components/AllWebsitesTable';

function App() {
  const [activeTab, setActiveTab] = useState<'discovery' | 'all_websites'>('discovery');
  const [jobId, setJobId] = useState<string | null>(null);
  const [triggerRefresh, setTriggerRefresh] = useState(0);

  const handleJobCreated = (id: string) => {
    setJobId(id);
  };

  const handleRunFinished = () => {
    setTriggerRefresh((prev) => prev + 1);
  };

  const handleJobStateChanged = () => {
    setTriggerRefresh((prev) => prev + 1);
  };

  return (
    <div className="container">
      <header className="flex-between" style={{ alignItems: 'center' }}>
        <h1>Gaming Media Discovery</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className={activeTab === 'discovery' ? 'primary-btn' : ''}
            onClick={() => setActiveTab('discovery')}
          >
            Discovery
          </button>
          <button
            className={activeTab === 'all_websites' ? 'primary-btn' : ''}
            onClick={() => setActiveTab('all_websites')}
          >
            All Websites
          </button>
        </div>
      </header>

      {activeTab === 'discovery' && (
        <>
          {!jobId && (
            <CreateJobForm onJobCreated={handleJobCreated} />
          )}

          {jobId && (
            <>
              <JobStatus
                jobId={jobId}
                onRunFinished={handleRunFinished}
                triggerRefresh={triggerRefresh}
              />
              <ResultsTable
                jobId={jobId}
                triggerRefresh={triggerRefresh}
                onJobStateChanged={handleJobStateChanged}
              />
            </>
          )}
        </>
      )}

      {activeTab === 'all_websites' && (
        <AllWebsitesTable />
      )}
    </div>
  );
}

export default App;
