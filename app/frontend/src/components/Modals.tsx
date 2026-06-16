"use client";

import { useEffect, useState } from "react";
import type { Capability, ExportPayload, Scenario, SortKey } from "@/lib/api";
import {
  deleteScenario,
  fetchExport,
  generateVerificationPlan,
  saveScenario,
} from "@/lib/api";
import { VERDICT_META } from "@/lib/verdict";

interface ModalsProps {
  showExport: boolean;
  showScenarios: boolean;
  cap: string;
  capLabel: string;
  scenarioName: string;
  scenarios: Scenario[];
  watchCount: number;
  watchedUnitKeys: string[];
  overlay: boolean;
  sort: SortKey;
  grain: string;
  onClose: () => void;
  onApplyScenario: (scenario: Scenario) => void;
  onScenariosChange: () => void;
  onScenarioNameChange: (name: string) => void;
}

export default function Modals({
  showExport,
  showScenarios,
  cap,
  capLabel,
  scenarioName,
  scenarios,
  watchCount,
  watchedUnitKeys,
  overlay,
  sort,
  grain,
  onClose,
  onApplyScenario,
  onScenariosChange,
  onScenarioNameChange,
}: ModalsProps) {
  const [newScenario, setNewScenario] = useState("");
  const [exportData, setExportData] = useState<ExportPayload | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [planText, setPlanText] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);

  useEffect(() => {
    if (!showExport) {
      setExportData(null);
      setPlanText(null);
      return;
    }
    let cancelled = false;
    setExportLoading(true);
    fetchExport(cap)
      .then((data) => {
        if (!cancelled) setExportData(data);
      })
      .catch(() => {
        if (!cancelled) setExportData({ capability: cap, regions: [] });
      })
      .finally(() => {
        if (!cancelled) setExportLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [showExport, cap]);

  const handleSaveScenario = async () => {
    const name = newScenario.trim();
    if (!name) return;
    await saveScenario({ name, cap, grain: grain as Scenario["grain"], overlay, sort });
    setNewScenario("");
    onScenarioNameChange(name);
    onScenariosChange();
  };

  const handleDeleteScenario = async (name: string) => {
    await deleteScenario(name);
    onScenariosChange();
  };

  const handleGeneratePlan = async () => {
    setPlanLoading(true);
    try {
      const res = await generateVerificationPlan(watchedUnitKeys, cap);
      setPlanText(res.plan || "Verification plan unavailable.");
    } catch {
      setPlanText("Verification plan unavailable. Check Agent configuration.");
    } finally {
      setPlanLoading(false);
    }
  };

  const regions = exportData?.regions ?? [];
  const hasWatch = watchCount > 0;

  return (
    <>
      {showExport && (
        <div className="mdp-modal-backdrop mdp-no-print" onClick={onClose}>
          <div
            className="mdp-modal"
            style={{ width: 560, maxHeight: "80vh" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: "20px 22px", borderBottom: "1px solid var(--border-3)" }}>
              <div
                style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.01em" }}
              >
                Care-gap action plan
              </div>
              <div style={{ fontSize: 12.5, color: "var(--faint)", marginTop: 2 }}>
                {scenarioName} · {capLabel} · generated for planner review
              </div>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px" }}>
              {exportLoading && (
                <div style={{ padding: 40, textAlign: "center", color: "var(--faint)" }}>
                  Loading export…
                </div>
              )}
              {!exportLoading && hasWatch && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {regions.map((r) => {
                    const vm = VERDICT_META[r.verdict];
                    return (
                      <div
                        key={r.name}
                        style={{
                          padding: "13px 14px",
                          border: "1px solid var(--border-3)",
                          borderRadius: 12,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <span style={{ fontSize: 14, fontWeight: 700 }}>{r.name}</span>
                          <span style={{ fontSize: 11.5, fontWeight: 700, color: vm.color }}>
                            {vm.label}
                          </span>
                        </div>
                        <div
                          className="mdp-mono"
                          style={{ fontSize: 10.5, color: "var(--faint)", margin: "4px 0 7px" }}
                        >
                          {r.sub} · RISK {r.risk} · CONF {r.conf}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.45 }}>
                          {r.action}
                        </div>
                        {r.note && (
                          <div
                            style={{
                              marginTop: 7,
                              fontSize: 11.5,
                              color: "var(--accent)",
                              background: "var(--accent-soft)",
                              padding: "6px 9px",
                              borderRadius: 8,
                            }}
                          >
                            Note · {r.note}
                          </div>
                        )}
                        {r.citations && r.citations.length > 0 && (
                          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                            {r.citations.map((c) => (
                              <div
                                key={c.rec_id}
                                className="mdp-mono"
                                style={{ fontSize: 10, color: "var(--faint)" }}
                              >
                                {c.facility}: {c.quote?.slice(0, 80)}… ({c.source})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {!exportLoading && !hasWatch && (
                <div
                  style={{
                    padding: "40px 0",
                    textAlign: "center",
                    color: "var(--faint)",
                    fontSize: 13,
                  }}
                >
                  No regions on the watchlist yet. Star regions from the detail view to build a
                  plan.
                </div>
              )}
              {planText && (
                <div
                  style={{
                    marginTop: 16,
                    padding: "14px 16px",
                    background: "var(--panel-3)",
                    border: "1px solid var(--border-3)",
                    borderRadius: 12,
                  }}
                >
                  <div
                    className="mdp-mono"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--faint)",
                      marginBottom: 8,
                      letterSpacing: "0.06em",
                    }}
                  >
                    VERIFICATION PLAN
                  </div>
                  <div
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink-2)",
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {planText}
                  </div>
                </div>
              )}
            </div>
            <div
              style={{
                padding: "14px 22px",
                borderTop: "1px solid var(--border-3)",
                display: "flex",
                justifyContent: "flex-end",
                gap: 9,
              }}
            >
              <button
                type="button"
                onClick={onClose}
                style={{
                  height: 38,
                  padding: "0 16px",
                  background: "var(--panel-2)",
                  border: "1px solid var(--border-2)",
                  borderRadius: 10,
                  fontFamily: "inherit",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--ink-2)",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
              <button
                type="button"
                disabled={planLoading || !hasWatch}
                onClick={handleGeneratePlan}
                style={{
                  height: 38,
                  padding: "0 16px",
                  background: "var(--accent-soft)",
                  border: "1px solid var(--accent-border)",
                  borderRadius: 10,
                  fontFamily: "inherit",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--accent)",
                  cursor: hasWatch ? "pointer" : "not-allowed",
                  opacity: hasWatch ? 1 : 0.5,
                }}
              >
                {planLoading ? "Generating…" : "Generate verification plan"}
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                style={{
                  height: 38,
                  padding: "0 18px",
                  background: "var(--solid)",
                  border: "none",
                  borderRadius: 10,
                  fontFamily: "inherit",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--solid-ink)",
                  cursor: "pointer",
                }}
              >
                Print / save PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {showScenarios && (
        <div className="mdp-modal-backdrop mdp-no-print" onClick={onClose}>
          <div
            className="mdp-modal"
            style={{ width: 460 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: "20px 22px", borderBottom: "1px solid var(--border-3)" }}>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-0.01em" }}>
                Saved scenarios
              </div>
              <div style={{ fontSize: 12.5, color: "var(--faint)", marginTop: 2 }}>
                Capability, grain & overlay snapshots
              </div>
            </div>
            <div style={{ padding: "16px 22px" }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <input
                  value={newScenario}
                  onChange={(e) => setNewScenario(e.target.value)}
                  placeholder="Name this scenario…"
                  style={{
                    flex: 1,
                    height: 38,
                    padding: "0 12px",
                    border: "1px solid var(--border-2)",
                    borderRadius: 10,
                    fontFamily: "inherit",
                    fontSize: 13,
                    outline: "none",
                    background: "var(--panel)",
                    color: "var(--ink)",
                  }}
                />
                <button
                  type="button"
                  onClick={handleSaveScenario}
                  style={{
                    height: 38,
                    padding: "0 16px",
                    background: "var(--accent)",
                    border: "none",
                    borderRadius: 10,
                    fontFamily: "inherit",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--solid-ink)",
                    cursor: "pointer",
                  }}
                >
                  Save
                </button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {scenarios.map((sc) => (
                  <div
                    key={sc.name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 11,
                      padding: "11px 13px",
                      border: "1px solid var(--border-3)",
                      borderRadius: 11,
                    }}
                  >
                    <div
                      style={{ flex: 1, cursor: "pointer" }}
                      onClick={() => onApplyScenario(sc)}
                    >
                      <div style={{ fontSize: 13, fontWeight: 700 }}>{sc.name}</div>
                      <div
                        className="mdp-mono"
                        style={{ fontSize: 10, color: "var(--faint)", marginTop: 1 }}
                      >
                        {capLabelFor(sc.cap)} · {sc.grain} · {sc.overlay ? "overlay on" : "overlay off"}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onApplyScenario(sc)}
                      style={{
                        height: 30,
                        padding: "0 12px",
                        background: "var(--accent-soft)",
                        border: "none",
                        borderRadius: 8,
                        fontFamily: "inherit",
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--accent)",
                        cursor: "pointer",
                      }}
                    >
                      Load
                    </button>
                    <span
                      onClick={() => handleDeleteScenario(sc.name)}
                      style={{ cursor: "pointer", color: "var(--faint)", fontSize: 17, lineHeight: 1 }}
                    >
                      ×
                    </span>
                  </div>
                ))}
                {scenarios.length === 0 && (
                  <div
                    style={{
                      padding: "18px 0",
                      textAlign: "center",
                      color: "var(--faint)",
                      fontSize: 12.5,
                    }}
                  >
                    No saved scenarios yet.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function capLabelFor(capId: string): string {
  const labels: Record<string, string> = {
    icu: "ICU",
    maternity: "Maternity",
    emergency: "Emergency",
    oncology: "Oncology",
    trauma: "Trauma",
    nicu: "NICU",
    dialysis: "Dialysis",
  };
  return labels[capId] ?? capId;
}
