"use client";

import type { TabKey, Unit } from "@/lib/api";
import { VERDICT_META, VERDICT_THRESHOLD, quadrantRadius, riskColor } from "@/lib/verdict";
import { QH, QW, sx, sy } from "./IndiaMap";

interface QuadrantViewProps {
  units: Unit[];
  tab: TabKey;
  selectedKey: string | null;
  onSelect: (unit: Unit) => void;
}

export default function QuadrantView({ units, tab, selectedKey, onSelect }: QuadrantViewProps) {
  const qMidX = sx(VERDICT_THRESHOLD);
  const qMidY = sy(VERDICT_THRESHOLD);
  const qHalfW = QW - qMidX;
  const qHalfH = QH - qMidY;
  const qLabRX = QW - 14;
  const qBotY = QH - 14;
  const qAxisY = QH - 2;

  const topNames = new Set(
    [...units].sort((a, b) => b.priority - a.priority).slice(0, 5).map((u) => u.unit_key),
  );

  const labels = units
    .filter((u) => u.watched || topNames.has(u.unit_key))
    .slice(0, 8)
    .map((u) => ({
      name: u.name.length > 16 ? `${u.name.slice(0, 15)}…` : u.name,
      x: sx(u.conf) + 9,
      y: sy(u.risk) + 3,
    }));

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: tab === "quad" ? "block" : "none",
        padding: "18px 22px",
      }}
    >
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        <div
          className="mdp-mono"
          style={{
            position: "absolute",
            left: -2,
            top: 8,
            fontSize: 10,
            color: "var(--faint)",
          }}
        >
          CARE-GAP RISK ↑
        </div>
        <svg
          viewBox={`0 0 ${QW} ${QH}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ width: "100%", height: "100%", overflow: "visible" }}
        >
          <rect x={qMidX} y={0} width={qHalfW} height={qMidY} fill="var(--q-desert)" />
          <rect x={0} y={0} width={qMidX} height={qMidY} fill="var(--q-blind)" />
          <rect x={qMidX} y={qMidY} width={qHalfW} height={qHalfH} fill="var(--q-served)" />
          <rect x={0} y={qMidY} width={qMidX} height={qHalfH} fill="var(--q-unknown)" />
          <line
            x1={qMidX}
            y1={0}
            x2={qMidX}
            y2={QH}
            stroke="var(--q-grid)"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <line
            x1={0}
            y1={qMidY}
            x2={QW}
            y2={qMidY}
            stroke="var(--q-grid)"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <text
            x={qLabRX}
            y={22}
            textAnchor="end"
            fontFamily="IBM Plex Mono, monospace"
            fontSize={11}
            fontWeight={600}
            fill="#c0654f"
          >
            CONFIRMED DESERTS
          </text>
          <text
            x={14}
            y={22}
            fontFamily="IBM Plex Mono, monospace"
            fontSize={11}
            fontWeight={600}
            fill="#c79a4a"
          >
            BLIND SPOTS · investigate
          </text>
          <text
            x={qLabRX}
            y={qBotY}
            textAnchor="end"
            fontFamily="IBM Plex Mono, monospace"
            fontSize={11}
            fontWeight={600}
            fill="#5aa67e"
          >
            ADEQUATELY SERVED
          </text>
          <text
            x={14}
            y={qBotY}
            fontFamily="IBM Plex Mono, monospace"
            fontSize={11}
            fontWeight={600}
            fill="#a9b0bd"
          >
            UNVERIFIED · low data
          </text>
          {units.map((u) => {
            const vm = VERDICT_META[u.verdict];
            const selected = selectedKey === u.unit_key;
            return (
              <circle
                key={u.unit_key}
                cx={sx(u.conf)}
                cy={sy(u.risk)}
                r={quadrantRadius(u.n_facilities)}
                fill={vm.color}
                fillOpacity={0.82}
                stroke={selected ? "var(--ink)" : "var(--panel)"}
                strokeWidth={selected ? 2.4 : 1.2}
                style={{ cursor: "pointer" }}
                onClick={() => onSelect(u)}
              />
            );
          })}
          {labels.map((t) => (
            <text
              key={t.name + t.x}
              x={t.x}
              y={t.y}
              fontFamily="Hanken Grotesk, sans-serif"
              fontSize={11}
              fontWeight={600}
              fill="var(--ink)"
            >
              {t.name}
            </text>
          ))}
          <text
            x={QW}
            y={qAxisY}
            textAnchor="end"
            fontFamily="IBM Plex Mono, monospace"
            fontSize={10}
            fill="#9aa0ad"
          >
            DATA CONFIDENCE →
          </text>
        </svg>
      </div>
    </div>
  );
}
