import type { Verdict } from "./api";

export const VERDICT_THRESHOLD = 58;
export const OVERLAY_CONF_THRESHOLD = 55;

export const VERDICT_COLORS: Record<Verdict, string> = {
  desert: "#d23f2d",
  blind: "#e0a32b",
  served: "#2f9e6b",
  unknown: "#9aa0ad",
};

export const VERDICT_META: Record<
  Verdict,
  { label: string; color: string; ink: string; bg: string; desc: string }
> = {
  desert: {
    label: "Confirmed desert",
    color: "#d23f2d",
    ink: "#a32b1c",
    bg: "#fbeae7",
    desc: "High risk · strong evidence",
  },
  blind: {
    label: "Blind spot",
    color: "#e0a32b",
    ink: "#a9781a",
    bg: "#fcf3e3",
    desc: "High risk · thin data — verify",
  },
  served: {
    label: "Adequately served",
    color: "#2f9e6b",
    ink: "#1f7a50",
    bg: "#e8f5ee",
    desc: "Low risk · well evidenced",
  },
  unknown: {
    label: "Unverified",
    color: "#9aa0ad",
    ink: "var(--muted)",
    bg: "#f1f2f5",
    desc: "Low signal both axes",
  },
};

const RISK_STOPS: Array<[number, [number, number, number]]> = [
  [0, [0.76, 0.1, 150]],
  [40, [0.85, 0.13, 95]],
  [66, [0.7, 0.16, 52]],
  [100, [0.55, 0.19, 27]],
];

export function riskColor(r: number): string {
  const t = Math.max(0, Math.min(100, r));
  let a = RISK_STOPS[0];
  let b = RISK_STOPS[RISK_STOPS.length - 1];
  for (let i = 0; i < RISK_STOPS.length - 1; i++) {
    if (t >= RISK_STOPS[i][0] && t <= RISK_STOPS[i + 1][0]) {
      a = RISK_STOPS[i];
      b = RISK_STOPS[i + 1];
      break;
    }
  }
  const f = (t - a[0]) / Math.max(1, b[0] - a[0]);
  const L = a[1][0] + (b[1][0] - a[1][0]) * f;
  const C = a[1][1] + (b[1][1] - a[1][1]) * f;
  const H = a[1][2] + (b[1][2] - a[1][2]) * f;
  return `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${H.toFixed(1)})`;
}

export function computeVerdict(risk: number, conf: number): Verdict {
  const T = VERDICT_THRESHOLD;
  if (risk >= T && conf >= T) return "desert";
  if (risk >= T && conf < T) return "blind";
  if (risk < T && conf >= T) return "served";
  return "unknown";
}

export function hatchCss(active: boolean): string {
  return active
    ? "repeating-linear-gradient(45deg, rgba(255,255,255,.55) 0, rgba(255,255,255,.55) 2px, transparent 2px, transparent 5px)"
    : "none";
}

export function tierMeta(tier: string): {
  tag: string;
  tagColor: string;
  tagBg: string;
  tagInk: string;
} {
  const t = tier.toUpperCase();
  if (t === "STRONG") {
    return { tag: "STRONG", tagColor: "#2f9e6b", tagBg: "#e8f5ee", tagInk: "#1f7a50" };
  }
  if (t === "PARTIAL") {
    return { tag: "PARTIAL", tagColor: "#e0a32b", tagBg: "#fcf3e3", tagInk: "#a9781a" };
  }
  return { tag: "WEAK", tagColor: "#9aa0ad", tagBg: "#f1f2f5", tagInk: "var(--muted)" };
}

export function quadrantRadius(nFacilities: number, k = 1.7): number {
  return Math.max(6, Math.min(20, Math.sqrt(Math.max(0, nFacilities)) * k));
}

export function sortUnitsClient<T extends { priority: number; risk: number; conf: number; name: string }>(
  units: T[],
  sort: "priority" | "risk" | "conf" | "az",
): T[] {
  const copy = [...units];
  if (sort === "az") {
    copy.sort((a, b) => a.name.localeCompare(b.name));
  } else if (sort === "risk") {
    copy.sort((a, b) => b.risk - a.risk);
  } else if (sort === "conf") {
    copy.sort((a, b) => a.conf - b.conf);
  } else {
    copy.sort((a, b) => b.priority - a.priority);
  }
  return copy;
}

export function summaryFromUnits(units: Array<{ verdict: Verdict }>): {
  desert: number;
  blind: number;
  served: number;
  unknown: number;
} {
  const counts = { desert: 0, blind: 0, served: 0, unknown: 0 };
  for (const u of units) counts[u.verdict]++;
  return counts;
}

export function grainLabel(grain: string): string {
  if (grain === "state") return "states";
  if (grain === "district") return "districts";
  return "PIN zones";
}
