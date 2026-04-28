import type { TripPlanResponse } from "../types/trip";

interface Props {
  data: TripPlanResponse;
}

export default function TripSummary({ data }: Props) {
  const { route, stops, daily_logs } = data;

  const totalDriving = daily_logs.reduce((s, l) => s + l.total_hours.driving, 0);
  const totalOnDuty = daily_logs.reduce((s, l) => s + l.total_hours.on_duty_not_driving, 0);
  const fuelStops = stops.filter((s) => s.type === "fuel").length;
  const restStops = stops.filter((s) => s.type === "rest_10hr" || s.type === "restart_34hr").length;

  const cards = [
    { label: "Total Distance", value: `${route.total_distance_miles.toFixed(0)} mi`, sub: `${route.total_duration_hours.toFixed(1)}h drive time` },
    { label: "Trip Duration", value: `${daily_logs.length} day${daily_logs.length > 1 ? "s" : ""}`, sub: `${totalDriving.toFixed(1)}h driving / ${totalOnDuty.toFixed(1)}h on-duty` },
    { label: "Stops", value: `${stops.length} total`, sub: `${fuelStops} fuel · ${restStops} overnight` },
    { label: "Log Sheets", value: `${daily_logs.length}`, sub: "Daily ELD logs generated" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{c.label}</p>
          <p className="mt-1 text-xl font-bold text-slate-800">{c.value}</p>
          <p className="text-xs text-slate-500 mt-0.5">{c.sub}</p>
        </div>
      ))}
    </div>
  );
}
