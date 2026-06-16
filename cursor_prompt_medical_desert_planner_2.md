# Cursor build brief — CareLens AI · Medical Desert Planner (Track 2)

You are building a **Databricks App** for the Databricks Apps & Agents Hackathon for Good, Track 2 (Medical Desert Planner). Build it end to end: a Lakeflow declarative (medallion) pipeline in Unity Catalog, Gold serving tables, a FastAPI backend, a Lakebase (Postgres) state store, AI/BI Genie + an Agent Bricks agent, and a Next.js UI — all hosted as one Databricks App on **Free Edition**.

Read this whole brief before writing code. Build in the phase order at the end. Do not invent data, rules, citations, or metrics. Every score must trace to a real record.

---

## 0. Non-negotiable principles

1. **Scoring is deterministic; the LLM is only at the edges.** Risk, confidence, verdict, and citations are computed in the pipeline (reproducible, auditable, traceable to record IDs). Genie and the Agent are used only for natural-language Q&A and for drafting verification plans / export narratives. Never let an LLM produce a risk/confidence/verdict number.
2. **Two-axis honesty.** A unit is a **confirmed desert** only when `risk >= 58 AND confidence >= 58`. High risk on thin data is a **blind spot**, not a desert. Never relabel a blind spot as a desert anywhere in the stack.
3. **Cite both sides.** Every important number traces to supply evidence (facility record IDs) and, where it exists, need evidence (NFHS-5 district indicators). The detail panel shows both.
4. **Communicate uncertainty.** Low-confidence units are visually hatched and gated to blind-spot/unverified. Capabilities with no need signal (ICU, trauma) bias toward blind-spot/unverified by construction — surface a "no direct need indicator" note rather than fabricating need.
5. **Persist user actions** (watchlist, notes, overrides, scenarios) in Lakebase, not localStorage.

---

## 1. Tech stack & hosting

- **Pipeline:** Lakeflow Declarative Pipeline (DLT) — Python, medallion (Bronze → Silver → Gold), registered in Unity Catalog.
- **Serving DB reads:** Databricks SQL connector against Gold tables via a SQL warehouse.
- **State store:** Lakebase (Postgres-compatible) via `psycopg`.
- **Backend:** FastAPI (Python 3.11).
- **AI:** AI/BI Genie space over Gold + an Agent Bricks "Care-Gap Analyst" agent (OpenAI-backed; vector index over Silver facility text).
- **Frontend:** Next.js (App Router) with `output: 'export'` (fully static SPA — no server components, no server actions). Client-side D3 for the India map.
- **Hosting:** One Databricks App. Build Next to static, serve it from FastAPI `StaticFiles`; FastAPI also serves `/api/*`. Single process, single `app.yaml` command.
- **Identity:** Use the Databricks Apps user identity (forwarded headers / OBO) as `planner_id` for Lakebase rows and for UC access.

---

## 2. Data sources (Unity Catalog)

Catalog/schema: `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset`

**`facilities`** (10k rows, all columns `string` unless noted). Key columns to use:
- Identity/geo: `unique_id`, `name`, `address_zipOrPostcode`, `address_stateOrRegion`, `address_city`, `address_country`, `address_countryCode`, `countries`, `latitude` (double), `longitude` (double), `cluster_id`
- Evidence (claims to verify): `description`, `capability`, `procedure`, `equipment`, `specialties`, `numberDoctors`, `capacity`, `yearEstablished`, `area`
- Source/credibility meta: `source_types`, `source_ids`, `source_urls`, `source`, `recency_of_page_update`, `distinct_social_media_presence_count`, `affiliated_staff_presence`, `custom_logo_presence`, `number_of_facts_about_the_organization`, `post_metrics_post_count`, `engagement_metrics_n_followers`, `officialWebsite`, `officialPhone`

**`india_post_pincode_directory`** — authoritative PIN crosswalk: `pincode` (bigint), `district`, `statename`, `divisionname`, `latitude` (string), `longitude` (string), `officetype`, `delivery`.

**`nfhs_5_district_health_indicators`** — district need signal: `district_name`, `state_ut`, `households_surveyed` (double), plus ~100 `*_pct` indicators (many typed `string` — must `try_cast` to double; unparseable → null). Columns used by the capability mapping are listed in §5.

---

## 3. Capabilities (7) and lexicons

Capability IDs and display labels (keep order; used in left rail):
`icu`→ICU, `maternity`→Maternity, `emergency`→Emergency, `oncology`→Oncology, `trauma`→Trauma, `nicu`→NICU, `dialysis`→Dialysis.

