"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { UnitDetail as UnitDetailType, Verdict } from "@/lib/api";
import { normalizeSourceUrl, saveNote, setOverride, setWatch } from "@/lib/api";
import { VERDICT_META, riskColor, tierMeta } from "@/lib/verdict";

interface UnitDetailProps {
  detail: UnitDetailType;
  cap: string;
  capLabel: string;
  onBack: () => void;
  onUpdated: () => void;
}

const OVERRIDE_OPTS: Array<{ id: Verdict; label: string }> = [
  { id: "desert", label: "Confirmed desert" },
  { id: "blind", label: "Blind spot" },
  { id: "served", label: "Adequately served" },
  { id: "unknown", label: "Unverified" },
];

export default function UnitDetail({
  detail,
  cap,
  capLabel,
  onBack,
  onUpdated,
}: UnitDetailProps) {
  const [note, setNoteLocal] = useState(detail.note);
  const noteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const vm = VERDICT_META[detail.verdict];
  const supply = detail.supply;
  const tot = Math.max(supply.n, 1);

  useEffect(() => {
    setNoteLocal(detail.note);
  }, [detail.note, detail.unit_key]);

  const persistNote = useCallback(
    (value: string) => {
      if (noteTimer.current) clearTimeout(noteTimer.current);
      noteTimer.current = setTimeout(async () => {
        await saveNote(detail.unit_key, cap, value);
        onUpdated();
      }, 600);
    },
    [cap, detail.unit_key, onUpdated],
  );

  const handleNoteChange = (value: string) => {
    setNoteLocal(value);
    persistNote(value);
  };

  const handleOverride = async (verdict: Verdict) => {
    const next = detail.verdict === verdict ? null : verdict;
    await setOverride(detail.unit_key, cap, next);
    onUpdated();
  };

  const handleWatch = async () => {
    await setWatch(detail.unit_key, cap, !detail.watched);
    onUpdated();
  };

  const ovBtnStyle = (v: Verdict, active: boolean) => {
    const m = VERDICT_META[v];
    return {
      padding: "8px 0",
      borderRadius: 9,
      cursor: "pointer" as const,
      fontFamily: "inherit",
      fontSize: 12,
      fontWeight: 600,
      border: `1px solid ${active ? m.color : "var(--border-2)"}`,
      background: active ? m.bg : "var(--panel)",
      color: active ? m.ink : "var(--muted)",
    };
  };

  return (
    <div className="mdp-fade" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ padding: "16px 18px 14px", borderBottom: "1px solid var(--border-3)" }}>
        <button
          type="button"
          onClick={onBack}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "none",
            border: "none",
            padding: 0,
            cursor: "pointer",
            color: "var(--faint)",
            fontFamily: "inherit",
            fontSize: 11.5,
            fontWeight: 600,
            marginBottom: 11,
          }}
        >
          ‹ Back to ranking
        </button>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 19,
                fontWeight: 800,
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            >
              {detail.name}
            </div>
            <div className="mdp-mono" style={{ fontSize: 11, color: "var(--faint)", marginTop: 3 }}>
              {detail.sub}
            </div>
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 10px",
              borderRadius: 99,
              background: vm.bg,
              flexShrink: 0,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: vm.color,
              }}
            />
            <span style={{ fontSize: 11.5, fontWeight: 700, color: vm.ink }}>{vm.label}</span>
          </div>
        </div>
        {detail.overridden && (
          <div
            style={{
              marginTop: 9,
              fontSize: 11,
              color: "var(--warn-ink)",
              background: "var(--warn-bg)",
              border: "1px solid var(--warn-border)",
              padding: "6px 9px",
              borderRadius: 8,
            }}
          >
            Verdict manually overridden ·{" "}
            <span
              onClick={() => setOverride(detail.unit_key, cap, null).then(onUpdated)}
              style={{ textDecoration: "underline", cursor: "pointer" }}
            >
              reset to model
            </span>
          </div>
        )}
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px 18px 22px" }}>
        <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
          <div
            style={{
              flex: 1,
              padding: "12px 13px",
              background: "var(--panel-3)",
              border: "1px solid var(--border-3)",
              borderRadius: 11,
            }}
          >
            <div
              className="mdp-mono"
              style={{ fontSize: 9.5, color: "var(--faint)", letterSpacing: "0.05em" }}
            >
              CARE-GAP RISK
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 3 }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: riskColor(detail.risk) }}>
                {detail.risk}
              </span>
              <span style={{ fontSize: 12, color: "var(--faint)", fontWeight: 600 }}>/100</span>
            </div>
            <div
              style={{
                height: 5,
                borderRadius: 99,
                background: "var(--border-3)",
                marginTop: 7,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${detail.risk}%`,
                  background: riskColor(detail.risk),
                }}
              />
            </div>
          </div>
          <div
            style={{
              flex: 1,
              padding: "12px 13px",
              background: "var(--panel-3)",
              border: "1px solid var(--border-3)",
              borderRadius: 11,
            }}
          >
            <div
              className="mdp-mono"
              style={{ fontSize: 9.5, color: "var(--faint)", letterSpacing: "0.05em" }}
            >
              DATA CONFIDENCE
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 3 }}>
              <span style={{ fontSize: 24, fontWeight: 800, color: "var(--ink-2)" }}>
                {detail.conf}
              </span>
              <span style={{ fontSize: 12, color: "var(--faint)", fontWeight: 600 }}>/100</span>
            </div>
            <div
              style={{
                height: 5,
                borderRadius: 99,
                background: "var(--border-3)",
                marginTop: 7,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${detail.conf}%`,
                  background: "#6b7180",
                }}
              />
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div
            className="mdp-mono"
            style={{ fontSize: 10, fontWeight: 600, color: "var(--faint)", letterSpacing: "0.06em" }}
          >
            NEED DRIVERS · {capLabel}
          </div>
          {detail.need.nfhs_matched && detail.need.index != null ? (
            <div className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)" }}>
              index {Math.round(detail.need.index)}
            </div>
          ) : (
            <div className="mdp-mono" style={{ fontSize: 10, color: "var(--warn-ink)" }}>
              need signal unavailable
            </div>
          )}
        </div>
        {detail.need.drivers.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
            {detail.need.drivers.map((d) => (
              <div
                key={d.label}
                style={{
                  padding: "10px 12px",
                  background: "var(--panel-3)",
                  border: "1px solid var(--border-3)",
                  borderRadius: 10,
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)" }}>{d.label}</div>
                <div className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)", marginTop: 3 }}>
                  {d.value != null ? `${d.value}%` : "—"} · {d.direction.replace(/_/g, " ")}
                </div>
              </div>
            ))}
          </div>
        ) : !detail.need.nfhs_matched ? (
          <div
            style={{
              fontSize: 12,
              color: "var(--muted)",
              marginBottom: 18,
              padding: "10px 12px",
              background: "var(--callout-bg)",
              border: "1px solid var(--callout-border)",
              borderRadius: 10,
            }}
          >
            No direct NFHS need indicator matched for this district. High supply deficit alone
            drives risk.
          </div>
        ) : null}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div
            className="mdp-mono"
            style={{ fontSize: 10, fontWeight: 600, color: "var(--faint)", letterSpacing: "0.06em" }}
          >
            EVIDENCE LEDGER · {capLabel}
          </div>
          <div className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)" }}>
            {supply.n} facilities
          </div>
        </div>
        {supply.n === 0 ? (
          <div
            style={{
              fontSize: 12.5,
              color: "var(--muted)",
              marginBottom: 16,
              fontStyle: "italic",
            }}
          >
            No claims found for this capability in this unit.
          </div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
              <div
                style={{
                  flex: Math.max(0.04, supply.strong / tot),
                  height: 7,
                  borderRadius: 99,
                  background: "#2f9e6b",
                }}
                title="strong"
              />
              <div
                style={{
                  flex: Math.max(0.04, supply.partial / tot),
                  height: 7,
                  borderRadius: 99,
                  background: "#e0a32b",
                }}
                title="partial"
              />
              <div
                style={{
                  flex: Math.max(0.04, supply.weak / tot),
                  height: 7,
                  borderRadius: 99,
                  background: "#d6d9e0",
                }}
                title="weak"
              />
            </div>
            <div style={{ display: "flex", gap: 14, marginBottom: 16 }}>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                <b style={{ color: "#2f9e6b" }}>{supply.strong}</b> strong
              </span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                <b style={{ color: "#c08416" }}>{supply.partial}</b> partial
              </span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                <b style={{ color: "var(--faint)" }}>{supply.weak}</b> weak/claim-only
              </span>
            </div>
          </>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 9, marginBottom: 20 }}>
          {detail.evidence.length === 0 && supply.n > 0 && (
            <div style={{ fontSize: 12, color: "var(--faint)", fontStyle: "italic" }}>
              Facilities matched but no citation spans available.
            </div>
          )}
          {detail.evidence.map((e, idx) => {
            const tm = tierMeta(e.tier);
            const sourceUrl = normalizeSourceUrl(e.source_url);
            return (
              <div
                key={`${e.rec_id}-${idx}`}
                style={{
                  padding: "12px 13px",
                  background: "var(--panel)",
                  border: "1px solid var(--border-3)",
                  borderRadius: 11,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-2)" }}>
                    {e.facility}
                  </span>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "2px 8px",
                      borderRadius: 99,
                      background: tm.tagBg,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: tm.tagColor,
                      }}
                    />
                    <span style={{ fontSize: 10, fontWeight: 700, color: tm.tagInk }}>
                      {tm.tag}
                    </span>
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: "var(--ink-2)",
                    lineHeight: 1.45,
                    fontStyle: "italic",
                  }}
                >
                  {e.quote}
                </div>
                <div className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)", marginTop: 7 }}>
                  source · {e.source}
                  {sourceUrl && (
                    <>
                      {" · "}
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "var(--accent)" }}
                      >
                        link
                      </a>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div
          className="mdp-mono"
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: "var(--faint)",
            letterSpacing: "0.06em",
            marginBottom: 9,
          }}
        >
          ANALYST OVERRIDE
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 6,
            marginBottom: 18,
          }}
        >
          {OVERRIDE_OPTS.map((o) => (
            <button
              key={o.id}
              type="button"
              style={ovBtnStyle(o.id, detail.verdict === o.id)}
              onClick={() => handleOverride(o.id)}
            >
              {o.label}
            </button>
          ))}
        </div>

        <div
          className="mdp-mono"
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: "var(--faint)",
            letterSpacing: "0.06em",
            marginBottom: 9,
          }}
        >
          PLANNER NOTE
        </div>
        <textarea
          value={note}
          onChange={(e) => handleNoteChange(e.target.value)}
          placeholder="Add context, a field observation, or a follow-up action…"
          style={{
            width: "100%",
            minHeight: 70,
            resize: "vertical",
            padding: "11px 12px",
            border: "1px solid var(--border-2)",
            borderRadius: 11,
            fontFamily: "inherit",
            fontSize: 12.5,
            color: "var(--ink-2)",
            outline: "none",
            background: "var(--panel-3)",
            lineHeight: 1.45,
          }}
        />
      </div>

      <div
        style={{
          padding: "12px 18px",
          borderTop: "1px solid var(--border-3)",
          display: "flex",
          gap: 8,
        }}
      >
        <button
          type="button"
          onClick={handleWatch}
          style={{
            flex: 1,
            height: 40,
            borderRadius: 11,
            cursor: "pointer",
            fontFamily: "inherit",
            fontSize: 13,
            fontWeight: 600,
            border: `1px solid ${detail.watched ? "var(--accent-border)" : "var(--border-2)"}`,
            background: detail.watched ? "var(--accent-soft)" : "var(--panel)",
            color: detail.watched ? "var(--accent)" : "var(--ink-2)",
          }}
        >
          {detail.watched ? "★ Remove from watchlist" : "☆ Add to watchlist"}
        </button>
      </div>
    </div>
  );
}
