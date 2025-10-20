import React, { useRef, useEffect, useState } from 'react';
import Map, { Source, Layer } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useAppContext } from '../store/AppContext';
import { getCountyColor } from '../utils/colors';
import { PARTY_COLORS } from '../constants';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

export function ElectionMap() {
  const mapRef = useRef(null);
  const { countyData, viewMode, setSelectedCounty, loading, error } = useAppContext();
  const [viewState, setViewState] = useState({
    longitude: -98.5795,
    latitude: 39.8283,
    zoom: 4
  });
  const [hoverInfo, setHoverInfo] = useState(null);

  // County fill layer style
  const countyFillLayer = {
    id: 'county-fills',
    type: 'fill',
    paint: {
      'fill-color': [
        'case',
        ['has', 'dem_share'],
        // Will be set dynamically based on data
        '#cccccc',
        '#cccccc'
      ],
      'fill-opacity': [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        0.9,
        0.7
      ]
    }
  };

  // County border layer style
  const countyBorderLayer = {
    id: 'county-borders',
    type: 'line',
    paint: {
      'line-color': '#ffffff',
      'line-width': 0.5
    }
  };

  // Update colors when data or mode changes
  useEffect(() => {
    if (!countyData || !mapRef.current) return;

    const map = mapRef.current.getMap();
    
    // Create color expression based on current mode
    const colorExpression = ['case'];
    
    for (const feature of countyData.features) {
      const value = viewMode === 'absolute' 
        ? feature.properties.dem_share 
        : feature.properties.swing;
      
      if (value !== undefined && value !== null) {
        const color = getCountyColor(value, viewMode, PARTY_COLORS);
        colorExpression.push(
          ['==', ['get', 'fips'], feature.properties.fips],
          color
        );
      }
    }
    
    colorExpression.push('#cccccc'); // default color
    
    if (map.getLayer('county-fills')) {
      map.setPaintProperty('county-fills', 'fill-color', colorExpression);
    }
  }, [countyData, viewMode]);

  const onMapClick = (event) => {
    const feature = event.features?.[0];
    if (feature) {
      setSelectedCounty(feature);
    }
  };

  const onMouseMove = (event) => {
    const feature = event.features?.[0];
    if (feature) {
      setHoverInfo({
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
        countyName: feature.properties.county_name || feature.properties.county,
        state: feature.properties.state
      });
    } else {
      setHoverInfo(null);
    }
  };

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
    <div className="relative w-full h-full">
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle="mapbox://styles/mapbox/light-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        interactiveLayerIds={['county-fills']}
        onClick={onMapClick}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoverInfo(null)}
      >
        <Source id="counties" type="geojson" data={countyData}>
          <Layer {...countyFillLayer} />
          <Layer {...countyBorderLayer} />
        </Source>
      </Map>

      {/* Hover tooltip */}
      {hoverInfo && (
        <div
          className="absolute bg-white px-3 py-2 rounded shadow-lg pointer-events-none text-sm"
          style={{
            left: hoverInfo.longitude,
            top: hoverInfo.latitude,
            transform: 'translate(-50%, -120%)'
          }}
        >
          <div className="font-semibold">{hoverInfo.countyName}</div>
          <div className="text-gray-600">{hoverInfo.state}</div>
        </div>
      )}
    </div>
  );
}
