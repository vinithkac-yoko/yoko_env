/** The canvas's view: which rectangle of the pattern (in mm) fills the drawing area. */
export interface View {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Bounds {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
}

/** A view showing all of `b` with a margin, with the shape of the drawing area (`aspect` = w / h). */
export function fit(b: Bounds, aspect: number, margin = 0.05): View {
  const bw = Math.max(b.max_x - b.min_x, 1);
  const bh = Math.max(b.max_y - b.min_y, 1);
  let w = bw * (1 + 2 * margin);
  let h = bh * (1 + 2 * margin);
  if (w / h < aspect) w = h * aspect;
  else h = w / aspect;
  const cx = (b.min_x + b.max_x) / 2;
  const cy = (b.min_y + b.max_y) / 2;
  return { x: cx - w / 2, y: cy - h / 2, w, h };
}

/** Zoom by `factor` (> 1 zooms in) keeping the pattern point (px, py) where it is on screen. */
export function zoomAt(v: View, factor: number, px: number, py: number): View {
  const w = clamp(v.w / factor, 5, 100000);
  const k = w / v.w;
  const h = v.h * k;
  return { x: px - (px - v.x) * k, y: py - (py - v.y) * k, w, h };
}

/** Move the view by a drag of (dx, dy) screen pixels on a drawing area `width` pixels wide. */
export function pan(v: View, dx: number, dy: number, width: number): View {
  const mmPerPx = v.w / Math.max(width, 1);
  return { ...v, x: v.x - dx * mmPerPx, y: v.y - dy * mmPerPx };
}

/** Screen pixels to pattern millimetres on a drawing area `width` pixels wide. */
export function toPattern(v: View, sx: number, sy: number, width: number): [number, number] {
  const mmPerPx = v.w / Math.max(width, 1);
  return [v.x + sx * mmPerPx, v.y + sy * mmPerPx];
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}
