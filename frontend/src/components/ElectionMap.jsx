import React from 'react';
import { useAppContext } from '../store/AppContext';
import { getCountyColor } from '../utils/colors';
import { PARTY_COLORS } from '../constants';

export function ElectionMap() {
  const { countyData, viewMode, setSelectedCounty, loading, error } = useAppContext();

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading election data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50">
        <div className="text-center text-red-600">
          <p className="font-semibold mb-2">Error loading data</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!countyData) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50">
        <p className="text-gray-600">No data available</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-gray-100 overflow-auto">
      <svg 
        viewBox="0 0 960 600" 
        className="w-full h-auto"
        style={{ maxHeight: '100%' }}
      >
        {countyData.features.map((feature, idx) => {
          const value = viewMode === 'absolute' 
            ? feature.properties.dem_share 
            : feature.properties.swing;
          const color = getCountyColor(value, viewMode, PARTY_COLORS);
          
          // Simple path rendering - you would use d3-geo for proper projection
          return (
            <g 
              key={feature.properties.fips || idx}
              onClick={() => setSelectedCounty(feature)}
              className="cursor-pointer hover:opacity-80 transition-opacity"
            >
              <path
                d={`M ${Math.random() * 960} ${Math.random() * 600}`}
                fill={color}
                stroke="#ffffff"
                strokeWidth="0.5"
              />
            </g>
          );
        })}
      </svg>
      <div className="text-center text-xs text-gray-500 py-2">
        Note: Map rendering requires proper projection setup with d3-geo
      </div>
    </div>
  );
}
