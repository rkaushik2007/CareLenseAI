"use client";

import type { Grain, SortKey, Unit } from "@/lib/api";
import { sortBtnStyle } from "@/lib/theme";
import { VERDICT_META, grainLabel, hatchCss, riskColor } from "@/lib/verdict";

interface RankedListProps {
  units: Unit[];
  sort: SortKey;
  grain: Grain;
  selectedKey: string | null;
  focusedState: string | null;
  onSortChange: (sort: SortKey) => void;
  onSelect: (unit: Unit) => void;
  onClearFocus: () => void;
}

const SORTS: Array<{ id: SortKey; label: string }> = [
  { id: "priority", label: "Priority" },
  { id: "risk", label: "Risk" },
  { id: "conf", label: "Low conf" },
  { id: "az", label: "A–Z" },
];

export default function RankedList({
  units,
  sort,
  grain,
  selectedKey,
  focusedState,
  onSortChange,
  onSelect,
  onClearFocus,
}: RankedListProps) {
  const title =
    focusedState && grain !== "state" ? focusedState : `Ranked ${grainLabel(grain)}`;

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ padding: "15px 18px 12px", borderBottom: "1px solid var(--border-3)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 11,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 700 }}>{title}</div>
          <div className="mdp-mono" style={{ fontSize: 10.5, color: "var(--faint)" }}>
            {units.length} shown
          </div>
        </div>
        {focusedState && grain !== "state" && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "4px 10px",
              background: "var(--accent-soft)",
              border: "1px solid var(--accent-border)",
              borderRadius: 99,
              marginBottom: 11,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)" }}>
              {focusedState}
            </span>
            <span
              onClick={onClearFocus}
              style={{ cursor: "pointer", color: "var(--accent)", fontSize: 13, lineHeight: 1 }}
            >
              ×
            </span>
          </div>
        )}
        <div style={{ display: "flex", gap: 5 }}>
          {SORTS.map((s) => (
            <button
              key={s.id}
              type="button"
              style={sortBtnStyle(sort === s.id)}
              onClick={() => onSortChange(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 12px 16px" }}>
        {units.map((u, i) => {
          const vm = VERDICT_META[u.verdict];
          const selected = selectedKey === u.unit_key;
          const showHatch = u.verdict === "blind" || u.verdict === "unknown";
          return (
            <div
              key={u.unit_key}
              onClick={() => onSelect(u)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 11,
                padding: "11px 11px",
                borderRadius: 11,
                cursor: "pointer",
                marginBottom: 3,
                background: selected ? "#f4f5ff" : "transparent",
                border: `1px solid ${selected ? "var(--accent-border)" : "transparent"}`,
              }}
            >
              <div style={{ width: 28, textAlign: "center", flexShrink: 0 }}>
                <span
                  className="mdp-mono"
                  style={{ fontSize: 12, fontWeight: 600, color: "var(--faint)" }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <div
                style={{
                  width: 5,
                  height: 34,
                  borderRadius: 99,
                  background: vm.color,
                  flexShrink: 0,
                  backgroundImage: hatchCss(showHatch),
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                  <span
                    style={{
                      flex: "1 1 auto",
                      minWidth: 0,
                      fontSize: 13,
                      fontWeight: 700,
                      color: "var(--ink-2)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {u.name}
                  </span>
                  {u.watched && (
                    <span style={{ flex: "none", color: "var(--accent)", fontSize: 11 }}>★</span>
                  )}
                  {u.hasNote && (
                    <span
                      style={{
                        flex: "none",
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: "var(--accent)",
                      }}
                    />
                  )}
                </div>
                <div className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)", marginTop: 1 }}>
                  {u.sub}
                </div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 800,
                    color: riskColor(u.risk),
                    lineHeight: 1,
                  }}
                >
                  {u.risk}
                </div>
                <div className="mdp-mono" style={{ fontSize: 9, color: "var(--faint)", marginTop: 2 }}>
                  CONF {u.conf}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