Match these lexicons (case-insensitive, word-boundary; store in `pipeline/lexicons.py`) against `capability`, `procedure`, `equipment`, `specialties`, `description`:

```python
LEXICONS = {
  "icu":       ["icu", "intensive care", "ventilator", "critical care", "multipara monitor", "hdu", "high dependency"],
  "maternity": ["maternity", "labour room", "labor room", "c-section", "caesarean", "cesarean", "obstetric", "antenatal", "delivery", "ob/gyn", "gynaec", "lscs"],
  "emergency": ["emergency", "casualty", "trauma triage", "ambulance", "24x7", "24/7", "round-the-clock", "accident & emergency", "a&e"],
  "oncology":  ["oncology", "cancer", "chemotherapy", "chemo", "radiotherapy", "palliative", "tumor", "tumour", "oncologist"],
  "trauma":    ["trauma", "orthopaedic", "orthopedic", "fracture", "accident wing", "ortho", "trauma centre", "trauma center"],
  "nicu":      ["nicu", "neonatal", "newborn care", "sncu", "phototherapy", "warmer", "neonatal ventilation"],
  "dialysis":  ["dialysis", "haemodialysis", "hemodialysis", "nephrology", "renal", "pmndp", "kidney"],
}
```

---

## 4. Pipeline (Lakeflow DLT) — Bronze / Silver / Gold

Use `import dlt` decorators (`@dlt.table`, `@dlt.expect_or_drop`, `@dlt.expect`). (May be swapped to the `from pyspark import pipelines as dp` / `@dp.table()` SDP form if you prefer; logic identical.) All tables land in the schema above.

### Bronze (`pipeline/bronze.py`) — typed, filtered, deduped snapshots
- `bronze_facilities`: read `facilities`; filter to India (`address_countryCode = 'IN'` OR `lower(countries) like '%india%'`); keep all columns; add `ingest_ts`. Add `is_cluster_primary` boolean: within each `cluster_id`, pick one representative (most-recent `recency_of_page_update`, tie-break highest `number_of_facts_about_the_organization`). Keep all rows but flag; counting uses primaries only.
- `bronze_pincodes`: read `india_post_pincode_directory`; cast lat/long to double.
- `bronze_nfhs`: read `nfhs_5_district_health_indicators` as-is.
- Expectations: `@dlt.expect("has_id", "unique_id IS NOT NULL")`, `@dlt.expect("has_name", "name IS NOT NULL")`.

### Silver (`pipeline/silver.py`)
- **`silver_geo_dim`** (`pipeline/geo_crosswalk.py`): canonical district dimension.
  - From `bronze_pincodes`: distinct `(pincode, district, statename, latitude, longitude)`; build `pin3 = lpad(substr(cast(pincode as string),1,3),3,'0')` for PIN-zone grain.
  - Build a normalized key: `geo_key = regexp_replace(lower(trim(name)), '[^a-z]', '')` after stripping the word "district".
  - Fuzzy-join NFHS `(district_name, state_ut)` to pincode `(district, statename)` on normalized key with a Levenshtein/Jaro fallback (threshold ~0.9). Output `district_canonical`, `state_canonical`, `nfhs_matched` (bool). **Unmatched NFHS or pincode districts are kept and flagged, never dropped.**
- **`silver_facility`**: one row per facility (primaries). Resolve geography: join `address_zipOrPostcode` (digits only, first 6) to `bronze_pincodes.pincode` → `district_resolved`, `state_resolved`, `pin3`. Fallback when postcode missing/invalid: `address_stateOrRegion` for state, `district_resolved = null` (flag `geo_source = 'state_only'`). Carry credibility meta columns. Add `geo_resolved` bool.
- **`silver_facility_capability_evidence`**: explode facility × 7 capabilities (only emit rows where tier != none). For each:
  - `matched_fields`: which of {capability, procedure, equipment, specialties, description} contain a lexicon hit.
  - `tier`:
    - `strong` if hit in ≥2 of {capability, procedure, equipment, specialties}, OR hit in ≥1 of those + quantitative backing (`capacity` or `numberDoctors` parse to a number > 0).
    - `partial` if hit in exactly 1 of {capability, procedure, equipment, specialties}.
    - `weak` if hit only in `description`.
  - `matched_span`: the first sentence/phrase (≤160 chars) containing the hit, from the highest-priority matched field (priority: capability > procedure > equipment > specialties > description).
  - `source_field`: that field name. `rec_id = unique_id`.
  - Expectation: drop rows with empty `matched_span`.
