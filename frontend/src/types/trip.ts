export interface Location {
  lat: number;
  lon: number;
  name: string;
}

export interface TripPlanRequest {
  current_location: Location;
  pickup_location: Location;
  dropoff_location: Location;
  current_cycle_used: number;
}

export interface Stop {
  type: string;
  location: Location;
  arrival_time: string;
  departure_time: string;
  duration_hours: number;
  mile_marker: number;
}

export interface LogEntry {
  status: string;
  start: string;
  end: string;
  duration_hours: number;
  location: string;
}

export interface Remark {
  time: string;
  location: string;
  status: string;
}

export interface DailyLog {
  date: string;
  total_miles: number;
  entries: LogEntry[];
  remarks: Remark[];
  total_hours: {
    off_duty: number;
    sleeper_berth: number;
    driving: number;
    on_duty_not_driving: number;
  };
}

export interface RouteInfo {
  total_distance_miles: number;
  total_duration_hours: number;
  geometry: number[][];
}

export interface TripPlanResponse {
  route: RouteInfo;
  stops: Stop[];
  daily_logs: DailyLog[];
}

export interface NominatimResult {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
}
