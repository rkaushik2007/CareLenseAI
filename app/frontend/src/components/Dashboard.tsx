"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import IndiaMap from "@/components/IndiaMap";
import Modals from "@/components/Modals";
import QuadrantView from "@/components/QuadrantView";
import RankedList from "@/components/RankedList";
import UnitDetail from "@/components/UnitDetail";
import type {
  Capability,
  GeoFeature,
  Grain,
  Scenario,
  SortKey,
  TabKey,
  Unit,
  UnitDetail as UnitDetailType,
} from "@/lib/api";
import {
  CAP_DOTS,
  askQuestion,
  extractStateFromUnit,
  fetchCapabilities,
  fetchGeo,
  fetchScenarios,
  fetchUnitDetail,
  fetchUnits,
} from "@/lib/api";
import {
  applyTheme,
  capBtnStyle,
  getStoredTheme,
  grainBtnStyle,
  segBtnStyle,
  setStoredTheme,
  tabBtnStyle,
  type Theme,
} from "@/lib/theme";
import { VERDICT_META, grainLabel, hatchCss, sortUnitsClient, summaryFromUnits } from "@/lib/verdict";

function normalize(s: string): string {
  return s.toLowerCase().replace(/[^a-z]/g, "");
}

function Logo() {
  return (
    <svg
      viewBox="0 0 72 84"
      style={{ height: 38, width: "auto", display: "block", flexShrink: 0 }}
      fill="none"
      aria-label="CareLens AI"
    >
      <defs>
        <linearGradient id="clpin" x1="14" y1="6" x2="58" y2="74" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#46ccf5" />
          <stop offset="0.55" stopColor="#2e86e4" />
          <stop offset="1" stopColor="#2256d6" />
        </linearGradient>
        <linearGradient id="clpup" x1="26" y1="21" x2="46" y2="42" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#23b9cb" />
          <stop offset="1" stopColor="#2a7de1" />
        </linearGradient>
      </defs>
      <path
        d="M36 4C19 4 6 17 6 33C6 45 16 56 30 67C32.5 69 34 71.5 36 77C38 71.5 39.5 69 42 67C56 56 66 45 66 33C66 17 53 4 36 4Z"
        fill="url(#clpin)"
      />
      <g stroke="#7ad8ff" strokeWidth="1.6" strokeLinecap="round">
        <path d="M55 20 L61.5 13.5" />
        <path d="M57 33 L65 33" />
        <path d="M17 47 L9.5 54" />
      </g>
      <g fill="#7ad8ff">
        <circle cx="62.6" cy="12.4" r="2.6" />
        <circle cx="66.4" cy="33" r="2.6" />
        <circle cx="8.4" cy="55" r="2.6" />
      </g>
      <path d="M13 31 Q36 14 59 31 Q36 48 13 31 Z" fill="#ffffff" />
      <path d="M20 31 Q36 19.5 52 31 Q36 42.5 20 31 Z" fill="url(#clpup)" />
      <path
        d="M24 31 H29.5 L32.4 24 L35.6 39 L38.6 27.5 L41 31 H48"
        stroke="#ffffff"
        strokeWidth="2.4"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx="30.5" cy="26.5" r="1.5" fill="#ffffff" opacity="0.9" />
    </svg>
  );
}

