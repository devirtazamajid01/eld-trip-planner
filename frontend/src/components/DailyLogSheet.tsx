import { useRef, useEffect } from "react";
import { drawDailyLog } from "../utils/logDrawing";
import type { DailyLog } from "../types/trip";

interface Props {
  log: DailyLog;
  index: number;
}

/**
 * Displays one calendar day's ELD log as a canvas-drawn FMCSA grid
 * plus a summary stat bar beneath it.
 *
 * `LogStat` is intentionally kept in this file — it is a private
 * layout helper used only here and too small to justify its own file.
 */

interface LogStatProps {
  label: string;
  value: number;
  color: string;
}

const LogStat = ({ label, value, color }: LogStatProps) => (
  <div className={`${color} px-3 py-2 text-center`}>
    <p className="text-xs text-slate-500">{label}</p>
    <p className="text-sm font-semibold text-slate-800">{value.toFixed(1)}h</p>
  </div>
);

const DailyLogSheet = ({ log, index }: Props) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current) {
      drawDailyLog(canvasRef.current, log);
    }
  }, [log]);

  const dateLabel = new Date(log.date + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 bg-slate-50 border-b border-slate-200">
        <h3 className="text-sm font-semibold text-slate-700">
          Day {index + 1} &mdash; {dateLabel}
        </h3>
        <span className="text-xs text-slate-500">{log.total_miles.toFixed(0)} miles</span>
      </div>
      <div className="overflow-x-auto p-4">
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={`Daily ELD log for ${dateLabel}: ${log.total_hours.driving.toFixed(1)}h driving, ${log.total_hours.off_duty.toFixed(1)}h off duty, ${log.total_hours.sleeper_berth.toFixed(1)}h sleeper, ${log.total_hours.on_duty_not_driving.toFixed(1)}h on duty not driving`}
          className="eld-canvas"
        />
      </div>
      <div className="grid grid-cols-4 gap-px bg-slate-200">
        <LogStat label="Off Duty" value={log.total_hours.off_duty} color="bg-slate-100" />
        <LogStat label="Sleeper" value={log.total_hours.sleeper_berth} color="bg-slate-100" />
        <LogStat label="Driving" value={log.total_hours.driving} color="bg-blue-50" />
        <LogStat
          label="On Duty (ND)"
          value={log.total_hours.on_duty_not_driving}
          color="bg-amber-50"
        />
      </div>
    </div>
  );
};

export default DailyLogSheet;
