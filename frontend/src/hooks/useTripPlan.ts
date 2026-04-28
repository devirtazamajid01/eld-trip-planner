import { useState } from "react";
import axios from "axios";
import type { TripPlanRequest, TripPlanResponse } from "../types/trip";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useTripPlan() {
  const [data, setData] = useState<TripPlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function planTrip(request: TripPlanRequest) {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const resp = await axios.post<TripPlanResponse>(
        `${API_URL}/api/trip-plan`,
        request
      );
      setData(resp.data);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const body = err.response?.data as Record<string, unknown> | undefined;
        const msg = body?.error ?? body?.detail ?? err.message;
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      } else {
        setError("An unexpected error occurred");
      }
    } finally {
      setLoading(false);
    }
  }

  return { data, loading, error, planTrip };
}