- **`silver_need_indicators`**: from `bronze_nfhs`, `try_cast` every mapped `*_pct` column (§5) to double; join to `silver_geo_dim` to attach `district_canonical`, `state_canonical`. Add `need_data_density = households_surveyed` (normalized later) and per-indicator non-null flags.

### Gold (`pipeline/gold.py`)
Materialize for all three grains: `state`, `district`, `pin`. Grain key conventions: state → `state`; district → `district_canonical | state_canonical`; pin → `pin3 + 'xxx' | state`.

- **`gold_geo_capability`** — one row per `(grain, unit_key, unit_name, sub, capability)` with: `risk` (int 6–97), `confidence` (int 8–96), `verdict` (`desert|blind|served|unknown`), `n_facilities`, `strong_count`, `partial_count`, `weak_count`, `supply_index`, `need_index` (nullable), `need_signal_strength` (`strong|moderate|weak|none`), `nfhs_matched` bool, plus the top driving NFHS indicators as a struct/array (`need_drivers: [{label, value, direction}]`). Compute per §6.
- **`gold_evidence_citations`** — top-k (k=6) cited facility spans per `(grain, unit_key, capability)`, ordered strong→partial→weak: `facility_name`, `matched_span` (quote), `tier`, `source_field`, `rec_id`, `source_url` (from `source_urls` first URL if present).

Persist Gold as Delta in UC. The verdict in Gold is the **base** verdict; analyst overrides from Lakebase are applied at read time in the API (§8), not baked into Gold.

---

## 5. Capability → NFHS-5 need mapping (SIGNED OFF — implement exactly)

Store in `pipeline/config.py` as `NEED_MAP`. Each indicator has a direction: `lower_is_worse` (low % = more need) or `higher_is_worse` (high % = more need). `try_cast` all; null indicators are skipped and reduce confidence.

| Capability | NFHS columns | Direction | Signal |
|---|---|---|---|
| maternity | `institutional_birth_5y_pct`, `institutional_birth_in_public_facility_5y_pct`, `mothers_who_had_at_least_4_anc_visits_lb5y_pct`, `births_attended_by_skilled_hp_5y_10_pct` | lower_is_worse | strong |
| | `average_out_of_pocket_expenditure_per_delivery_in_a_public_fac` | higher_is_worse | |
| nicu | `institutional_birth_in_public_facility_5y_pct`, `mothers_whose_last_birth_was_protected_against_neo_tetanus_pct`, `children_who_received_pnc_from_a_doctor_nurse_lhv_anm_midwi_pct` | lower_is_worse | strong |
| oncology | `women_age_30_49_years_ever_undergone_a_cervical_screen_pct`, `women_age_30_49_years_ever_undergone_a_breast_exam_pct`, `women_age_30_49_years_ever_undergone_an_oral_cancer_exam_pct` | lower_is_worse | moderate |
| | `w15_plus_who_use_any_kind_of_tobacco_pct`, `m15_plus_who_use_any_kind_of_tobacco_pct`, `w15_plus_who_consume_alcohol_pct`, `m15_plus_who_consume_alcohol_pct` | higher_is_worse | |
| dialysis | `w15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct`, `m15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct`, `w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct`, `m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct` | higher_is_worse | moderate |
| emergency | `children_with_fever_or_symptoms_of_ari_2wk_taken_to_a_healt_pct`, `children_with_diarrhoea_2wk_taken_to_a_health_facility_or_h_pct` | lower_is_worse | weak |
| icu | `w15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct`, `m15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct`, `w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct`, `m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct` | higher_is_worse | weak |
| trauma | *(none — no NFHS indicator)* | — | none |

---

## 6. Scoring formulas (deterministic — implement exactly)

Helper: `winsor_minmax(x, lo_p=5, hi_p=95)` = clip to 5th/95th percentile across units **within the current grain**, then min-max to 0–100.

**Need index** (per unit, capability), only for district grain natively; roll up to state weighted by `households_surveyed`; for PIN grain reuse the parent district's need:
- For each mapped indicator, normalize to a 0–100 *need* score: `lower_is_worse` → `100 - winsor_minmax(value)`; `higher_is_worse` → `winsor_minmax(value)`.
- `need_index = mean(available indicator need scores)`. If all null → `need_index = null`, `need_signal_strength` from table (or `none`).

