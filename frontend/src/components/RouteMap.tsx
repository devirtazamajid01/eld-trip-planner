import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { RouteInfo, Stop } from "../types/trip";
import { getStopConfig, formatStopTime } from "../utils/stopConfig";

import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)
  ._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function createColorIcon(color: string) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,.4);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function FitBounds({ geometry }: { geometry: number[][] }) {
  const map = useMap();

  useEffect(() => {
    if (!geometry.length) return;
    const lats = geometry.map((c) => c[1]);
    const lons = geometry.map((c) => c[0]);
    const bounds = L.latLngBounds(
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)]
    );
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [geometry, map]);

  return null;
}

interface Props {
  route: RouteInfo;
  stops: Stop[];
}

export default function RouteMap({ route, stops }: Props) {
  const positions: [number, number][] = route.geometry.map((c) => [c[1], c[0]]);

  return (
    <MapContainer
      center={[39.5, -98.35]}
      zoom={4}
      className="h-full w-full rounded-xl"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds geometry={route.geometry} />
      <Polyline positions={positions} color="#3b82f6" weight={4} opacity={0.8} />
      {stops.map((stop) => {
        const cfg = getStopConfig(stop.type);
        return (
          <Marker
            key={`${stop.arrival_time}-${stop.mile_marker}`}
            position={[stop.location.lat, stop.location.lon]}
            icon={createColorIcon(cfg.color)}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-semibold" style={{ color: cfg.color }}>
                  {cfg.label}
                </p>
                <p className="text-slate-600">{stop.location.name}</p>
                <p className="text-slate-500 text-xs mt-1">
                  {formatStopTime(stop.arrival_time)} &mdash;{" "}
                  {formatStopTime(stop.departure_time)}
                </p>
                <p className="text-slate-500 text-xs">
                  Mile {stop.mile_marker.toFixed(0)} &middot;{" "}
                  {stop.duration_hours.toFixed(1)}h
                </p>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
