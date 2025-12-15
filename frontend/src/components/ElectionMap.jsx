import React, { useMemo, useRef, useState, useCallback } from 'react';
import Map, { Source, Layer } from 'react-map-gl';
import { useAppContext } from '../store/useAppContext';
import { getCountyColor } from '../utils/colors';
import { PARTY_COLORS } from '../constants';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

export function ElectionMap() {
  const mapRef = useRef(null);

  const {
    countyData,
    selectedYear,
    viewMode,
    setSelectedCounty,
    loading,
    error,
  } = useAppContext();

  const [viewState, setViewState] = useState({
    longitude: -98.5795,
    latitude: 39.8283,
    zoom: 4,
  });

  const [hoverInfo, setHoverInfo] = useState(null);

  /**
   * Build a NEW GeoJSON object with a derived `fillColor` property per feature.
   * This makes styling declarative: Mapbox just reads `fillColor` from each feature.
   */
  const styledCountyData = useMemo(() => {
    if (!countyData) return null;

    // Avoid mutating original features.
    const features = countyData.features.map((feature) => {
      const props = feature.properties || {};

      const value =
        viewMode === 'absolute' ? props.dem_share : props.swing;

      const fillColor =
        props.hasData && value != null
          ? getCountyColor(value, viewMode, PARTY_COLORS)
          : '#cccccc';

      return {
        ...feature,
        properties: {
          ...props,
          fillColor,
        },
      };
    });

    return {
      ...countyData,
      features,
    };
  }, [countyData, viewMode]);

  // Layers: paint reads from feature properties
  const countyFillLayer = useMemo(
    () => ({
      id: 'county-fills',
      type: 'fill',
      paint: {
        // Use the per-feature computed color; fall back to gray
        'fill-color': ['coalesce', ['get', 'fillColor'], '#cccccc'],
        'fill-opacity': 0.7,
      },
    }),
    []
  );

  const countyBorderLayer = useMemo(
    () => ({
      id: 'county-borders',
      type: 'line',
      paint: {
        'line-color': '#ffffff',
        'line-width': 0.5,
      },
    }),
    []
  );

  const onMapClick = useCallback(
    (event) => {
      const feature = event.features?.[0];
      if (feature) {
        setSelectedCounty(feature);
      }
    },
    [setSelectedCounty]
  );

  /**
   * IMPORTANT: use screen pixel coords for tooltip positioning.
   * Your old code used lng/lat as CSS pixels which is wrong.
   */
  const onMouseMove = useCallback((event) => {
    const feature = event.features?.[0];
    if (!feature) {
      setHoverInfo(null);
      return;
    }

    setHoverInfo({
      x: event.point.x,
      y: event.point.y,
      countyName: feature.properties.county_name || feature.properties.county,
      state: feature.properties.state,
    });
  }, []);

  const onMouseLeave = useCallback(() => {
    setHoverInfo(null);
  }, []);

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

  if (!styledCountyData) {
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
        onMove={(evt) => setViewState(evt.viewState)}
        mapStyle="mapbox://styles/mapbox/light-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        interactiveLayerIds={['county-fills']}
        onClick={onMapClick}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        reuseMaps
      >
        <Source
          // Keying by year+mode ensures React/Mapbox don't get “stuck” reusing the wrong source instance
          key={`counties-${selectedYear}-${viewMode}`}
          id="counties"
          type="geojson"
          data={styledCountyData}
        >
          <Layer {...countyFillLayer} />
          <Layer {...countyBorderLayer} />
        </Source>
      </Map>

      {hoverInfo && (
        <div
          className="absolute bg-white px-3 py-2 rounded shadow-lg pointer-events-none text-sm z-10 border border-gray-200"
          style={{
            left: hoverInfo.x,
            top: hoverInfo.y,
            transform: 'translate(-50%, -120%)',
          }}
        >
          <div className="font-semibold">{hoverInfo.countyName}</div>
          <div className="text-gray-600 text-xs">{hoverInfo.state}</div>
        </div>
      )}
    </div>
  );
}
