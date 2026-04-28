import { useState } from "react";
import LocationInput from "./LocationInput";
import type { Location, TripPlanRequest } from "../types/trip";

interface Props {
  onSubmit: (req: TripPlanRequest) => void;
  loading: boolean;
}

export default function TripForm({ onSubmit, loading }: Props) {
  const [currentLocation, setCurrentLocation] = useState<Location | null>(null);
  const [pickupLocation, setPickupLocation] = useState<Location | null>(null);
  const [dropoffLocation, setDropoffLocation] = useState<Location | null>(null);
  const [cycleUsed, setCycleUsed] = useState(0);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentLocation || !pickupLocation || !dropoffLocation) return;
    onSubmit({
      current_location: currentLocation,
      pickup_location: pickupLocation,
      dropoff_location: dropoffLocation,
      current_cycle_used: cycleUsed,
    });
  }

  const isValid = currentLocation && pickupLocation && dropoffLocation;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <LocationInput
          label="Current Location"
          value={currentLocation}
          onChange={setCurrentLocation}
          placeholder="e.g. Dallas, TX"
        />
        <LocationInput
          label="Pickup Location"
          value={pickupLocation}
          onChange={setPickupLocation}
          placeholder="e.g. Houston, TX"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <LocationInput
          label="Drop-off Location"
          value={dropoffLocation}
          onChange={setDropoffLocation}
          placeholder="e.g. Los Angeles, CA"
        />
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Current Cycle Used (Hours)
          </label>
          <input
            type="number"
            min={0}
            max={70}
            step={0.5}
            value={cycleUsed}
            onChange={(e) => {
              const v = Number(e.target.value);
              setCycleUsed(Number.isNaN(v) ? 0 : Math.min(70, Math.max(0, v)));
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
          <p className="mt-1 text-xs text-slate-500">
            Hours already used in current 70-hr / 8-day cycle
          </p>
        </div>
      </div>
      <button
        type="submit"
        disabled={!isValid || loading}
        className="w-full cursor-pointer rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Planning Trip...
          </span>
        ) : (
          "Generate Trip Plan"
        )}
      </button>
      {!isValid && (
        <p className="text-xs text-amber-600 mt-2 text-center">
          Please select all three locations to generate a trip plan.
        </p>
      )}
    </form>
  );
}
