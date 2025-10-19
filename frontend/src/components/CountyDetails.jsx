import React from 'react';
import { useAppContext } from '../store/AppContext';
import { formatNumber, formatPercent } from '../utils/format';
import { ELECTION_YEARS } from '../constants';

export function CountyDetails() {
  const { selectedCounty, selectedYear, viewMode } = useAppContext();

  if (!selectedCounty) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <p className="text-sm text-gray-500">Click on a county to view details</p>
      </div>
    );
  }

  const county = selectedCounty.properties || {};
  const demShare = county.dem_share || 0;
  const repShare = county.rep_share || 0;
  const winner = demShare > repShare ? 'Democrat' : 'Republican';
  const margin = Math.abs(demShare - repShare);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h3 className="font-bold text-xl mb-1">{county.county_name || county.county}</h3>
      <p className="text-sm text-gray-600 mb-4">{county.state} • {selectedYear}</p>

      {viewMode === 'absolute' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center pb-3 border-b">
            <span className="text-sm font-medium text-gray-700">Winner:</span>
            <span className={`text-base font-bold ${
              winner === 'Democrat' ? 'text-blue-700' : 'text-red-700'
            }`}>
              {winner} +{formatPercent(margin)}
            </span>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium text-blue-700">Democrat</span>
              <span className="font-semibold">{formatPercent(demShare)}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
              <div
                className="bg-blue-600 h-3 rounded-full transition-all"
                style={{ width: `${demShare}%` }}
              ></div>
            </div>

            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium text-red-700">Republican</span>
              <span className="font-semibold">{formatPercent(repShare)}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-red-600 h-3 rounded-full transition-all"
                style={{ width: `${repShare}%` }}
              ></div>
            </div>
          </div>

          <div className="border-t pt-3 space-y-1 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Total Votes:</span>
              <span className="font-medium text-gray-900">{formatNumber(county.total_votes || 0)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>Democratic Votes:</span>
              <span className="font-medium text-gray-900">{formatNumber(county.DEMOCRAT || 0)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>Republican Votes:</span>
              <span className="font-medium text-gray-900">{formatNumber(county.REPUBLICAN || 0)}</span>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'swing' && county.swing !== undefined && (
        <div className="space-y-4">
          <div className="flex justify-between items-center pb-3 border-b">
            <span className="text-sm font-medium text-gray-700">Swing:</span>
            <span className={`text-base font-bold ${
              county.swing > 0 ? 'text-blue-700' : 'text-red-700'
            }`}>
              {county.swing > 0 ? 'D +' : 'R +'}{formatPercent(Math.abs(county.swing))}
            </span>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>{ELECTION_YEARS[ELECTION_YEARS.indexOf(selectedYear) - 1]} Result:</span>
              <span className="font-medium text-gray-900">{formatPercent(county.dem_share_y1 || 0)} D</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>{selectedYear} Result:</span>
              <span className="font-medium text-gray-900">{formatPercent(county.dem_share_y2 || demShare)} D</span>
            </div>
            {county.flipped && (
              <div className="mt-3 px-3 py-2 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg text-center font-medium">
                🔄 County Flipped!
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
