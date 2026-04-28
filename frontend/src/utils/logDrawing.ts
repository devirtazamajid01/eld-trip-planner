/**
 * Canvas drawing utilities for FMCSA-style ELD daily log sheets.
 *
 * The grid has 24 hour columns (midnight to midnight) and 4 status rows:
 *   Row 0: Off Duty
 *   Row 1: Sleeper Berth
 *   Row 2: Driving
 *   Row 3: On Duty (Not Driving)
 */

import type { DailyLog } from "../types/trip";

const CANVAS_W = 900;
const CANVAS_H = 520;
const DPR = 2;

const GRID_LEFT = 130;
const GRID_RIGHT = CANVAS_W - 55;
const GRID_TOP = 100;
const GRID_ROW_H = 50;
const GRID_ROWS = 4;
const GRID_BOTTOM = GRID_TOP + GRID_ROWS * GRID_ROW_H;
const GRID_W = GRID_RIGHT - GRID_LEFT;

const ROW_LABELS = ["1. Off Duty", "2. Sleeper\n    Berth", "3. Driving", "4. On Duty\n    (Not Driving)"];
const STATUS_TO_ROW: Record<string, number> = {
  off_duty: 0,
  sleeper_berth: 1,
  driving: 2,
  on_duty_not_driving: 3,
};

const LINE_COLOR = "#1e3a5f";
const GRID_LINE_COLOR = "#b0b8c4";
const GRID_LINE_LIGHT = "#d4dbe4";
const STATUS_LINE_COLOR = "#1a56db";
const STATUS_LINE_WIDTH = 3;
const BG_COLOR = "#ffffff";
const HEADER_BG = "#1e3a5f";

function timeToX(timeStr: string): number {
  let h: number, m: number;
  if (timeStr === "24:00") {
    h = 24; m = 0;
  } else {
    const [hStr, mStr] = timeStr.split(":");
    h = parseInt(hStr, 10);
    m = parseInt(mStr, 10);
  }
  const fraction = (h + m / 60) / 24;
  return GRID_LEFT + fraction * GRID_W;
}

function rowCenterY(row: number): number {
  return GRID_TOP + row * GRID_ROW_H + GRID_ROW_H / 2;
}

export function drawDailyLog(canvas: HTMLCanvasElement, log: DailyLog): void {
  canvas.width = CANVAS_W * DPR;
  canvas.height = CANVAS_H * DPR;
  canvas.style.width = `${CANVAS_W}px`;
  canvas.style.height = `${CANVAS_H}px`;

  const ctx = canvas.getContext("2d")!;
  ctx.scale(DPR, DPR);

  ctx.fillStyle = BG_COLOR;
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  drawHeader(ctx, log);
  drawGrid(ctx);
  drawStatusLines(ctx, log);
  drawTotals(ctx, log);
  drawRemarks(ctx, log);
}

function drawHeader(ctx: CanvasRenderingContext2D, log: DailyLog) {
  ctx.fillStyle = HEADER_BG;
  ctx.fillRect(0, 0, CANVAS_W, 38);

  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 14px 'Inter', sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("DRIVER'S DAILY LOG", 15, 25);

  ctx.font = "11px 'Inter', sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("(24 Hours)", CANVAS_W - 15, 25);

  ctx.fillStyle = LINE_COLOR;
  ctx.font = "bold 12px 'Inter', sans-serif";
  ctx.textAlign = "left";

  const d = new Date(log.date + "T00:00:00");
  const dateStr = d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });

  ctx.fillText(`Date: ${dateStr}`, 15, 60);
  ctx.fillText(`Total Miles Driving: ${log.total_miles.toFixed(0)}`, 300, 60);

  ctx.strokeStyle = GRID_LINE_COLOR;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, 75);
  ctx.lineTo(CANVAS_W, 75);
  ctx.stroke();

  ctx.fillStyle = LINE_COLOR;
  ctx.font = "bold 9px 'Inter', sans-serif";
  ctx.textAlign = "center";

  const hourLabels = [
    "Mid-\nnight", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
    "Noon", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "Mid-\nnight",
  ];

  for (let i = 0; i <= 24; i++) {
    const x = GRID_LEFT + (i / 24) * GRID_W;
    const label = hourLabels[i];
    if (label.includes("\n")) {
      const parts = label.split("\n");
      ctx.fillText(parts[0], x, GRID_TOP - 16);
      ctx.fillText(parts[1], x, GRID_TOP - 6);
    } else {
      ctx.fillText(label, x, GRID_TOP - 8);
    }
  }
}

