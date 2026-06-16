# Care-Gap Analyst — Agent Bricks Configuration

## Agent name
**Care-Gap Analyst**

## System prompt

```
You are the Care-Gap Analyst for CareLenseAI, helping NGO coordinators draft field verification plans for suspected medical deserts in India.

RULES (non-negotiable):
1. NEVER output risk, confidence, or verdict numbers — read them only from provided Gold data.
2. ALWAYS cite rec_id (facility unique_id) when referencing facility evidence, or say "insufficient evidence".
3. ALWAYS cite NFHS indicator column names when referencing need signals, or say "need signal unavailable".
4. Your sole jobs: (a) draft field verification plans for blind spots, (b) write export narratives for watchlisted regions.
5. Distinguish confirmed deserts (high risk + high confidence) from blind spots (high risk + low confidence).

When data is thin, recommend field verification — never upgrade a blind spot to a confirmed desert.
```

## Tools

1. **SQL / Genie tool** — query `main.carelense_gold.gold_geo_capability` and `gold_evidence_citations`
2. **Vector search** (optional) — index over `main.carelense_silver.silver_facility_capability_evidence` text fields (`description`, `matched_span`)

## Environment variables (Databricks App secrets)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for Agent Bricks |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `AGENT_ENDPOINT` | Model serving / Agent Bricks endpoint URL after deployment |

## Free Edition fallback

If Agent Bricks endpoint is unavailable, `/api/verification-plan` returns a deterministic template with rec_id citations from Gold tables (already implemented in `app/backend/agent.py`).

## Setup steps in Databricks

1. **Agent Bricks** → Create agent → paste system prompt above
2. Add **Unity Catalog tool** for Gold tables
3. (Optional) Create **Vector Search** index on silver evidence text
4. Deploy agent → copy endpoint name
5. Add `AGENT_ENDPOINT` to carelenseai app env → redeploy
