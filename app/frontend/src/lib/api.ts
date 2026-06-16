export function normalizeSourceUrl(raw?: string | null): string | null {
  if (!raw) return null;
  const s = raw.trim();
  if (/^https?:\/\//i.test(s)) return s;
  if (s.startsWith("[")) {
    try {
      const arr = JSON.parse(s) as unknown;
      if (Array.isArray(arr)) {
        for (const item of arr) {
          const u = String(item).trim();
          if (/^https?:\/\//i.test(u)) return u;
        }
      }
    } catch {
      /* ignore malformed JSON */
    }
  }
  const first = s.split(/[,;]/)[0]?.trim().replace(/^[\["']+|[\]"']+$/g, "");
  if (first && /^https?:\/\//i.test(first)) return first;
  return null;
}

export type Verdict = "desert" | "blind" | "served" | "unknown";
export type SortKey = "priority" | "risk" | "conf" | "az";
export type TabKey = "map" | "quad";
export type Grain = "state" | "district" | "pin";

export interface Capability {
  id: string;
  label: string;
  dot: string;
  coverage: number;
}

export interface Summary {
  desert: number;
  blind: number;
  served: number;
  unknown: number;
}

export interface Unit {
  unit_key: string;
  name: string;
  sub: string;
  risk: number;
  conf: number;
  verdict: Verdict;
  base_verdict?: Verdict;
  overridden?: boolean;
  watched: boolean;
  hasNote: boolean;
  n_facilities: number;
  priority: number;
  state?: string;
}

export interface NeedDriver {
  label: string;
  value: number | null;
  direction: string;
}

export interface EvidenceItem {
  facility: string;
  quote: string;
  tier: string;
  source_field: string;
  rec_id: string;
  source_url?: string | null;
  source: string;
}

export interface UnitDetail {
  unit_key: string;
  name: string;
  sub: string;
  risk: number;
  conf: number;
  verdict: Verdict;
  base_verdict: Verdict;
  overridden: boolean;
  supply: {
    strong: number;
    partial: number;
    weak: number;
    n: number;
  };
  need: {
    index: number | null;
    signal_strength: string | null;
    drivers: NeedDriver[];
    nfhs_matched: boolean;
  };
  evidence: EvidenceItem[];
  note: string;
  watched: boolean;
}

export interface GeoFeature {
  unit_key: string;
  state: string;
  district?: string | null;
  pin3?: string | null;
  name?: string;
  risk: number;
  conf: number;
  verdict: Verdict;
}

export interface Scenario {
  name: string;
  cap: string;
  grain: Grain;
  overlay: boolean;
  sort: SortKey;
}

export interface ExportRegion {
  name: string;
  sub: string;
  risk: number;
  conf: number;
  verdict: Verdict;
  action: string;
  note: string;
  citations?: Array<{
    facility: string;
    quote: string;
    rec_id: string;
    source: string;
  }>;
}

export interface ExportPayload {
  capability: string;
  regions: ExportRegion[];
}

export interface AskResponse {
  answer?: string;
  sql?: string;
  rows?: unknown[];
  error?: string;
}

export interface VerificationPlanResponse {
  plan?: string;
  sections?: unknown;
  error?: string;
}

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(err || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchCapabilities(): Promise<Capability[]> {
  return request("/api/capabilities");
}

export function fetchSummary(cap: string, grain: Grain): Promise<Summary> {
  return request(`/api/summary?cap=${encodeURIComponent(cap)}&grain=${encodeURIComponent(grain)}`);
}

export function fetchUnits(
  cap: string,
  grain: Grain,
  opts?: { q?: string; state?: string },
): Promise<Unit[]> {
  const params = new URLSearchParams({ cap, grain });
  if (opts?.q) params.set("q", opts.q);
  if (opts?.state) params.set("state", opts.state);
  return request(`/api/units?${params}`);
}

export function fetchUnitDetail(cap: string, unitKey: string): Promise<UnitDetail> {
  return request(
    `/api/unit?cap=${encodeURIComponent(cap)}&unit_key=${encodeURIComponent(unitKey)}`,
  );
}

export function fetchGeo(cap: string, grain: Grain): Promise<GeoFeature[]> {
  return request(`/api/geo?cap=${encodeURIComponent(cap)}&grain=${encodeURIComponent(grain)}`);
}

export function setWatch(unitKey: string, cap: string, on: boolean): Promise<{ ok: boolean }> {
  return request("/api/watch", {
    method: "POST",
    body: JSON.stringify({ unit_key: unitKey, cap, on }),
  });
}

export function saveNote(unitKey: string, cap: string, note: string): Promise<{ ok: boolean }> {
  return request("/api/note", {
    method: "PUT",
    body: JSON.stringify({ unit_key: unitKey, cap, note }),
  });
}

export function setOverride(
  unitKey: string,
  cap: string,
  verdict: Verdict | null,
): Promise<{ ok: boolean }> {
  return request("/api/override", {
    method: "PUT",
    body: JSON.stringify({ unit_key: unitKey, cap, verdict }),
  });
}

export function fetchScenarios(): Promise<Scenario[]> {
  return request("/api/scenarios");
}

export function saveScenario(scenario: Scenario): Promise<{ ok: boolean }> {
  return request("/api/scenario", {
    method: "POST",
    body: JSON.stringify(scenario),
  });
}

export function deleteScenario(name: string): Promise<{ ok: boolean }> {
  return request(`/api/scenario/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function fetchExport(cap: string): Promise<ExportPayload> {
  return request(`/api/export?cap=${encodeURIComponent(cap)}`);
}

export function askQuestion(question: string): Promise<AskResponse> {
  return request("/api/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function generateVerificationPlan(
  unitKeys: string[],
  cap: string,
): Promise<VerificationPlanResponse> {
  return request("/api/verification-plan", {
    method: "POST",
    body: JSON.stringify({ unit_keys: unitKeys, cap }),
  });
}

export const CAP_DOTS: Record<string, string> = {
  icu: "#d23f2d",
  maternity: "#7c4dd6",
  emergency: "#e0732b",
  oncology: "#2f9e6b",
  trauma: "#d6452f",
  nicu: "#3d8bd6",
  dialysis: "#1f9e9e",
};

export function extractStateFromUnit(unit: Unit): string {
  if (unit.sub.includes("·")) {
    const parts = unit.sub.split("·");
    return parts[parts.length - 1].trim();
  }
  if (unit.sub.toLowerCase().includes("state")) return unit.name;
  const keyParts = unit.unit_key.split("|");
  if (keyParts.length > 1) return keyParts[keyParts.length - 1];
  if (unit.unit_key.startsWith("state:")) return unit.unit_key.slice(6);
  return unit.name;
}

export function extractDistrictFromUnit(unit: Unit): string | null {
  if (unit.unit_key.startsWith("district:")) {
    return unit.unit_key.split(":")[1]?.split("|")[0] ?? unit.name;
  }
  if (unit.unit_key.startsWith("pin:")) {
    const namePart = unit.name.split("·")[1]?.trim();
    return namePart ?? null;
  }
  return unit.name;
}
