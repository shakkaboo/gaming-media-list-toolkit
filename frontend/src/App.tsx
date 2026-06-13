import { useState } from 'react';
import { CreateJobForm } from './components/CreateJobForm';
import { JobStatus } from './components/JobStatus';
import { ResultsTable } from './components/ResultsTable';

function App() {
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
      <header>
        <h1>Gaming Media Discovery</h1>
      </header>

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
    </div>
  );
}

export default App;
