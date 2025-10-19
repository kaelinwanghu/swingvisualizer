export async function loadElectionData(year, viewMode) {
  let dataUrl;
  if (viewMode === 'absolute') {
    dataUrl = `/data/elections_${year}.csv`;
  } else {
    // Find previous year for swing calculation
    const years = [2000, 2004, 2008, 2012, 2016, 2020, 2024];
    const currentIndex = years.indexOf(year);
    if (currentIndex <= 0) return null;
    const prevYear = years[currentIndex - 1];
    dataUrl = `/data/swings_${prevYear}_to_${year}.csv`;
  }

  const response = await fetch(dataUrl);
  const csvText = await response.text();
  
  // Simple CSV parsing
  const lines = csvText.split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  const data = {};
  
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const values = lines[i].split(',');
    const row = {};
    headers.forEach((header, idx) => {
      row[header] = values[idx]?.trim();
    });
    data[row.fips] = row;
  }
  
  return data;
}

export async function loadCountyGeometry() {
  const response = await fetch('/data/counties.geojson');
  return response.json();
}

export function mergeElectionWithGeometry(geoData, electionData) {
  return {
    ...geoData,
    features: geoData.features.map(feature => {
      const fips = feature.properties.fips;
      const data = electionData[fips] || {};
      return {
        ...feature,
        properties: {
          ...feature.properties,
          ...data,
          dem_share: parseFloat(data.dem_share || data.dem_share_y2 || 0),
          rep_share: parseFloat(data.rep_share || data.rep_share_y2 || 0),
          swing: parseFloat(data.swing || 0),
          total_votes: parseInt(data.total_votes || data.total_votes_y2 || 0),
          DEMOCRAT: parseInt(data.DEMOCRAT || data.dem_votes_y2 || 0),
          REPUBLICAN: parseInt(data.REPUBLICAN || data.rep_votes_y2 || 0),
          flipped: data.flipped === 'True' || data.flipped === true
        }
      };
    })
  };
}