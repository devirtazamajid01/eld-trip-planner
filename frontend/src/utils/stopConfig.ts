export interface StopTypeConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  icon: string;
}

export const STOP_TYPES: Record<string, StopTypeConfig> = {
  pickup: {
    label: "Pickup",
    color: "#16a34a",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
    textColor: "text-green-600",
    icon: "P",
  },
  dropoff: {
    label: "Drop-off",
    color: "#dc2626",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
    textColor: "text-red-600",
    icon: "D",
  },
  fuel: {
    label: "Fuel Stop",
    color: "#ea580c",
    bgColor: "bg-orange-50",
    borderColor: "border-orange-200",
    textColor: "text-orange-600",
    icon: "F",
  },
  rest_30min: {
    label: "30-Min Break",
    color: "#2563eb",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    textColor: "text-blue-600",
    icon: "R",
  },
  rest_10hr: {
    label: "10-Hr Rest",
    color: "#7c3aed",
    bgColor: "bg-violet-50",
    borderColor: "border-violet-200",
    textColor: "text-violet-600",
    icon: "S",
  },
  restart_34hr: {
    label: "34-Hr Restart",
    color: "#be185d",
    bgColor: "bg-pink-50",
    borderColor: "border-pink-200",
    textColor: "text-pink-600",
    icon: "X",
  },
};

const DEFAULT_CONFIG: StopTypeConfig = {
  label: "Stop",
  color: "#6b7280",
  bgColor: "bg-slate-50",
  borderColor: "border-slate-200",
  textColor: "text-slate-600",
  icon: "?",
};

export const getStopConfig = (type: string): StopTypeConfig => STOP_TYPES[type] ?? DEFAULT_CONFIG;

export const formatStopTime = (iso: string): string =>
  new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
