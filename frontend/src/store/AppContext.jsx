import React, { createContext, useContext, useState, useMemo } from 'react';
import PropTypes from 'prop-types';

const AppContext = createContext();

export function AppProvider({ children }) {
  const [selectedYear, setSelectedYear] = useState(2024);
  const [viewMode, setViewMode] = useState('absolute');
  const [selectedCounty, setSelectedCounty] = useState(null);
  const [countyData, setCountyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const value = useMemo(() => ({
    selectedYear,
    setSelectedYear,
    viewMode,
    setViewMode,
    selectedCounty,
    setSelectedCounty,
    countyData,
    setCountyData,
    loading,
    setLoading,
    error,
    setError
  }), [selectedYear, viewMode, selectedCounty, countyData, loading, error]);

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

AppProvider.propTypes = {
  children: PropTypes.node.isRequired
};

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
}
