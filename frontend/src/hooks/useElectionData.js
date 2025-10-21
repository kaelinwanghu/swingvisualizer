import { useEffect } from 'react';
import { useAppContext } from '../store/AppContext';
import { loadElectionData, loadCountyGeometry, mergeElectionWithGeometry, hasSwingData } from '../utils/data';

export function useElectionData() {
  const { selectedYear, viewMode, setCountyData, setLoading, setError } = useAppContext();

  useEffect(() => {
    let isMounted = true;

    async function fetchData() {
      if (!isMounted) return;
      
      setLoading(true);
      setError(null);

      try {
        if (viewMode === 'swing' && !hasSwingData(selectedYear)) {
          setError(`Swing data not available for ${selectedYear} (first election year)`);
          setCountyData(null);
          setLoading(false);
          return;
        }

        const [geoData, electionData] = await Promise.all([
          loadCountyGeometry(),
          loadElectionData(selectedYear)
        ]);

        if (!isMounted) return;

        if (!electionData) {
          setError(`No election data found for ${selectedYear}`);
          setCountyData(null);
          return;
        }

        const mergedData = mergeElectionWithGeometry(geoData, electionData);
        
        console.log(`Loaded data for ${selectedYear}:`, {
          counties: mergedData.features.length,
          withData: mergedData.features.filter(f => f.properties.hasData).length,
          sampleCounty: mergedData.features[0]?.properties
        });

        setCountyData(mergedData);
      } catch (err) {
        if (!isMounted) return;
        console.error('Error loading election data:', err);
        setError(`Failed to load data: ${err.message}`);
        setCountyData(null);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [selectedYear, viewMode, setCountyData, setLoading, setError]);
}
