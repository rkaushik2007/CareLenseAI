"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { feature } from "topojson-client";
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import type { GeoFeature, Grain, TabKey, Unit } from "@/lib/api";
import { extractDistrictFromUnit, extractStateFromUnit } from "@/lib/api";
import { applyTheme, getStoredTheme, mapStrokeColors, type Theme } from "@/lib/theme";
import {
  OVERLAY_CONF_THRESHOLD,
  VERDICT_META,
  hatchCss,
  quadrantRadius,
  riskColor,
} from "@/lib/verdict";

const MAP_URLS = [
  "https://cdn.jsdelivr.net/gh/udit-001/india-maps-data@main/geojson/india.geojson",
  "https://raw.githubusercontent.com/udit-001/india-maps-data/main/geojson/india.geojson",
];

const QW = 760;
const QH = 460;
const PAD_L = 56;
const PAD_R = 26;
const PAD_T = 30;
const PAD_B = 40;
const INNER_W = QW - PAD_L - PAD_R;
const INNER_H = QH - PAD_T - PAD_B;

function sx(conf: number): number {
  return PAD_L + (conf / 100) * INNER_W;
}

function sy(risk: number): number {
  return PAD_T + (1 - risk / 100) * INNER_H;
}

function stateName(props: GeoJsonProperties | null): string {
  if (!props) return "";
  return (
    (props.st_nm as string) ||
    (props.NAME_1 as string) ||
    (props.state as string) ||
    (props.STATE as string) ||
    ""
  );
}

function districtName(props: GeoJsonProperties | null): string {
  if (!props) return "";
  return (
    (props.district as string) ||
    (props.NAME_2 as string) ||
    (props.dt_name as string) ||
    ""
  );
}

function normalizeName(s: string): string {
  return s.toLowerCase().replace(/[^a-z]/g, "");
}

interface IndiaMapProps {
  geoData: GeoFeature[];
  grain: Grain;
  overlay: boolean;
  tab: TabKey;
  selectedKey: string | null;
  focusedState: string | null;
  theme: Theme;
  onSelect: (unit: Unit) => void;
  units: Unit[];
}