export default function Dashboard() {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [capabilitiesError, setCapabilitiesError] = useState(false);
  const [cap, setCap] = useState("icu");
  const [grain, setGrain] = useState<Grain>("state");
  const [overlay, setOverlay] = useState(true);
  const [sort, setSort] = useState<SortKey>("priority");
  const [tab, setTab] = useState<TabKey>("map");
  const [units, setUnits] = useState<Unit[]>([]);
  const [geoData, setGeoData] = useState<GeoFeature[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<UnitDetailType | null>(null);
  const [query, setQuery] = useState("");
  const [focusedState, setFocusedState] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("light");
  const [scenarioName, setScenarioName] = useState("Baseline");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [showExport, setShowExport] = useState(false);
  const [showScenarios, setShowScenarios] = useState(false);
  const [askResult, setAskResult] = useState<string | null>(null);
  const [askLoading, setAskLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const t = getStoredTheme();
    setTheme(t);
    applyTheme(t);
  }, []);

  const loadScenarios = useCallback(async () => {
    try {
      const list = await fetchScenarios();
      setScenarios(list);
    } catch {
      setScenarios([]);
    }
  }, []);

  useEffect(() => {
    fetchCapabilities()
      .then((caps) => {
        setCapabilities(caps);
        setCapabilitiesError(false);
      })
      .catch(() => {
        setCapabilities([]);
        setCapabilitiesError(true);
      });
    loadScenarios();
  }, [loadScenarios]);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [u, g] = await Promise.all([fetchUnits(cap, grain), fetchGeo(cap, grain)]);
      setUnits(u);
      setGeoData(g);
    } catch (err) {
      setUnits([]);
      setGeoData([]);
      setLoadError(err instanceof Error ? err.message : "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [cap, grain]);

  useEffect(() => {
    refreshData();
    setSelectedKey(null);
    setDetail(null);
  }, [refreshData]);

  useEffect(() => {
    if (!selectedKey) {
      setDetail(null);
      return;
    }
    fetchUnitDetail(cap, selectedKey)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [selectedKey, cap]);

  const capLabel = useMemo(() => {
    return capabilities.find((c) => c.id === cap)?.label ?? cap;
  }, [capabilities, cap]);

  const filteredUnits = useMemo(() => {
    let list = units;
    if (focusedState && grain !== "state") {
      list = list.filter((u) => normalize(extractStateFromUnit(u)) === normalize(focusedState));
    }
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(
        (u) =>
          (u.name + u.sub + extractStateFromUnit(u)).toLowerCase().includes(q),
      );
    }
    return sortUnitsClient(list, sort);
  }, [units, focusedState, grain, query, sort]);

  const summary = useMemo(() => {
    const counts = summaryFromUnits(units);
    const total = units.length || 1;
    return (["desert", "blind", "served", "unknown"] as const).map((key) => ({
      key,
      label:
        key === "desert"
          ? "Confirmed deserts"
          : key === "blind"
            ? "Blind spots"
            : key === "served"
              ? "Adequately served"
              : "Unverified",
      color: VERDICT_META[key].color,
      count: counts[key],
      pct: `${Math.round((counts[key] / total) * 100)}%`,
    }));
  }, [units]);

  const watchCount = useMemo(() => units.filter((u) => u.watched).length, [units]);
  const watchedUnitKeys = useMemo(
    () => units.filter((u) => u.watched).map((u) => u.unit_key),
    [units],
  );

  const handleSelect = (unit: Unit) => {
    setSelectedKey(unit.unit_key);
    setFocusedState(extractStateFromUnit(unit));
  };

  const handleTheme = (t: Theme) => {
    setTheme(t);
    setStoredTheme(t);
    applyTheme(t);
  };

  const handleApplyScenario = (sc: Scenario) => {
    setCap(sc.cap);
    setGrain(sc.grain);
    setOverlay(sc.overlay);
    setSort(sc.sort);
    setScenarioName(sc.name);
    setSelectedKey(null);
    setShowScenarios(false);
  };

  const handleSearchKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter" || !query.trim()) return;
    setAskLoading(true);
    setAskResult(null);
    try {
      const res = await askQuestion(query.trim());
      setAskResult(res.answer || res.error || "No answer returned.");
    } catch {
      setAskResult("Unable to reach Genie. Try again later.");
    } finally {
      setAskLoading(false);
    }
  };

  const grains: Array<{ id: Grain; label: string }> = [
    { id: "state", label: "State" },
    { id: "district", label: "District" },
    { id: "pin", label: "PIN" },
  ];

  const legend = [
    {
      title: "Confirmed desert",
      desc: "High risk · strong evidence",
      color: "#d23f2d",
      hatch: "none",
    },
    {
      title: "Blind spot",
      desc: "High risk · thin data — verify",
      color: "#e0a32b",
      hatch: hatchCss(true),
    },
    {
      title: "Adequately served",
      desc: "Low risk · well evidenced",
      color: "#2f9e6b",
      hatch: "none",
    },
    {
      title: "Unverified",
      desc: "Low signal both axes",
      color: "#cfd3db",
      hatch: hatchCss(true),
    },
  ];

  return (
    <div className="mdp-app">
      <header
        className="mdp-no-print"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          height: 66,
          minHeight: 66,
          padding: "0 22px",
          background: "var(--panel)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Logo />
          <div style={{ lineHeight: 1.05 }}>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.02em" }}>
              <span style={{ color: "var(--ink)" }}>CareLens</span>
              <span style={{ color: "#19b1cf" }}> AI</span>
            </div>
            <div
              className="mdp-mono"
              style={{
                fontSize: 8.5,
                fontWeight: 500,
                color: "var(--faint)",
                letterSpacing: "0.07em",
                marginTop: 2,
              }}
            >
              MEDICAL DESERT PLANNER · TRACK 2
            </div>
          </div>
        </div>

        <div style={{ position: "relative", flex: "0 1 360px", minWidth: 300 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              height: 34,
              padding: "0 12px",
              background: "var(--panel-2)",
              border: "1px solid var(--border-2)",
              borderRadius: 9,
            }}
          >
            <div
              style={{
                width: 13,
                height: 13,
                border: "1.8px solid var(--faint)",
                borderRadius: "50%",
                position: "relative",
                flexShrink: 0,
              }}
            />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setAskResult(null);
                const q = e.target.value.trim().toLowerCase();
                if (q && grain !== "state") {
                  const match = units.find(
                    (u) =>
                      normalize(extractStateFromUnit(u)) === normalize(q) ||
                      u.name.toLowerCase() === q,
                  );
                  if (match) setFocusedState(extractStateFromUnit(match));
                }
              }}
              onKeyDown={handleSearchKeyDown}
              placeholder="Search a state, district or PIN… (Enter to ask Genie)"
              style={{
                border: "none",
                outline: "none",
                background: "transparent",
                fontFamily: "inherit",
                fontSize: 13,
                color: "var(--ink)",
                width: "100%",
              }}
            />
          </div>
          {(askResult || askLoading) && (
            <div className="mdp-ask-result">
              {askLoading ? "Asking Genie…" : askResult}
            </div>
          )}
        </div>

        <div style={{ flex: 1 }} />

        <div
          style={{
            display: "flex",
            gap: 3,
            padding: 3,
            background: "var(--panel-2)",
            border: "1px solid var(--border-2)",
            borderRadius: 9,
          }}
        >
          <button
            type="button"
            title="Light theme"
            style={segBtnStyle(theme !== "dark")}
            onClick={() => handleTheme("light")}
          >
            <span
              style={{
                width: 13,
                height: 13,
                borderRadius: "50%",
                border: "2px solid currentColor",
                display: "block",
              }}
            />
          </button>
          <button
            type="button"
            title="Dark theme"
            style={segBtnStyle(theme === "dark")}
            onClick={() => handleTheme("dark")}
          >
            <span
              style={{
                width: 13,
                height: 13,
                borderRadius: "50%",
                boxShadow: "inset -4px -3px 0 0 currentColor",
                display: "block",
              }}
            />
          </button>
        </div>

        <button
          type="button"
          onClick={() => setShowScenarios(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            height: 34,
            padding: "0 13px",
            background: "var(--panel-2)",
            border: "1px solid var(--border-2)",
            borderRadius: 9,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <div
            style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }}
          />
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-2)" }}>
            {scenarioName}
          </span>
          <span className="mdp-mono" style={{ fontSize: 10, color: "var(--faint)" }}>
            SCENARIO
          </span>
        </button>

        <button
          type="button"
          onClick={() => setShowExport(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            height: 34,
            padding: "0 15px",
            background: "var(--solid)",
            border: "none",
            borderRadius: 9,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--solid-ink)" }}>
            Export plan
          </span>
          <span style={{ fontSize: 11, color: "var(--solid-ink)", fontWeight: 600 }}>
            {watchCount}
          </span>
        </button>
      </header>

      <div className="mdp-body-grid">
        <aside
          className="mdp-no-print"
          style={{
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            background: "var(--panel)",
            borderRight: "1px solid var(--border)",
            overflowY: "auto",
          }}
        >
          <div style={{ padding: "18px 18px 8px" }}>
            <div
              className="mdp-mono"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: "var(--faint)",
                letterSpacing: "0.08em",
                marginBottom: capabilitiesError ? 4 : 11,
              }}
            >
              CAPABILITY
            </div>
            {capabilitiesError ? (
              <div
                style={{
                  fontSize: 9,
                  color: "var(--warn, #c47a00)",
                  marginBottom: 8,
                  lineHeight: 1.3,
                }}
              >
                Coverage unavailable
              </div>
            ) : null}
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {(capabilities.length ? capabilities : Object.keys(CAP_DOTS).map((id) => ({
                id,
                label: id,
                dot: CAP_DOTS[id],
              }))).map((c) => (
                <button
                  key={c.id}
                  type="button"
                  style={capBtnStyle(cap === c.id)}
                  onClick={() => {
                    setCap(c.id);
                    setSelectedKey(null);
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 2,
                        background: c.dot || CAP_DOTS[c.id],
                      }}
                    />
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{c.label}</span>
                  </span>
                  <span className="mdp-mono" style={{ fontSize: 10, opacity: 0.6 }}>
                    {capabilitiesError || c.coverage == null ? "—" : c.coverage.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div style={{ height: 1, background: "var(--border-3)", margin: "14px 18px" }} />

          <div style={{ padding: "0 18px" }}>
            <div
              className="mdp-mono"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: "var(--faint)",
                letterSpacing: "0.08em",
                marginBottom: 10,
              }}
            >
              GEOGRAPHIC GRAIN
            </div>
            <div
              style={{
                display: "flex",
                gap: 5,
                padding: 4,
                background: "var(--panel-2)",
                border: "1px solid var(--border-3)",
                borderRadius: 10,
              }}
            >
              {grains.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  style={grainBtnStyle(grain === g.id)}
                  onClick={() => {
                    setGrain(g.id);
                    setSelectedKey(null);
                    setFocusedState(null);
                  }}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: "16px 18px 0" }}>
            <div
              className="mdp-mono"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: "var(--faint)",
                letterSpacing: "0.08em",
                marginBottom: 10,
              }}
            >
              UNCERTAINTY OVERLAY
            </div>
            <button
              type="button"
              onClick={() => setOverlay(!overlay)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "11px 12px",
                background: "var(--panel-3)",
                border: "1px solid var(--border-3)",
                borderRadius: 10,
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "inherit",
              }}
            >
              <span style={{ display: "block" }}>
                <span
                  style={{
                    display: "block",
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: "var(--ink-2)",
                  }}
                >
                  Hatch data-poor areas
                </span>
                <span
                  style={{ display: "block", fontSize: 11, color: "var(--faint)", marginTop: 2 }}
                >
                  Mark low-evidence regions
                </span>
              </span>
              <span
                style={{
                  width: 36,
                  height: 21,
                  borderRadius: 99,
                  background: overlay ? "var(--accent)" : "var(--track-off)",
                  position: "relative",
                  flexShrink: 0,
                  transition: "background .15s",
                }}
              >
                <span
                  style={{
                    position: "absolute",
                    top: 2,
                    left: overlay ? 17 : 2,
                    width: 17,
                    height: 17,
                    borderRadius: "50%",
                    background: "#fff",
                    boxShadow: "0 1px 3px rgba(0,0,0,.35)",
                    transition: "left .15s",
                  }}
                />
              </span>
            </button>
          </div>

          <div style={{ height: 1, background: "var(--border-3)", margin: "16px 18px" }} />

          <div style={{ padding: "0 18px 18px" }}>
            <div
              className="mdp-mono"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: "var(--faint)",
                letterSpacing: "0.08em",
                marginBottom: 11,
              }}
            >
              VERDICT LEGEND
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {legend.map((l) => (
                <div key={l.title} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <span
                    style={{
                      width: 13,
                      height: 13,
                      borderRadius: 4,
                      background: l.color,
                      marginTop: 1,
                      flexShrink: 0,
                      backgroundImage: l.hatch,
                    }}
                  />
                  <span style={{ display: "block" }}>
                    <span
                      style={{
                        display: "block",
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--ink-2)",
                        lineHeight: 1.2,
                      }}
                    >
                      {l.title}
                    </span>
                    <span
                      style={{
                        display: "block",
                        fontSize: 10.5,
                        color: "var(--faint)",
                        lineHeight: 1.25,
                        marginTop: 1,
                      }}
                    >
                      {l.desc}
                    </span>
                  </span>
                </div>
              ))}
            </div>
            <div
              style={{
                marginTop: 16,
                padding: "11px 12px",
                background: "var(--callout-bg)",
                border: "1px solid var(--callout-border)",
                borderRadius: 10,
              }}
            >
              <div style={{ fontSize: 11, color: "var(--callout-ink)", lineHeight: 1.45 }}>
                A region is only a{" "}
                <b style={{ color: "var(--callout-strong)" }}>confirmed desert</b> when high risk
                meets high evidence. High risk on thin data is a{" "}
                <b style={{ color: "var(--callout-strong)" }}>blind spot</b> — not a conclusion.
              </div>
            </div>
          </div>
        </aside>

        <main
          className="mdp-no-print"
          style={{
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            minWidth: 0,
            padding: 16,
            gap: 14,
            overflow: "hidden",
          }}
        >
          {loadError ? (
            <div
              style={{
                margin: "0 16px",
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid #e57373",
                background: "rgba(229,115,115,0.12)",
                color: "var(--ink)",
                fontSize: 12,
              }}
            >
              Data API error: {loadError}. Open /api/health/data in this app for SQL diagnostics.
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 10 }}>
            {summary.map((s) => (
              <div
                key={s.key}
                style={{
                  flex: 1,
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  borderRadius: 13,
                  padding: "12px 14px",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: 3,
                    height: "100%",
                    background: s.color,
                  }}
                />
                <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
                  <span
                    style={{
                      fontSize: 26,
                      fontWeight: 800,
                      letterSpacing: "-0.02em",
                      color: "var(--ink)",
                    }}
                  >
                    {loading ? "—" : s.count}
                  </span>
                  <span
                    className="mdp-mono"
                    style={{ fontSize: 10, color: s.color, fontWeight: 600 }}
                  >
                    {loading ? "" : s.pct}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    fontWeight: 600,
                    color: "var(--muted)",
                    marginTop: 1,
                  }}
                >
                  {s.label}
                </div>
              </div>
            ))}
          </div>

          <div
            style={{
              flex: 1,
              minHeight: 0,
              background: "var(--panel)",
              border: "1px solid var(--border)",
              borderRadius: 14,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "13px 16px",
                borderBottom: "1px solid var(--border-3)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 4,
                  padding: 4,
                  background: "var(--panel-2)",
                  borderRadius: 9,
                }}
              >
                <button
                  type="button"
                  style={tabBtnStyle(tab === "map")}
                  onClick={() => setTab("map")}
                >
                  Map
                </button>
                <button
                  type="button"
                  style={tabBtnStyle(tab === "quad")}
                  onClick={() => setTab("quad")}
                >
                  Risk × Confidence
                </button>
              </div>
              <div style={{ flex: 1 }} />
              <div style={{ fontSize: 13, color: "var(--muted)" }}>
                {tab === "map"
                  ? `Care-gap risk · ${capLabel}`
                  : `Risk vs. evidence · ${capLabel}`}
              </div>
              <div className="mdp-mono" style={{ fontSize: 10.5, color: "var(--faint)" }}>
                {units.length} {grainLabel(grain)} · overlay {overlay ? "ON" : "OFF"}
              </div>
            </div>

            <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
              <IndiaMap
                geoData={geoData}
                grain={grain}
                overlay={overlay}
                tab={tab}
                selectedKey={selectedKey}
                focusedState={focusedState}
                theme={theme}
                onSelect={handleSelect}
                units={units}
              />
              <QuadrantView
                units={units}
                tab={tab}
                selectedKey={selectedKey}
                onSelect={handleSelect}
              />
            </div>
          </div>
        </main>

        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            background: "var(--panel)",
            borderLeft: "1px solid var(--border)",
          }}
        >
          {detail && selectedKey ? (
            <UnitDetail
              detail={detail}
              cap={cap}
              capLabel={capLabel}
              onBack={() => setSelectedKey(null)}
              onUpdated={refreshData}
            />
          ) : (
            <RankedList
              units={filteredUnits}
              sort={sort}
              grain={grain}
              selectedKey={selectedKey}
              focusedState={focusedState}
              onSortChange={setSort}
              onSelect={handleSelect}
              onClearFocus={() => setFocusedState(null)}
            />
          )}
        </aside>
      </div>

      <Modals
        showExport={showExport}
        showScenarios={showScenarios}
        cap={cap}
        capLabel={capLabel}
        scenarioName={scenarioName}
        scenarios={scenarios}
        watchCount={watchCount}
        watchedUnitKeys={watchedUnitKeys}
        overlay={overlay}
        sort={sort}
        grain={grain}
        onClose={() => {
          setShowExport(false);
          setShowScenarios(false);
        }}
        onApplyScenario={handleApplyScenario}
        onScenariosChange={loadScenarios}
        onScenarioNameChange={setScenarioName}
      />
    </div>
  );
}
