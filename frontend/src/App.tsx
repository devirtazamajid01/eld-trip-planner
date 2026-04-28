import { useRef } from "react";
import TripForm from "./components/TripForm";
import RouteMap from "./components/RouteMap";
import DailyLogSheet from "./components/DailyLogSheet";
import StopsList from "./components/StopsList";
import TripSummary from "./components/TripSummary";
import { useTripPlan } from "./hooks/useTripPlan";

export default function App() {
  const { data, loading, error, planTrip } = useTripPlan();
  const resultsRef = useRef<HTMLDivElement>(null);

  function handleSubmit(req: Parameters<typeof planTrip>[0]) {
    planTrip(req).then(() => {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 200);
    });
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <header className="bg-[#1e3a5f] text-white shadow-lg">
        <div className="max-w-6xl mx-auto px-4 py-5 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
            <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" />
              <path d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10m10 0H3m10 0h2m4 0h2V9a3 3 0 00-3-3h-2" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">ELD Trip Planner</h1>
            <p className="text-xs text-blue-200">FMCSA-compliant HOS route planning &amp; daily log generation</p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        <section className="bg-white rounded-2xl shadow-md border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Trip Details</h2>
          <TripForm onSubmit={handleSubmit} loading={loading} />
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span className="bg-slate-100 rounded px-2 py-1">Property-carrying CMV</span>
            <span className="bg-slate-100 rounded px-2 py-1">70-hr / 8-day cycle</span>
            <span className="bg-slate-100 rounded px-2 py-1">Fuel every 1,000 mi</span>
            <span className="bg-slate-100 rounded px-2 py-1">1 hr pickup / drop-off</span>
          </div>
        </section>

        {error && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <strong>Error:</strong> {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-3">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />
              <p className="text-sm text-slate-500">Calculating HOS-compliant route...</p>
            </div>
          </div>
        )}

        {data && (
          <div ref={resultsRef} className="space-y-8">
            <TripSummary data={data} />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <div className="rounded-2xl overflow-hidden shadow-md border border-slate-200 h-[500px]">
                  <RouteMap route={data.route} stops={data.stops} />
                </div>
              </div>
              <div>
                <div className="bg-white rounded-2xl shadow-md border border-slate-200 p-4 h-[500px] overflow-y-auto">
                  <h3 className="text-sm font-semibold text-slate-700 mb-3 sticky top-0 bg-white pb-2 border-b border-slate-100">
                    Route Stops ({data.stops.length})
                  </h3>
                  <StopsList stops={data.stops} />
                </div>
              </div>
            </div>

            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-4">Daily ELD Log Sheets</h2>
              <div className="space-y-6">
                {data.daily_logs.map((log, i) => (
                  <DailyLogSheet key={log.date} log={log} index={i} />
                ))}
              </div>
            </section>
          </div>
        )}
      </main>

      <footer className="border-t border-slate-200 mt-16 py-6 text-center text-xs text-slate-400">
        ELD Trip Planner
      </footer>
    </div>
  );
}
