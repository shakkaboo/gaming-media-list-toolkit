import React from 'react';

export const ErrorBanner: React.FC<{ error: string | null }> = ({ error }) => {
  if (!error) return null;
  return (
    <div className="error-banner">
      <strong>Error:</strong> {error}
    </div>
  );
};
