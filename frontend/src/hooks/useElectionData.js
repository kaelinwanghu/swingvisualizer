import { useEffect } from 'react';
import { useAppContext } from '../store/AppContext';
import { loadElectionData, loadCountyGeometry, mergeElectionWithGeometry } from '../utils/data';

export function useElectionData() {
  const { selectedYear, viewMode, setCountyData, setLoading, setError } = useAppContext();

  useEffect(() => {
    let isMounted = true;

    async function fetchData() {
      if (!isMounted) return;
      setLoading(true);
      setError(null);

      try {
        const [geoData, electionData] = await Promise.all([
          loadCountyGeometry(),
          loadElectionData(selectedYear, viewMode)
        ]);

        if (!isMounted) return;

        if (!electionData) {
          setError('No data available for this year/mode combination');
          setCountyData(null);
          return;
        }

        const mergedData = mergeElectionWithGeometry(geoData, electionData);
        setCountyData(mergedData);
      } catch (err) {
        if (!isMounted) return;
        console.error('Error loading data:', err);
        setError('Failed to load election data');
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
