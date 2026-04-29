/**
 * Canvas drawing utilities for FMCSA-style ELD daily log sheets.
 *
 * Color values are sourced from CSS custom properties defined in
 * `src/index.css` (`--eld-navy`, `--eld-grid-line`, etc.) so the visual
 * theme has a single source of truth. They are read once and cached on
 * first draw — `getComputedStyle` is too expensive to call per-paint.
 *
 * Grid layout:
 *   Row 0: Off Duty
 *   Row 1: Sleeper Berth
 *   Row 2: Driving
 *   Row 3: On Duty (Not Driving)
 */

import type { DailyLog } from "../types/trip";

// ── Layout constants ────────────────────────────────────────────────────────

const CANVAS_W = 900;
const CANVAS_H = 520;
const DEVICE_PIXEL_RATIO = 2; // HiDPI: bitmap at 2×, CSS size at 1×

const GRID = {
  left: 130,
  right: CANVAS_W - 55,
  top: 100,
  rowHeight: 50,
  rows: 4,
} as const;

const GRID_BOTTOM = GRID.top + GRID.rows * GRID.rowHeight;
const GRID_W = GRID.right - GRID.left;

// ── Theme (read from CSS custom properties) ──────────────────────────────────

interface CanvasTheme {
  navy: string;
  gridLine: string;
  gridFaint: string;
  statusLine: string;
  bg: string;
  textOnDark: string;
  textMuted: string;
}

const readCssVar = (name: string, fallback: string): string => {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

let themeCache: CanvasTheme | null = null;

const getTheme = (): CanvasTheme => {
  if (themeCache) return themeCache;
  themeCache = {
    navy: readCssVar("--eld-navy", "#1e3a5f"),
    gridLine: readCssVar("--eld-grid-line", "#b0b8c4"),
    gridFaint: readCssVar("--eld-grid-faint", "#d4dbe4"),
    statusLine: readCssVar("--eld-status-line", "#1a56db"),
    bg: readCssVar("--eld-canvas-bg", "#ffffff"),
    textOnDark: "#ffffff",
    textMuted: readCssVar("--eld-text-muted", "#64748b"),
  };
  return themeCache;
};

// ── Row metadata ─────────────────────────────────────────────────────────────

const ROW_LABELS = [
  "1. Off Duty",
  "2. Sleeper\n    Berth",
  "3. Driving",
  "4. On Duty\n    (Not Driving)",
];

const STATUS_TO_ROW: Record<string, number> = {
  off_duty: 0,
  sleeper_berth: 1,
  driving: 2,
  on_duty_not_driving: 3,
};

// ── Coordinate helpers ───────────────────────────────────────────────────────

const timeToX = (timeStr: string): number => {
  const [h, m] = timeStr === "24:00" ? [24, 0] : timeStr.split(":").map(Number);
  return GRID.left + ((h + m / 60) / 24) * GRID_W;
};

const rowCenterY = (row: number): number => GRID.top + row * GRID.rowHeight + GRID.rowHeight / 2;

// ── Public draw entry point ──────────────────────────────────────────────────

export const drawDailyLog = (canvas: HTMLCanvasElement, log: DailyLog): void => {
  canvas.width = CANVAS_W * DEVICE_PIXEL_RATIO;
  canvas.height = CANVAS_H * DEVICE_PIXEL_RATIO;
  canvas.style.width = `${CANVAS_W}px`;
  canvas.style.height = `${CANVAS_H}px`;

  const ctx = canvas.getContext("2d")!;
  ctx.scale(DEVICE_PIXEL_RATIO, DEVICE_PIXEL_RATIO);

  const theme = getTheme();
  ctx.fillStyle = theme.bg;
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  drawHeader(ctx, log, theme);
  drawGrid(ctx, theme);
  drawStatusLines(ctx, log, theme);
  drawTotals(ctx, log, theme);
  drawRemarks(ctx, log, theme);
};

// ── Header ───────────────────────────────────────────────────────────────────

const drawHeader = (ctx: CanvasRenderingContext2D, log: DailyLog, theme: CanvasTheme): void => {
  ctx.fillStyle = theme.navy;
  ctx.fillRect(0, 0, CANVAS_W, 38);

  ctx.fillStyle = theme.textOnDark;
  ctx.font = "bold 14px 'Inter', sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("DRIVER'S DAILY LOG", 15, 25);

  ctx.font = "11px 'Inter', sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("(24 Hours)", CANVAS_W - 15, 25);

  ctx.fillStyle = theme.navy;
  ctx.font = "bold 12px 'Inter', sans-serif";
  ctx.textAlign = "left";

  const dateStr = new Date(log.date + "T00:00:00").toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  ctx.fillText(`Date: ${dateStr}`, 15, 60);
  ctx.fillText(`Total Miles Driving: ${log.total_miles.toFixed(0)}`, 300, 60);

  ctx.strokeStyle = theme.gridLine;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, 75);
  ctx.lineTo(CANVAS_W, 75);
  ctx.stroke();

  drawHourLabels(ctx, theme);
};

