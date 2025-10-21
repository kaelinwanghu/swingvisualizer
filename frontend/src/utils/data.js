import { DATA_PATHS } from '../constants';

export async function loadElectionData(year) {
  const dataUrl = `${DATA_PATHS.ELECTIONS}elections_${year}.json`;
  
  try {
    const response = await fetch(dataUrl);
    if (!response.ok) {
      throw new Error(`Failed to load data for ${year}: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Error loading election data for ${year}:`, error);
    throw error;
  }
}

export async function loadCountyGeometry() {
  const geoUrl = `${DATA_PATHS.GEOJSON}counties.geojson`;
  
  try {
    const response = await fetch(geoUrl);
    if (!response.ok) {
      throw new Error(`Failed to load county geometry: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error('Error loading county geometry:', error);
    throw error;
  }
}

export function mergeElectionWithGeometry(geoData, electionData) {
  return {
    ...geoData,
    features: geoData.features.map(feature => {
      const fips = feature.properties.fips;
      const countyData = electionData[fips];
      
      if (!countyData) {
        return {
          ...feature,
          properties: {
            ...feature.properties,
            hasData: false
          }
        };
      }
      
      return {
        ...feature,
        properties: {
          ...feature.properties,
          ...countyData,
          hasData: true,
          dem_share: Number(countyData.dem_share || 0),
          rep_share: Number(countyData.rep_share || 0),
          swing: Number(countyData.swing || 0),
          swing_magnitude: Number(countyData.swing_magnitude || 0),
          margin: Number(countyData.margin || 0),
          margin_change: Number(countyData.margin_change || 0),
          total_votes: Number(countyData.total_votes || 0),
          DEMOCRAT: Number(countyData.DEMOCRAT || 0),
          REPUBLICAN: Number(countyData.REPUBLICAN || 0),
          flipped: countyData.flipped === 1 || countyData.flipped === true,
          year: Number(countyData.year)
        }
      };
    })
  };
}

export function hasSwingData(year) {
  return year > 2000;
}
