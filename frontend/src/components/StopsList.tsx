import type { Stop } from "../types/trip";
import { getStopConfig, formatStopTime } from "../utils/stopConfig";

interface Props {
  stops: Stop[];
}

export default function StopsList({ stops }: Props) {
  return (
    <div className="space-y-2">
      {stops.map((stop) => {
        const cfg = getStopConfig(stop.type);
        return (
          <div
            key={`${stop.arrival_time}-${stop.mile_marker}`}
            className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${cfg.textColor} ${cfg.bgColor} ${cfg.borderColor}`}
          >
            <div
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
              style={{ backgroundColor: cfg.color }}
            >
              {cfg.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold">{cfg.label}</p>
              <p className="text-xs truncate opacity-80">{stop.location.name}</p>
              <p className="text-xs opacity-70 mt-0.5">
                {formatStopTime(stop.arrival_time)} &rarr;{" "}
                {formatStopTime(stop.departure_time)} &middot; Mile{" "}
                {stop.mile_marker.toFixed(0)}
              </p>
            </div>
            <span className="text-xs font-medium whitespace-nowrap">
              {stop.duration_hours.toFixed(1)}h
            </span>
          </div>
        );
      })}
    </div>
  );
}