const HOUR_LABELS = [
  "Mid-\nnight",
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "11",
  "Noon",
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "11",
  "Mid-\nnight",
];

const drawHourLabels = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  ctx.fillStyle = theme.navy;
  ctx.font = "bold 9px 'Inter', sans-serif";
  ctx.textAlign = "center";

  for (let i = 0; i <= 24; i++) {
    const x = GRID.left + (i / 24) * GRID_W;
    const label = HOUR_LABELS[i];
    if (label.includes("\n")) {
      const [top, bot] = label.split("\n");
      ctx.fillText(top, x, GRID.top - 16);
      ctx.fillText(bot, x, GRID.top - 6);
    } else {
      ctx.fillText(label, x, GRID.top - 8);
    }
  }
};

// ── Grid ─────────────────────────────────────────────────────────────────────

const drawGrid = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  drawRowLabels(ctx, theme);
  drawHorizontalLines(ctx, theme);
  drawVerticalLines(ctx, theme);
  drawTickMarks(ctx, theme);
  drawTotalColumnHeader(ctx, theme);
};

const drawRowLabels = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  ctx.fillStyle = theme.navy;
  ctx.font = "bold 10px 'Inter', sans-serif";
  ctx.textAlign = "left";

  for (let r = 0; r < GRID.rows; r++) {
    const y = GRID.top + r * GRID.rowHeight;
    const label = ROW_LABELS[r];
    if (label.includes("\n")) {
      const [top, bot] = label.split("\n");
      ctx.fillText(top, 8, y + GRID.rowHeight / 2 - 5);
      ctx.fillText(bot, 8, y + GRID.rowHeight / 2 + 7);
    } else {
      ctx.fillText(label, 8, y + GRID.rowHeight / 2 + 3);
    }
  }
};

const drawHorizontalLines = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  ctx.strokeStyle = theme.navy;
  ctx.lineWidth = 1;
  for (let r = 0; r <= GRID.rows; r++) {
    const y = GRID.top + r * GRID.rowHeight;
    ctx.beginPath();
    ctx.moveTo(GRID.left, y);
    ctx.lineTo(GRID.right, y);
    ctx.stroke();
  }

  ctx.strokeStyle = theme.gridFaint;
  ctx.setLineDash([3, 3]);
  for (let r = 0; r < GRID.rows; r++) {
    const y = GRID.top + r * GRID.rowHeight + GRID.rowHeight / 2;
    ctx.beginPath();
    ctx.moveTo(GRID.left, y);
    ctx.lineTo(GRID.right, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
};

const drawVerticalLines = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  for (let i = 0; i <= 24; i++) {
    const x = GRID.left + (i / 24) * GRID_W;
    const isEmphasis = i === 0 || i === 12 || i === 24;
    ctx.strokeStyle = theme.gridLine;
    ctx.lineWidth = isEmphasis ? 1.5 : 0.75;
    ctx.beginPath();
    ctx.moveTo(x, GRID.top);
    ctx.lineTo(x, GRID_BOTTOM);
    ctx.stroke();
  }
};

