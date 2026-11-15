import { useEffect, useRef, useState } from "react";
import type { Scene } from "../api";
import { type Bounds, fit, pan, toPattern, type View, zoomAt } from "../view";

interface Props {
  scene: Scene;
  selected: number | null;
  onSelect: (id: number | null) => void;
  showLabels: boolean;
  showLandmarks: boolean;
  /** What to fit the view to; a new `fitKey` fits again. */
  fitTo: Bounds;
  fitKey: number;
}

/** The pattern as SVG: every line and curve drawn the same way, every point, its label. Wheel to
 * zoom about the cursor, drag to pan, click an object to select it. */
export default function Canvas({
  scene,
  selected,
  onSelect,
  showLabels,
  showLandmarks,
  fitTo,
  fitKey,
}: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [measured, setMeasured] = useState(false);
  const [view, setView] = useState<View | null>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      setSize({ w: el.clientWidth || 800, h: el.clientHeight || 600 });
      setMeasured(true);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // fit once the drawing area is measured, and whenever asked (fitKey); switching to another size
  // of the pattern keeps the view, so the two sizes can be compared in place
  useEffect(() => {
    if (measured) setView(fit(fitTo, size.w / size.h));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, measured]);

  if (!view) return <div ref={box} className="h-full w-full" />;
  const mmPerPx = view.w / Math.max(size.w, 1);
  const r = 2.5 * mmPerPx;
  const font = 11 * mmPerPx;
  const hit = 8;

  const onWheel = (e: React.WheelEvent) => {
    const rect = box.current!.getBoundingClientRect();
    const [px, py] = toPattern(view, e.clientX - rect.left, e.clientY - rect.top, size.w);
    setView(zoomAt(view, e.deltaY < 0 ? 1.2 : 1 / 1.2, px, py));
  };
  const onDown = (e: React.MouseEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, moved: false };
  };
  const onMove = (e: React.MouseEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true;
    if (d.moved) {
      setView((v) => (v ? pan(v, dx, dy, size.w) : v));
      drag.current = { x: e.clientX, y: e.clientY, moved: true };
    }
  };
  const onUp = (e: React.MouseEvent) => {
    const d = drag.current;
    drag.current = null;
    if (d && !d.moved && e.target === e.currentTarget) onSelect(null);
  };
  const pick = (id: number) => (e: React.MouseEvent) => {
    if (drag.current?.moved) return;
    e.stopPropagation();
    drag.current = null;
    onSelect(id);
  };
  const stroke = (id: number) => (id === selected ? "#dc2626" : "#1f2933");

  return (
    <div ref={box} className="h-full w-full select-none overflow-hidden bg-white" data-testid="canvas">
      <svg
        width={size.w}
        height={size.h}
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        onWheel={onWheel}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={() => (drag.current = null)}
        className="cursor-grab active:cursor-grabbing"
      >
        <rect x={view.x} y={view.y} width={view.w} height={view.h} fill="white" />
        {scene.lines.map((l, i) => (
          <g key={`l${i}`} onMouseUp={pick(l.id)}>
            <line x1={l.a[0]} y1={l.a[1]} x2={l.b[0]} y2={l.b[1]} stroke={stroke(l.id)}
              strokeWidth={1} vectorEffect="non-scaling-stroke" />
            <line x1={l.a[0]} y1={l.a[1]} x2={l.b[0]} y2={l.b[1]} stroke="transparent"
              strokeWidth={hit} vectorEffect="non-scaling-stroke" className="cursor-pointer" />
          </g>
        ))}
        {scene.curves.map((c) => {
          const d = c.points.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
          return (
            <g key={`c${c.id}`} onMouseUp={pick(c.id)} data-curve={c.name}>
              <path d={d} fill="none" stroke={stroke(c.id)} strokeWidth={1.2}
                vectorEffect="non-scaling-stroke" />
              <path d={d} fill="none" stroke="transparent" strokeWidth={hit}
                vectorEffect="non-scaling-stroke" className="cursor-pointer" />
            </g>
          );
        })}
        {scene.points.map((p) => {
          const names = showLandmarks ? scene.proposed_landmarks[String(p.id)] : undefined;
          const on = p.id === selected;
          return (
            <g key={`p${p.id}`} onMouseUp={pick(p.id)} className="cursor-pointer" data-point={p.label}>
              <circle cx={p.x} cy={p.y} r={r * 3} fill="transparent" />
              <circle cx={p.x} cy={p.y} r={on ? r * 1.6 : r} fill={on ? "#dc2626" : "#1f2933"} />
              {showLabels && p.label && (
                <text x={p.x + r * 1.5} y={p.y - r * 1.5} fontSize={font}
                  fill={on ? "#dc2626" : "#334155"}>{p.label}</text>
              )}
              {names && (
                <text x={p.x + r * 1.5} y={p.y + font * 1.1} fontSize={font * 0.85}
                  fill="#7c3aed" fontStyle="italic">{names.join(" / ")} (proposed)</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
