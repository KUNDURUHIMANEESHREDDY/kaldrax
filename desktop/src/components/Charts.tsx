import { useEffect, useId, useRef, useState } from "react";

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(680);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return { ref, width };
}

function niceMax(value: number): number {
  if (value <= 4) return 4;
  const pow = Math.pow(10, Math.floor(Math.log10(value)));
  const n = value / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * pow;
}

function smoothPath(points: Array<{ x: number; y: number }>): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const t = 0.2;
    const c1x = p1.x + (p2.x - p0.x) * t;
    const c1y = p1.y + (p2.y - p0.y) * t;
    const c2x = p2.x - (p3.x - p1.x) * t;
    const c2y = p2.y - (p3.y - p1.y) * t;
    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

/* ------------------------------------------------------------------ */
/* Line chart                                                          */
/* ------------------------------------------------------------------ */

export type Series = { name: string; color: string; area?: boolean; dashed?: boolean };

export function LineChart({
  data,
  series,
  height = 220,
  formatValue = (n) => `${n}`,
  compact,
}: {
  data: Array<{ label: string; values: number[] }>;
  series: Series[];
  height?: number;
  formatValue?: (n: number) => string;
  compact?: boolean;
}) {
  const { ref, width } = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const gid = useId().replace(/[^a-zA-Z0-9]/g, "");

  const pad = { top: 12, right: 8, bottom: 24, left: compact ? 26 : 34 };
  const innerW = Math.max(20, width - pad.left - pad.right);
  const innerH = Math.max(20, height - pad.top - pad.bottom);

  const maxRaw = Math.max(1, ...data.flatMap((d) => d.values));
  const max = niceMax(maxRaw);
  const ticks = 4;

  const xFor = (i: number) => {
    if (data.length <= 1) return pad.left + innerW / 2;
    return pad.left + (innerW * i) / (data.length - 1);
  };
  const yFor = (v: number) => pad.top + innerH - (Math.max(0, v) / max) * innerH;

  const labelEvery = Math.max(1, Math.ceil(data.length / (compact ? 4 : 7)));

  return (
    <div className="chart" ref={ref}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${Math.max(width, 40)} ${height}`}
        role="img"
        aria-label="Stock movement over time"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const step = data.length <= 1 ? innerW : innerW / (data.length - 1);
          const idx = Math.round((x - pad.left) / step);
          setHover(Math.max(0, Math.min(data.length - 1, idx)));
        }}
      >
        <defs>
          {series.map((s, si) => (
            <linearGradient key={s.name} id={`${gid}-${si}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.13" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const y = pad.top + (innerH * i) / ticks;
          const value = max - (max * i) / ticks;
          return (
            <g key={i}>
              <line className="chart__grid" x1={pad.left} x2={width - pad.right} y1={y} y2={y} />
              <text className="chart__axis" x={pad.left - 8} y={y + 3} textAnchor="end">
                {formatValue(Math.round(value))}
              </text>
            </g>
          );
        })}

        {series.map((s, si) => {
          const pts = data.map((d, i) => ({ x: xFor(i), y: yFor(d.values[si] ?? 0) }));
          const path = smoothPath(pts);
          return (
            <g key={s.name}>
              {s.area ? (
                <path
                  d={`${path} L ${xFor(data.length - 1)} ${pad.top + innerH} L ${xFor(0)} ${pad.top + innerH} Z`}
                  fill={`url(#${gid}-${si})`}
                  stroke="none"
                />
              ) : null}
              <path
                d={path}
                fill="none"
                stroke={s.color}
                strokeWidth={s.dashed ? 1.4 : 1.8}
                strokeDasharray={s.dashed ? "4 4" : undefined}
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </g>
          );
        })}

        {data.map((d, i) =>
          i % labelEvery === 0 || i === data.length - 1 ? (
            <text
              key={d.label + i}
              className="chart__axis"
              x={xFor(i)}
              y={height - 6}
              textAnchor={i === 0 ? "start" : i === data.length - 1 ? "end" : "middle"}
            >
              {d.label}
            </text>
          ) : null
        )}

        {hover !== null ? (
          <g>
            <line
              x1={xFor(hover)}
              x2={xFor(hover)}
              y1={pad.top}
              y2={pad.top + innerH}
              stroke="#d9d9d5"
              strokeDasharray="3 3"
            />
            {series.map((s, si) => (
              <circle
                key={s.name}
                cx={xFor(hover)}
                cy={yFor(data[hover].values[si] ?? 0)}
                r="3.4"
                fill="#fff"
                stroke={s.color}
                strokeWidth="1.8"
              />
            ))}
          </g>
        ) : null}
      </svg>

      {hover !== null ? (
        <div
          className="chart__tip"
          style={{
            left: Math.min(Math.max(xFor(hover), 78), Math.max(80, width - 78)),
            top: Math.max(48, pad.top + 4),
          }}
        >
          <div className="chart__tip-title">{data[hover].label}</div>
          {series.map((s, si) => (
            <div className="chart__tip-row" key={s.name}>
              <span>
                <i style={{ background: s.color }} />
                {s.name}
              </span>
              <b>
                {formatValue(data[hover].values[si] ?? 0)}
              </b>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Donut chart                                                         */
/* ------------------------------------------------------------------ */

export type DonutDatum = { label: string; value: number; color: string };

export function DonutChart({
  data,
  size = 168,
  thickness = 16,
  centerLabel = "Total",
  centerValue,
}: {
  data: DonutDatum[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const gap = data.length > 1 ? 2.5 : 0;

  let offset = 0;
  const segments = data.map((d) => {
    const frac = total > 0 ? d.value / total : 0;
    const len = Math.max(0, frac * c - gap);
    const seg = { ...d, len, offset };
    offset += frac * c;
    return seg;
  });

  return (
    <div className="donut__figure" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${centerLabel} split by category`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#f2f2f0"
          strokeWidth={thickness}
        />
        {segments.map((s, i) => (
          <circle
            key={s.label}
            className="donut__seg"
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={active === i ? thickness + 3 : thickness}
            strokeDasharray={`${s.len} ${Math.max(0, c - s.len)}`}
            strokeDashoffset={-s.offset}
            strokeLinecap="butt"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            <title>
              {s.label}: {s.value}
            </title>
          </circle>
        ))}
      </svg>
      <div className="donut__center">
        <b>{active !== null ? data[active].value : centerValue ?? total}</b>
        <span>{active !== null ? data[active].label : centerLabel}</span>
      </div>
    </div>
  );
}

export function DonutLegend({ data, suffix }: { data: DonutDatum[]; suffix?: string }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="donut__legend">
      {data.map((d) => (
        <div className="donut__legend-row" key={d.label}>
          <span className="chart-legend__swatch" style={{ background: d.color }} />
          <span className="name">{d.label}</span>
          <b>
            {d.value}
            {suffix ? <span className="muted" style={{ fontWeight: 400 }}>{suffix}</span> : null}
          </b>
          <span className="pct">{total > 0 ? Math.round((d.value / total) * 100) : 0}%</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Horizontal bars                                                     */
/* ------------------------------------------------------------------ */

export function HBars({
  data,
  formatValue = (n) => `${n}`,
}: {
  data: Array<{ label: string; value: number; meta?: string; color?: string }>;
  formatValue?: (n: number) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="hbars">
      {data.map((d) => (
        <div className="hbar" key={d.label}>
          <span className="hbar__name" title={d.label}>
            {d.label}
          </span>
          <span className="hbar__value">{formatValue(d.value)}</span>
          <span className="hbar__track">
            <span
              className="hbar__fill"
              style={{ width: `${Math.max(3, (d.value / max) * 100)}%`, background: d.color ?? "#232323" }}
            />
          </span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stacked vertical bars                                               */
/* ------------------------------------------------------------------ */

export function StackedBars({
  data,
  series,
  height = 150,
}: {
  data: Array<{ label: string; segments: number[]; total: number }>;
  series: Array<{ name: string; color: string }>;
  height?: number;
}) {
  const max = Math.max(1, ...data.map((d) => d.total));
  return (
    <div className="stack-bars" style={{ height }}>
      {data.map((d) => (
        <div className="stack-bar" key={d.label} title={`${d.label}: ${d.total}`}>
          <div className="stack-bar__col" style={{ height: `${Math.max(3, (d.total / max) * 100)}%` }}>
            {d.segments.map((v, i) =>
              v > 0 ? (
                <i
                  key={i}
                  style={{
                    height: `${(v / Math.max(1, d.total)) * 100}%`,
                    background: series[i]?.color ?? "#ccc",
                  }}
                />
              ) : null
            )}
          </div>
          <div>
            <div className="stack-bar__value">{d.total}</div>
            <div className="stack-bar__label">{d.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sparkline                                                           */
/* ------------------------------------------------------------------ */

export function Sparkline({ values, color = "#5f6f52", height = 34 }: { values: number[]; color?: string; height?: number }) {
  const max = Math.max(1, ...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => ({
    x: (i / Math.max(1, values.length - 1)) * 100,
    y: height - 3 - ((v - min) / range) * (height - 6),
  }));
  return (
    <svg className="spark" viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <path
        d={smoothPath(pts.map((p) => ({ x: p.x, y: p.y })))}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
