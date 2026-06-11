import { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import { addDataToMap } from '@kepler.gl/actions';
import { processGeojson } from '@kepler.gl/processors';
import { AUSTIN_VIEWPORT } from '../constants/austinBounds';

const SIDEBAR_WIDTH_PX = 320;
const MAP_ID = 'austin_traffic_map';

export default function MapContainer({ liveTraffic, incidents, mapboxToken }) {
  const dispatch = useDispatch();

  useEffect(() => {
    if (!liveTraffic) return;

    const datasets = [
      {
        info: { id: 'live_traffic', label: 'Live Traffic' },
        data: processGeojson(liveTraffic),
      },
    ];

    if (incidents?.features?.length > 0) {
      datasets.push({
        info: { id: 'incidents', label: 'Incidents' },
        data: processGeojson(incidents),
      });
    }

    dispatch(
      addDataToMap({
        datasets,
        options: { centerMap: false, readOnly: false },
        config: {
          mapState: AUSTIN_VIEWPORT,
        },
      })
    );
  }, [liveTraffic, incidents, dispatch]);

  return (
    <div className="relative flex-1 h-full">
      <KeplerGl
        id={MAP_ID}
        mapboxApiAccessToken={mapboxToken}
        width={window.innerWidth - SIDEBAR_WIDTH_PX}
        height={window.innerHeight}
      />
    </div>
  );
}