**Supply index** (per unit, capability):
- `supply_raw = Σ over facilities in unit (strong=1.0, partial=0.5, weak=0.15)`.
- `supply_index = winsor_minmax(supply_raw)` across units in grain.
- `supply_deficit = 100 - supply_index`.

**Risk** (per unit, capability):
- If `need_index` is not null: `risk = 0.6*need_index + 0.4*supply_deficit`.
- If `need_index` is null (trauma; or unmatched district): `risk = supply_deficit`.
- `risk = round(clip(risk, 6, 97))`.

**Confidence** (per unit, capability), weighted mean of 0–100 sub-signals → `round(clip(·, 8, 96))`:
- `evidence_strength` (35%): share of unit facilities at strong/partial tier, scaled 0–100.
- `meta_credibility` (25%): per-facility mean of normalized `recency_of_page_update` (recent=high), count of distinct `source_types`/`source_urls`, `affiliated_staff_presence`, `number_of_facts_about_the_organization`, social presence; averaged over unit facilities.
- `need_data_density` (20%): `winsor_minmax(households_surveyed)` × `nfhs_matched`; 0 if unmatched.
- `n_facilities` (10%): `min(100, 100 * log10(1+n)/log10(1+25))`.
- `capability_signal` (10%): strong=100, moderate=70, weak=40, none=15 (from `need_signal_strength`).

**Verdict** (T = 58; identical to the mockup):
- `risk>=58 & conf>=58` → `desert`; `risk>=58 & conf<58` → `blind`; `risk<58 & conf>=58` → `served`; else `unknown`.

**Priority** (for ranked-list default sort): `risk * (desert:2.1, blind:1.5, served:0.7, unknown:1.0)`.

---

## 7. Lakebase schema (`lakebase/schema.sql`)

`unit_key` format: `state:Bihar` | `district:Araria|Bihar` | `pin:854xxx|Bihar`.

```sql
create table if not exists planner_watch (
  planner_id text, unit_key text, capability text, created_at timestamptz default now(),
  primary key (planner_id, unit_key, capability));
create table if not exists planner_notes (
  planner_id text, unit_key text, capability text, note text, updated_at timestamptz default now(),
  primary key (planner_id, unit_key, capability));
create table if not exists planner_overrides (
  planner_id text, unit_key text, capability text,
  verdict text check (verdict in ('desert','blind','served','unknown')),
  updated_at timestamptz default now(),
  primary key (planner_id, unit_key, capability));
create table if not exists planner_scenarios (
  planner_id text, name text, cap text, grain text, overlay boolean, sort text,
  created_at timestamptz default now(), primary key (planner_id, name));
```

---

## 8. FastAPI backend (`app/backend/`)

`main.py` mounts `/api` and serves the Next static export at `/`. `gold_reads.py` (SQL warehouse), `lakebase.py` (psycopg), `genie.py`, `agent.py`, `models.py` (pydantic).

