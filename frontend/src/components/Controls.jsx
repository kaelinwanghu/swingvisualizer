import React from 'react';
import { useAppContext } from '../store/AppContext';
import { ELECTION_YEARS, PARTY_COLORS } from '../constants';
import { hasSwingData } from '../utils/data';

export function Controls() {
  const { selectedYear, setSelectedYear, viewMode, setViewMode } = useAppContext();
  const swingAvailable = hasSwingData(selectedYear);

  const handleYearChange = (newYear) => {
    setSelectedYear(newYear);
    if (newYear === 2000 && viewMode === 'swing') {
      setViewMode('absolute');
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-xl font-bold mb-4">Election Data Viewer</h2>
      
      <div className="mb-6">
        <label htmlFor="year-select" className="block text-sm font-medium text-gray-700 mb-2">
          Election Year
        </label>
        <select
          value={selectedYear}
          onChange={(e) => handleYearChange(Number(e.target.value))}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {ELECTION_YEARS.map(year => (
            <option key={year} value={year}>{year}</option>
          ))}
        </select>
      </div>

      <div className="mb-6">
        <p className="block text-sm font-medium text-gray-700 mb-2">
          View Mode
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('absolute')}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === 'absolute'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Results
          </button>
          <button
            onClick={() => setViewMode('swing')}
            disabled={!swingAvailable}
            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === 'swing'
                ? 'bg-blue-600 text-white'
                : swingAvailable 
                  ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            Swing
          </button>
        </div>
        {viewMode === 'swing' && swingAvailable && (
          <p className="text-xs text-gray-500 mt-2">
            Showing change from {ELECTION_YEARS[ELECTION_YEARS.indexOf(selectedYear) - 1]} to {selectedYear}
          </p>
        )}
        {!swingAvailable && (
          <p className="text-xs text-gray-500 mt-2">
            Swing mode not available for {selectedYear} (first year)
          </p>
        )}
      </div>

      <div className="border-t pt-4">
        <p className="text-sm font-medium text-gray-700 mb-2">Legend</p>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <div className="w-6 h-6 rounded" style={{ backgroundColor: PARTY_COLORS.DEMOCRAT }}></div>
            <span>Democrat</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <div className="w-6 h-6 rounded" style={{ backgroundColor: PARTY_COLORS.REPUBLICAN }}></div>
            <span>Republican</span>
          </div>
        </div>
      </div>
    </div>
  );
}