export default function IndiaMap({
  geoData,
  grain,
  overlay,
  tab,
  selectedKey,
  focusedState,
  theme,
  onSelect,
  units,
}: IndiaMapProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const geoRef = useRef<FeatureCollection | null>(null);
  const svgRef = useRef<d3.Selection<SVGSVGElement, unknown, null, undefined> | null>(null);
  const pathsRef = useRef<d3.Selection<SVGPathElement, Feature<Geometry, GeoJsonProperties>, SVGGElement, unknown> | null>(null);
  const hatchRef = useRef<d3.Selection<SVGPathElement, Feature<Geometry, GeoJsonProperties>, SVGGElement, unknown> | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);

  const metricLookup = useMemo(() => {
    const byState = new Map<string, GeoFeature>();
    const byDistrict = new Map<string, GeoFeature>();
    const byDistrictState = new Map<string, GeoFeature>();

    for (const g of geoData) {
      byState.set(normalizeName(g.state), g);
      if (g.district) {
        byDistrict.set(normalizeName(g.district), g);
        byDistrictState.set(`${normalizeName(g.district)}|${normalizeName(g.state)}`, g);
      }
      if (g.name) {
        byDistrict.set(normalizeName(g.name), g);
      }
    }

    return { byState, byDistrict, byDistrictState };
  }, [geoData]);

  const getMetric = useCallback(
    (props: GeoJsonProperties | null): GeoFeature | null => {
      const st = stateName(props);
      const dist = districtName(props);
      if (grain === "state") {
        return metricLookup.byState.get(normalizeName(st)) ?? null;
      }
      if (dist) {
        return (
          metricLookup.byDistrictState.get(`${normalizeName(dist)}|${normalizeName(st)}`) ??
          metricLookup.byDistrict.get(normalizeName(dist)) ??
          null
        );
      }
      return metricLookup.byState.get(normalizeName(st)) ?? null;
    },
    [grain, metricLookup],
  );

  const paint = useCallback(() => {
    if (!pathsRef.current || !hatchRef.current) return;
    const colors = mapStrokeColors(theme);

    const isFocused = (props: GeoJsonProperties | null) => {
      const st = stateName(props);
      if (focusedState && normalizeName(focusedState) === normalizeName(st)) return true;
      if (selectedKey) {
        const sel = units.find((u) => u.unit_key === selectedKey);
        if (sel && normalizeName(extractStateFromUnit(sel)) === normalizeName(st)) return true;
      }
      return false;
    };

    pathsRef.current
      .attr("fill", (d) => {
        const m = getMetric(d.properties);
        return m ? riskColor(m.risk) : "var(--border-3)";
      })
      .attr("stroke", (d) => (isFocused(d.properties) ? colors.focus : colors.stroke))
      .attr("stroke-width", (d) => (isFocused(d.properties) ? 0.9 : 0.35))
      .attr("fill-opacity", (d) => {
        const st = stateName(d.properties);
        if (focusedState && !isFocused(d.properties)) return 0.4;
        if (focusedState && normalizeName(focusedState) !== normalizeName(st)) return 0.4;
        return 1;
      });

    hatchRef.current.attr("opacity", (d) => {
      if (!overlay) return 0;
      const m = getMetric(d.properties);
      if (!m) return 0;
      return m.conf < OVERLAY_CONF_THRESHOLD
        ? Math.min(0.85, (OVERLAY_CONF_THRESHOLD - m.conf) / 45 + 0.3)
        : 0;
    });
  }, [theme, overlay, getMetric, focusedState, selectedKey, units]);

  const drawMap = useCallback(() => {
    const el = hostRef.current;
    const geo = geoRef.current;
    if (!el || !geo) return;

    el.innerHTML = "";
    const w = el.clientWidth || 700;
    const h = el.clientHeight || 500;
    const svg = d3.select(el).append("svg").attr("width", w).attr("height", h).style("display", "block");
    svgRef.current = svg;

    const defs = svg.append("defs");
    const hp = defs
      .append("pattern")
      .attr("id", "mdphatch")
      .attr("width", 5)
      .attr("height", 5)
      .attr("patternUnits", "userSpaceOnUse")
      .attr("patternTransform", "rotate(45)");
    hp.append("rect").attr("width", 5).attr("height", 5).attr("fill", "none");
    hp.append("line")
      .attr("x1", 0)
      .attr("y1", 0)
      .attr("x2", 0)
      .attr("y2", 5)
      .attr("stroke", "rgba(255,255,255,.75)")
      .attr("stroke-width", 2);

    const proj = d3.geoMercator().fitExtent(
      [
        [16, 12],
        [w - 16, h - 12],
      ],
      geo,
    );
    const pathGen = d3.geoPath(proj);
    const g = svg.append("g");

    const onClick = (_ev: MouseEvent, d: Feature<Geometry, GeoJsonProperties>) => {
      const st = stateName(d.properties);
      const dist = districtName(d.properties);
      if (!st) return;

      let unit: Unit | undefined;
      if (grain === "state") {
        unit = units.find((u) => normalizeName(u.name) === normalizeName(st));
      } else if (dist) {
        unit = units.find(
          (u) =>
            normalizeName(extractDistrictFromUnit(u) ?? "") === normalizeName(dist) &&
            normalizeName(extractStateFromUnit(u)) === normalizeName(st),
        );
      }
      if (!unit) {
        unit = units.find((u) => normalizeName(extractStateFromUnit(u)) === normalizeName(st));
      }
      if (unit) onSelect(unit);
    };

    pathsRef.current = g
      .selectAll("path")
      .data(geo.features)
      .enter()
      .append("path")
      .attr("d", pathGen as never)
      .style("cursor", "pointer")
      .on("click", onClick)
      .on("mouseenter", function () {
        d3.select(this).raise();
      })
      .on("mousemove", (ev: MouseEvent, d) => {
        const m = getMetric(d.properties);
        if (!m || !tipRef.current) return;
        const st = stateName(d.properties);
        const dist = districtName(d.properties);
        const title = grain === "state" ? st : dist ? `${dist} · ${st}` : st;
        const vm = VERDICT_META[m.verdict];
        tipRef.current.innerHTML = `<div style="font-weight:700;margin-bottom:2px">${title}</div><div class="mdp-mono" style="font-size:10px;color:#9aa3b4">RISK ${m.risk} · CONF ${m.conf} · <span style="color:${vm.color}">${vm.label}</span></div>`;
        tipRef.current.style.left = `${ev.clientX}px`;
        tipRef.current.style.top = `${ev.clientY}px`;
        tipRef.current.style.display = "block";
      })
      .on("mouseleave", () => {
        if (tipRef.current) tipRef.current.style.display = "none";
        paint();
      });

    hatchRef.current = g
      .selectAll("path.hatch")
      .data(geo.features)
      .enter()
      .append("path")
      .attr("class", "hatch")
      .attr("d", pathGen as never)
      .attr("fill", "url(#mdphatch)")
      .attr("pointer-events", "none")
      .attr("opacity", 0);

    paint();
  }, [getMetric, grain, onSelect, paint, units]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(false);
      let geojson: FeatureCollection | null = null;
      for (const url of MAP_URLS) {
        try {
          const r = await fetch(url);
          if (!r.ok) continue;
          const j = await r.json();
          if (j.type === "FeatureCollection") {
            geojson = j as FeatureCollection;
          } else if (j.objects) {
            const objKey = Object.keys(j.objects)[0];
            geojson = feature(j, j.objects[objKey]) as unknown as FeatureCollection;
          }
          if (geojson?.features?.length) break;
        } catch {
          geojson = null;
        }
      }
      if (cancelled) return;
      if (!geojson) {
        setError(true);
        setLoading(false);
        return;
      }
      geoRef.current = geojson;
      setLoading(false);
      setError(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!loading && !error && geoRef.current && tab === "map") {
      requestAnimationFrame(drawMap);
    }
  }, [loading, error, tab, drawMap]);

  useEffect(() => {
    paint();
  }, [paint, geoData, overlay, theme, focusedState, selectedKey]);

  useEffect(() => {
    if (tab === "map" && geoRef.current) {
      requestAnimationFrame(drawMap);
    }
  }, [tab, drawMap]);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <>
      <div
        ref={hostRef}
        style={{ position: "absolute", inset: 0, display: tab === "map" ? "block" : "none" }}
      />
      {loading && tab === "map" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span className="mdp-mono" style={{ fontSize: 12, color: "var(--faint)" }}>
            loading boundaries…
          </span>
        </div>
      )}
      {error && tab === "map" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 30,
          }}
        >
          <span
            style={{
              fontSize: 12.5,
              color: "var(--faint)",
              textAlign: "center",
              maxWidth: 280,
            }}
          >
            Map boundaries unavailable offline. The quadrant and ranked views carry the full
            analysis.
          </span>
        </div>
      )}
      <div
        style={{
          position: "absolute",
          left: 16,
          bottom: 14,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 12px",
          background: "var(--legend-bg)",
          border: "1px solid var(--border-2)",
          borderRadius: 10,
          backdropFilter: "blur(6px)",
        }}
      >
        <span className="mdp-mono" style={{ fontSize: 9.5, color: "var(--faint)" }}>
          LOW RISK
        </span>
        <span
          style={{
            width: 104,
            height: 9,
            borderRadius: 99,
            background: "linear-gradient(90deg,#79c39a,#e8d36a,#e79a3d,#d23f2d)",
          }}
        />
        <span className="mdp-mono" style={{ fontSize: 9.5, color: "var(--faint)" }}>
          HIGH
        </span>
        <span style={{ width: 1, height: 16, background: "var(--border)", margin: "0 2px" }} />
        <span
          style={{
            width: 14,
            height: 11,
            borderRadius: 3,
            backgroundImage:
              "repeating-linear-gradient(45deg,#cfd3db 0,#cfd3db 2px,transparent 2px,transparent 4px)",
            border: "1px solid #d8dbe2",
          }}
        />
        <span className="mdp-mono" style={{ fontSize: 9.5, color: "var(--faint)" }}>
          DATA-POOR
        </span>
      </div>
      <div ref={tipRef} className="mdp-map-tooltip" style={{ display: "none" }} />
    </>
  );
}

export { QW, QH, sx, sy, PAD_L, PAD_R, PAD_T, PAD_B, INNER_W, INNER_H };