function drawGrid(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = LINE_COLOR;
  ctx.font = "bold 10px 'Inter', sans-serif";
  ctx.textAlign = "left";

  for (let r = 0; r < GRID_ROWS; r++) {
    const y = GRID_TOP + r * GRID_ROW_H;
    const label = ROW_LABELS[r];
    if (label.includes("\n")) {
      const parts = label.split("\n");
      ctx.fillText(parts[0], 8, y + GRID_ROW_H / 2 - 5);
      ctx.fillText(parts[1], 8, y + GRID_ROW_H / 2 + 7);
    } else {
      ctx.fillText(label, 8, y + GRID_ROW_H / 2 + 3);
    }
  }

  ctx.strokeStyle = LINE_COLOR;
  ctx.lineWidth = 1;
  for (let r = 0; r <= GRID_ROWS; r++) {
    const y = GRID_TOP + r * GRID_ROW_H;
    ctx.beginPath();
    ctx.moveTo(GRID_LEFT, y);
    ctx.lineTo(GRID_RIGHT, y);
    ctx.stroke();
  }

  ctx.strokeStyle = GRID_LINE_LIGHT;
  ctx.setLineDash([3, 3]);
  for (let r = 0; r < GRID_ROWS; r++) {
    const y = GRID_TOP + r * GRID_ROW_H + GRID_ROW_H / 2;
    ctx.beginPath();
    ctx.moveTo(GRID_LEFT, y);
    ctx.lineTo(GRID_RIGHT, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  for (let i = 0; i <= 24; i++) {
    const x = GRID_LEFT + (i / 24) * GRID_W;
    ctx.strokeStyle = GRID_LINE_COLOR;
    ctx.lineWidth = i === 0 || i === 12 || i === 24 ? 1.5 : 0.75;
    ctx.beginPath();
    ctx.moveTo(x, GRID_TOP);
    ctx.lineTo(x, GRID_BOTTOM);
    ctx.stroke();
  }

  ctx.strokeStyle = GRID_LINE_LIGHT;
  ctx.lineWidth = 0.5;
  for (let i = 0; i < 96; i++) {
    if (i % 4 === 0) continue;
    const x = GRID_LEFT + (i / 96) * GRID_W;
    for (let r = 0; r < GRID_ROWS; r++) {
      const yt = GRID_TOP + r * GRID_ROW_H;
      const tick = i % 2 === 0 ? 6 : 3;
      ctx.beginPath();
      ctx.moveTo(x, yt);
      ctx.lineTo(x, yt + tick);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, yt + GRID_ROW_H - tick);
      ctx.lineTo(x, yt + GRID_ROW_H);
      ctx.stroke();
    }
  }

  ctx.fillStyle = LINE_COLOR;
  ctx.font = "bold 9px 'Inter', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Total", GRID_RIGHT + 27, GRID_TOP - 14);
  ctx.fillText("Hours", GRID_RIGHT + 27, GRID_TOP - 4);
}

function drawStatusLines(ctx: CanvasRenderingContext2D, log: DailyLog) {
  if (!log.entries.length) return;

  ctx.strokeStyle = STATUS_LINE_COLOR;
  ctx.lineWidth = STATUS_LINE_WIDTH;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  ctx.beginPath();

  let prevRow: number | null = null;
  let prevX: number | null = null;

  for (const entry of log.entries) {
    const row = STATUS_TO_ROW[entry.status];
    if (row === undefined) {
      prevRow = null;
      prevX = null;
      continue;
    }

    const x1 = timeToX(entry.start);
    const x2 = timeToX(entry.end);
    const y = rowCenterY(row);

    if (prevRow !== null && prevX !== null && prevRow !== row) {
      const prevY = rowCenterY(prevRow);
      ctx.moveTo(x1, prevY);
      ctx.lineTo(x1, y);
    }

    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y);

    prevRow = row;
    prevX = x2;
  }

  ctx.stroke();
}

function drawTotals(ctx: CanvasRenderingContext2D, log: DailyLog) {
  const totals = [
    log.total_hours.off_duty,
    log.total_hours.sleeper_berth,
    log.total_hours.driving,
    log.total_hours.on_duty_not_driving,
  ];

  ctx.fillStyle = LINE_COLOR;
  ctx.font = "bold 11px 'Inter', sans-serif";
  ctx.textAlign = "center";

  for (let r = 0; r < GRID_ROWS; r++) {
    const y = rowCenterY(r) + 4;
    const val = totals[r] ?? 0;
    ctx.fillText(val.toFixed(1), GRID_RIGHT + 27, y);
  }

  const sumY = GRID_BOTTOM + 4;
  ctx.strokeStyle = LINE_COLOR;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(GRID_RIGHT + 4, sumY);
  ctx.lineTo(GRID_RIGHT + 50, sumY);
  ctx.stroke();

  const total = totals.reduce((a, b) => a + (b ?? 0), 0);
  ctx.font = "bold 12px 'Inter', sans-serif";
  ctx.fillText(`= ${total.toFixed(1)}`, GRID_RIGHT + 27, sumY + 15);
}

function drawRemarks(ctx: CanvasRenderingContext2D, log: DailyLog) {
  const remarksTop = GRID_BOTTOM + 35;

  ctx.fillStyle = HEADER_BG;
  ctx.fillRect(0, remarksTop, CANVAS_W, 22);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 11px 'Inter', sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("REMARKS", 15, remarksTop + 15);

  ctx.fillStyle = LINE_COLOR;
  ctx.font = "11px 'Inter', sans-serif";

  const filtered = log.remarks.filter(
    (r, i, arr) => i === 0 || r.location !== arr[i - 1]?.location
  );

  const maxRemarks = 5;
  const shown = filtered.slice(0, maxRemarks);

  shown.forEach((remark, i) => {
    const y = remarksTop + 38 + i * 18;
    ctx.fillText(`${remark.time}  —  ${remark.location}`, 20, y);
  });

  if (filtered.length > maxRemarks) {
    const y = remarksTop + 38 + maxRemarks * 18;
    ctx.fillStyle = "#64748b";
    ctx.font = "italic 10px 'Inter', sans-serif";
    ctx.fillText(`+ ${filtered.length - maxRemarks} more entries`, 20, y);
  }
}

export { CANVAS_W, CANVAS_H };