Endpoints:
- `GET /api/capabilities` → 7 caps, each with a computed `coverage` figure = share of India facilities with ≥1 matched claim for that capability (replaces the prototype's hardcoded `cov` like `0.61`; rendered as the mono figure in the left rail).
- `GET /api/summary?cap&grain&scenario` → `{desert, blind, served, unknown}` counts (overrides applied).
- `GET /api/units?cap&grain&sort&q&state` → ranked `[{unit_key,name,sub,risk,conf,verdict,watched,hasNote,n_facilities}]` (`n_facilities` drives quadrant dot radius — see §10).
- `GET /api/unit?cap&unit_key` → detail: `risk, conf, verdict, base_verdict, overridden, supply:{strong,partial,weak,n}, need:{index, signal_strength, drivers:[{label,value,direction}]}, evidence:[{facility,quote,tier,source_field,rec_id,source_url}], note, watched`.
- `GET /api/geo?grain&cap` → `[{state, district?, pin3?, risk, conf, verdict}]` for choropleth fill + hatch.
- `POST /api/watch` `{unit_key,cap,on}`; `PUT /api/note` `{unit_key,cap,note}`; `PUT /api/override` `{unit_key,cap,verdict|null}`.
- `GET /api/scenarios`; `POST /api/scenario`; `DELETE /api/scenario/{name}`.
- `POST /api/ask` `{question}` → Genie (returns answer + the SQL/rows it grounded on).
- `POST /api/verification-plan` `{unit_keys[]}` → Agent (returns cited plan).
- `GET /api/export?scenario` → export payload for watched units (per-unit recommended action + citations).
- `GET /healthz`.

Read-time override: when serving units/summary/unit, overlay `planner_overrides` onto the Gold base verdict. Cache Gold reads in-process (TTL ~5 min) — Free Edition warehouse is small.

---

## 9. AI layer

**Genie** (`genie/space_config.md`): a Genie space over `gold_geo_capability` and `gold_evidence_citations`. Document table semantics, the verdict definitions, and that "strong evidence" = `strong_count`. `/api/ask` proxies to it. Example asks to validate: "worst ICU gaps in Bihar with strong evidence", "districts that are blind spots for maternity".

**Agent Bricks "Care-Gap Analyst"** (`agent/care_gap_analyst.md`): grounded on (a) Gold via a SQL/Genie tool and (b) a vector index over `silver_facility` text (`description`, `matched_span`s). OpenAI-backed via `OPENAI_API_KEY` / `OPENAI_BASE_URL` read from env (never hard-coded). Sole jobs: draft a **field verification plan** for selected blind spots and write the **export narrative**. Hard system rule: cite `rec_id`s and NFHS indicators, or state "insufficient evidence" — never invent. It must never output risk/confidence/verdict numbers; it reads them from Gold.

---

## 10. Frontend (`app/frontend/`) — port the mockup, rewire to the API

The uploaded mockup `Medical_Desert_Planner_dc.html` is the **design source of truth**. Reproduce its layout, CSS variables/tokens, verdict colors/labels, thresholds, light/dark theme, and all interactions in Next.js + React. **Remove the synthetic engine entirely** (`_hash`, `_rand`, `_metrics`, `_verdict` synthetic data, fabricated evidence). Every number comes from the API.

Preserve exactly:
- Verdict meta (colors/labels): desert `#d23f2d` "Confirmed desert", blind `#e0a32b` "Blind spot", served `#2f9e6b` "Adequately served", unknown `#9aa0ad` "Unverified". Threshold 58. Risk color ramp (the `oklch` interpolation) and the hatch overlay for `conf < 55`.
- Left rail: capability selector (7), grain toggle (State/District/PIN), uncertainty overlay toggle, verdict legend + the callout text about deserts vs blind spots.
- Center: summary band (4 counts), Map / Risk×Confidence quadrant tabs, D3 India choropleth (load India GeoJSON from the same CDN the mockup uses; the no-boundary fallback message stays).
- Right: ranked list (sorts: Priority/Risk/Low conf/A–Z) and the selected-unit detail panel — but the detail panel now shows **both** supply citations (facility quotes + rec_id) **and** need drivers (NFHS indicators), the strong/partial/weak breakdown, analyst override buttons, planner note, watchlist toggle.
- Modals: Export plan (now calls `/api/export`, with an "Generate verification plan" button hitting the Agent) and Scenarios (save/apply/delete via API).
- A search/ask box wired to `/api/ask` (Genie) for natural-language Q&A.

State (watch/notes/overrides/scenarios/theme) goes through the API to Lakebase, not localStorage. Keep theme in localStorage only as a UI nicety.

### 10.1 Production deltas from the handoff README (close these gaps the prototype faked)

The handoff `README.md` is high-fidelity on visuals but the prototype synthesizes data. Implement these production-specific decisions:

- **Desktop-only.** Reproduce as-is: full viewport, `min-width: 1340px`, `100vh`, no page scroll (internal panels scroll). Do **not** build responsive/mobile layouts — it's an analyst tool.
- **Server vs client params.** Only `cap` and `grain` trigger an API refetch. `overlay` (hatch where `conf < 55`) and `sort` (priority/risk/low-conf/A–Z) are pure client-side transforms over already-fetched units — never refetch on those. This keeps the snappy feel of the prototype.
- **Quadrant dot radius** encodes a real quantity now: `r = clamp(6, 20, sqrt(n_facilities) * k)` (districts/PIN included), not population. Keep axes (X = data confidence →, Y = care-gap risk ↑), the dashed 58 threshold grid lines, the four tinted/labeled quadrants, and text labels for watched or top-priority units. ViewBox 760×460.
- **Citation source string** keeps the prototype's shape `rec_<id> · <capability>/<field>` but is populated from real provenance: `rec_id = unique_id`, `<field> = source_field` from `gold_evidence_citations`. Render the facility's `source_url` as a link when present.
- **Override warn/reset banner** stays: when a unit's verdict is overridden, show the `--warn-*` banner with a "reset to model" action (clears the Lakebase override → reverts to Gold `base_verdict`).
- **Export modal** keeps the "Print / save PDF" button (`window.print()`) **and** adds a "Generate verification plan" button that calls `/api/verification-plan` (Agent). `/api/export` supplies the per-unit recommended action + citations; the print stylesheet must render the plan cleanly.
- **No-evidence / no-need states** must render honestly: a unit with zero matched facilities for the capability shows "no claims found" (not a fabricated count); a unit whose district didn't match NFHS shows "need signal unavailable" in the detail panel instead of a need number.

---

## 11. Hosting (`app/app.yaml`, `README.md`)

**Deployment target & hard constraints:**
- Deploy workspace: `https://dbc-d7535c0c-012b.cloud.databricks.com/`. Deploy via Databricks Asset Bundles / `databricks apps deploy` against this workspace.
- **Do not use Streamlit** anywhere. The UI is a real Next.js (React) frontend; the backend is FastAPI. No Gradio/Dash either.
- One Databricks App, single process: FastAPI serves `/api/*` and the static Next export.
- **Secrets, never hard-coded:** OpenAI key as `OPENAI_API_KEY` (base URL `https://api.openai.com/v1`), plus SQL warehouse ID, Lakebase connection string, Genie space ID, Agent endpoint. Read all from env / Databricks App resources. The Agent layer is the only consumer of `OPENAI_API_KEY`. If the repo is committed/submitted, ensure no secret value appears in any file — reference by name only.

- Build: `cd frontend && npm ci && npm run build` (Next `output:'export'` → `frontend/out`).
- Runtime: FastAPI serves `/api/*` and mounts `frontend/out` at `/` via `StaticFiles(html=True)`.
- `app.yaml` command: `uvicorn backend.main:app --host 0.0.0.0 --port $DATABRICKS_APP_PORT`.
- Env: SQL warehouse ID, Lakebase connection, Genie space ID, Agent endpoint, `OPENAI_API_KEY` (+ `OPENAI_BASE_URL=https://api.openai.com/v1`) — via Databricks App resources/secrets, never hard-coded.
- Confirm everything used is available on **Free Edition**; if a feature isn't, note it in the README and degrade gracefully (e.g., if Agent endpoint is unavailable, `/api/verification-plan` returns a deterministic template with citations rather than failing).

---

## 12. Build order (phases)

1. **Pipeline**: bronze → geo_crosswalk → silver → gold. Validate counts; spot-check 5 facilities' tiers and spans by hand. Confirm trauma/ICU bias to blind/unknown.
2. **Lakebase**: schema + a thin data-access module; smoke-test CRUD.
3. **FastAPI**: Gold reads + state endpoints + override overlay. Verify `/api/units`, `/api/unit`, `/api/geo`, `/api/summary` against the pipeline numbers.
4. **Frontend**: port mockup, wire to API, kill synthetic engine.
5. **Genie**: space + `/api/ask`.
6. **Agent**: Care-Gap Analyst + `/api/verification-plan` + export narrative.
7. **Package** as Databricks App; deploy; rehearse the 3-minute demo (Genie ask → drill into a blind spot → generate verification plan → export).

---

## 13. Acceptance criteria

- No synthetic/random numbers anywhere; grep the frontend for `Math.random`/hash scoring and confirm removed.
- For any selected unit, the detail panel shows ≥1 real facility citation (with `rec_id`) for non-empty supply, and the NFHS drivers when `nfhs_matched`.
- No unit is `desert` unless `risk>=58 && conf>=58`. Trauma never shows `desert` (need_index null). ICU rarely does.
- Unmatched districts render with low confidence and a visible "need signal unavailable" note — never a fabricated need value.
- Watch/note/override/scenario persist across reloads (Lakebase) and across browsers for the same planner identity.
- Genie answers cite Gold rows; Agent plans cite `rec_id`s/indicators or say "insufficient evidence".
- App runs live on Free Edition; map fallback works offline; `/healthz` returns ok.

---

## 14. Data-Readiness bonus (cheap ambition, optional)

Surface a small "Data readiness" panel from the DLT expectation results + crosswalk flags: % facilities geo-resolved, % NFHS districts matched, sparse-field coverage, and `cluster_id` duplicate counts. It reuses pipeline outputs and strengthens the honesty story for judges.