const drawTickMarks = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  ctx.strokeStyle = theme.gridFaint;
  ctx.lineWidth = 0.5;

  for (let i = 0; i < 96; i++) {
    if (i % 4 === 0) continue;
    const x = GRID.left + (i / 96) * GRID_W;
    const tickLen = i % 2 === 0 ? 6 : 3;

    for (let r = 0; r < GRID.rows; r++) {
      const top = GRID.top + r * GRID.rowHeight;
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, top + tickLen);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, top + GRID.rowHeight - tickLen);
      ctx.lineTo(x, top + GRID.rowHeight);
      ctx.stroke();
    }
  }
};

const drawTotalColumnHeader = (ctx: CanvasRenderingContext2D, theme: CanvasTheme): void => {
  ctx.fillStyle = theme.navy;
  ctx.font = "bold 9px 'Inter', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Total", GRID.right + 27, GRID.top - 14);
  ctx.fillText("Hours", GRID.right + 27, GRID.top - 4);
};

// ── Status lines ─────────────────────────────────────────────────────────────

const drawStatusLines = (
  ctx: CanvasRenderingContext2D,
  log: DailyLog,
  theme: CanvasTheme
): void => {
  if (!log.entries.length) return;

  ctx.strokeStyle = theme.statusLine;
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  ctx.beginPath();

  let prevRow: number | null = null;

  for (const entry of log.entries) {
    const row = STATUS_TO_ROW[entry.status];
    if (row === undefined) {
      prevRow = null;
      continue;
    }

    const x1 = timeToX(entry.start);
    const x2 = timeToX(entry.end);
    const y = rowCenterY(row);

    if (prevRow !== null && prevRow !== row) {
      ctx.moveTo(x1, rowCenterY(prevRow));
      ctx.lineTo(x1, y);
    }

    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y);
    prevRow = row;
  }

  ctx.stroke();
};

// ── Totals column ─────────────────────────────────────────────────────────────

const drawTotals = (ctx: CanvasRenderingContext2D, log: DailyLog, theme: CanvasTheme): void => {
  const totals = [
    log.total_hours.off_duty,
    log.total_hours.sleeper_berth,
    log.total_hours.driving,
    log.total_hours.on_duty_not_driving,
  ];

  ctx.fillStyle = theme.navy;
  ctx.font = "bold 11px 'Inter', sans-serif";
  ctx.textAlign = "center";

  totals.forEach((val, r) => {
    ctx.fillText((val ?? 0).toFixed(1), GRID.right + 27, rowCenterY(r) + 4);
  });

  const sumY = GRID_BOTTOM + 4;
  ctx.strokeStyle = theme.navy;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(GRID.right + 4, sumY);
  ctx.lineTo(GRID.right + 50, sumY);
  ctx.stroke();

  const total = totals.reduce((acc, v) => acc + (v ?? 0), 0);
  ctx.font = "bold 12px 'Inter', sans-serif";
  ctx.fillText(`= ${total.toFixed(1)}`, GRID.right + 27, sumY + 15);
};

// ── Remarks section ───────────────────────────────────────────────────────────

const MAX_REMARKS = 5;

const drawRemarks = (ctx: CanvasRenderingContext2D, log: DailyLog, theme: CanvasTheme): void => {
  const top = GRID_BOTTOM + 35;

  ctx.fillStyle = theme.navy;
  ctx.fillRect(0, top, CANVAS_W, 22);
  ctx.fillStyle = theme.textOnDark;
  ctx.font = "bold 11px 'Inter', sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("REMARKS", 15, top + 15);

  ctx.fillStyle = theme.navy;
  ctx.font = "11px 'Inter', sans-serif";

  const unique = log.remarks.filter((r, i, arr) => i === 0 || r.location !== arr[i - 1]?.location);
  const shown = unique.slice(0, MAX_REMARKS);

  shown.forEach((remark, i) => {
    ctx.fillText(`${remark.time}  —  ${remark.location}`, 20, top + 38 + i * 18);
  });

  if (unique.length > MAX_REMARKS) {
    ctx.fillStyle = theme.textMuted;
    ctx.font = "italic 10px 'Inter', sans-serif";
    ctx.fillText(`+ ${unique.length - MAX_REMARKS} more entries`, 20, top + 38 + MAX_REMARKS * 18);
  }
};

export { CANVAS_W, CANVAS_H };
