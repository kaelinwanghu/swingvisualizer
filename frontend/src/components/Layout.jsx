import React from 'react';
import { Controls } from './Controls';
import { CountyDetails } from './CountyDetails';
import { Map } from './ElectionMap';

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-4">
        <header className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">
            American Election Swing Visualizer
          </h1>
          <p className="text-gray-600 mt-1">County-level presidential election results 2000-2024</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <aside className="lg:col-span-1 space-y-4">
            <Controls />
            <CountyDetails />
          </aside>

          <main className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-lg overflow-hidden" style={{ height: '600px' }}>
              <Map />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}