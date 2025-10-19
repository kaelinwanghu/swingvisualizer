import React from 'react';
import { AppProvider } from './store/AppContext';
import { Layout } from './components/Layout';
import { useElectionData } from './hooks/useElectionData';

function AppContent() {
  useElectionData();
  return <Layout />;
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}