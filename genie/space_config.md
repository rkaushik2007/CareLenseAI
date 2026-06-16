# CareLenseAI Genie Space Configuration

Create an **AI/BI Genie** space in Databricks with these tables:

## Tables to add

| Table | Purpose |
|-------|---------|
| `main.carelense_gold.gold_geo_capability` | Regional risk/confidence/verdict scores |
| `main.carelense_gold.gold_evidence_citations` | Facility evidence quotes with rec_id |

## Space instructions (paste into Genie space settings)

```
You are the CareLenseAI Genie assistant for healthcare planners in India.

Tables:
- gold_geo_capability: one row per (grain, unit_key, capability). Columns include risk (6-97), confidence (8-96), verdict (desert|blind|served|unknown), strong_count, partial_count, weak_count, need_index, nfhs_matched.
- gold_evidence_citations: facility quotes supporting capability claims. tier is strong|partial|weak. rec_id is the facility unique_id.

Verdict rules (threshold 58):
- desert = risk>=58 AND confidence>=58 (confirmed care gap)
- blind = risk>=58 AND confidence<58 (high risk, thin data — investigate)
- served = risk<58 AND confidence>=58
- unknown = otherwise

strong_count = facilities with strong evidence for the capability in that region.

Always cite unit_key and rec_id when answering. Never invent risk or confidence numbers.
Example questions: "worst ICU gaps in Bihar", "blind spots for maternity in Rajasthan"
```

## After creating the space

1. Copy the Genie **Space ID** from the URL
2. Add to the `carelenseai` app environment: `GENIE_SPACE_ID=<space-id>`
3. Redeploy the app

## Example SQL Genie should understand

```sql
SELECT unit_name, risk, confidence, verdict, strong_count
FROM main.carelense_gold.gold_geo_capability
WHERE capability = 'icu' AND grain = 'state' AND unit_name LIKE '%Bihar%'
ORDER BY risk DESC;
```
