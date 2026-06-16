"""Genie proxy for natural-language Q&A over Gold tables."""

from __future__ import annotations

import os
import re
import time
import urllib.error
from typing import Any

from pipeline.lexicons import CAPABILITIES

_INDIAN_STATES = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "puducherry", "chandigarh",
)


class GenieAuthError(Exception):
    def __init__(self, code: int, message: str = "") -> None:
        self.code = code
        super().__init__(message or f"Genie auth error {code}")


def ask_genie(question: str) -> dict[str, Any]:
    pin = _parse_pin(question)
    if pin:
        pin_answer = _gold_pin_answer(question, pin)
        if pin_answer:
            return pin_answer

    space_id = os.getenv("GENIE_SPACE_ID", "")
    if not space_id:
        return _gold_fallback_answer(question) or _fallback_answer(question)

    auth_failed = False
    last_exc: Exception | None = None

    try:
        return _ask_genie_sdk(space_id, question)
    except Exception as exc:
        last_exc = exc
        if _is_auth_or_forbidden(exc):
            auth_failed = True
        else:
            try:
                return _ask_genie_rest(space_id, question)
            except Exception as exc2:
                last_exc = exc2
                if _is_auth_or_forbidden(exc2):
                    auth_failed = True

    if auth_failed:
        fb = _gold_fallback_answer(question)
        if fb:
            return fb

    if last_exc is not None:
        fb = _gold_fallback_answer(question)
        if fb:
            return {
                **fb,
                "answer": f"Genie unavailable ({last_exc}). {fb['answer']}",
            }
        fb = _fallback_answer(question)
        return {
            "answer": f"Genie unavailable ({last_exc}). {fb['answer']}",
            "sql": None,
            "rows": [],
        }

    return _fallback_answer(question)


def _is_auth_or_forbidden(exc: Exception) -> bool:
    if isinstance(exc, GenieAuthError):
        return True
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
        return True
    msg = str(exc).lower()
    if any(t in msg for t in ("401", "403", "unauthorized", "forbidden", "permission denied")):
        return True
    code = getattr(exc, "status_code", None)
    if code in (401, 403):
        return True
    return False


def _ask_genie_sdk(space_id: str, question: str) -> dict[str, Any]:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    genie = w.genie
    try:
        if hasattr(genie, "start_conversation_and_wait"):
            msg = genie.start_conversation_and_wait(space_id=space_id, content=question)
        elif hasattr(genie, "start_conversation"):
            waiter = genie.start_conversation(space_id=space_id, content=question)
            msg = waiter.result() if hasattr(waiter, "result") else waiter
        else:
            raise RuntimeError("Genie SDK missing start_conversation")
    except Exception as exc:
        if _is_auth_or_forbidden(exc):
            raise GenieAuthError(403, str(exc)) from exc
        raise

    return _format_genie_message(msg)


def _ask_genie_rest(space_id: str, question: str) -> dict[str, Any]:
    import json
    import urllib.request

    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    host = (w.config.host or "").rstrip("/")
    headers = {"Content-Type": "application/json", **w.config.authenticate()}

    def _api(method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{host}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                detail = err.read().decode("utf-8", errors="replace")[:300]
                raise GenieAuthError(err.code, detail) from err
            raise

    start = _api(
        "POST",
        f"/api/2.0/genie/spaces/{space_id}/start-conversation",
        {"content": question},
    )
    conversation_id = start.get("conversation_id") or start.get("conversation", {}).get("id")
    message_id = start.get("message_id") or start.get("id")
    if not conversation_id or not message_id:
        return _format_genie_message(start)

    msg: dict[str, Any] = {}
    for _ in range(40):
        msg = _api(
            "GET",
            f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}",
        )
        status = (msg.get("status") or "").upper()
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            return _format_genie_message(msg)
        time.sleep(2)

    return _format_genie_message(msg)


def _extract_text(val: Any) -> str:
    """Pull human-readable text from Genie SDK objects (e.g. TextAttachment)."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float, bool)):
        return str(val)
    if isinstance(val, dict):
        for key in ("text", "content", "description", "value", "message"):
            if val.get(key):
                extracted = _extract_text(val[key])
                if extracted:
                    return extracted
        return ""
    if isinstance(val, (list, tuple)):
        parts = [_extract_text(item) for item in val]
        return "\n\n".join(p for p in parts if p)
    for attr in ("text", "content", "description", "value", "message"):
        if hasattr(val, attr):
            inner = getattr(val, attr)
            if inner is not None and inner is not val:
                extracted = _extract_text(inner)
                if extracted:
                    return extracted
    return ""


def _format_genie_message(msg: Any) -> dict[str, Any]:
    if isinstance(msg, dict):
        d = msg
    else:
        d = {}
        for key in (
            "content",
            "status",
            "conversation_id",
            "attachments",
            "query",
            "description",
            "error",
        ):
            if hasattr(msg, key):
                d[key] = getattr(msg, key)

    answer_parts: list[str] = []
    sql = d.get("query") or d.get("sql")
    attachments = d.get("attachments") or []
    if isinstance(attachments, list):
        for att in attachments:
            text = _extract_text(att)
            if text:
                answer_parts.append(text)
            if isinstance(att, dict):
                q = att.get("query") or att.get("sql")
            else:
                q = getattr(att, "query", None) or getattr(att, "sql", None)
            if q and not sql:
                sql = q

    content = d.get("content") or d.get("description")
    content_text = _extract_text(content)
    if content_text:
        answer_parts.insert(0, content_text)

    answer = "\n\n".join(p for p in answer_parts if p).strip()
    if not answer:
        err = _extract_text(d.get("error"))
        answer = err or str(d.get("status") or "Genie returned no text.")

    return {"answer": answer, "sql": sql, "rows": []}


def _parse_pin(question: str) -> str | None:
    q = question.strip()
    if re.fullmatch(r"\d{6}", q):
        return q.zfill(6)
    m = re.search(r"\b(\d{6})\b", q)
    if m:
        return m.group(1).zfill(6)
    return None


def _gold_pin_answer(question: str, pin: str) -> dict[str, Any] | None:
    from app.backend import gold_reads

    cap = _parse_capability(question)
    pin3 = pin[:3].zfill(3)
    try:
        rows, sql = gold_reads.query_pin_gaps(pin, cap=cap)
    except Exception as exc:
        return {
            "answer": f"PIN lookup failed for {pin}: {exc}",
            "sql": None,
            "rows": [],
        }

    if not rows:
        return {
            "answer": (
                f"No care-gap data for PIN {pin} (zone {pin3}xxx). "
                "Gold aggregates by the first three PIN digits; try a nearby PIN or switch to District grain."
            ),
            "sql": sql,
            "rows": [],
        }

    states = sorted({(r.get("unit_key") or "").split("|")[-1] for r in rows if "|" in (r.get("unit_key") or "")})
    state_hint = f" in {', '.join(states)}" if states else ""
    lines = [
        f"Care-gap summary for PIN {pin} (zone {pin3}xxx{state_hint}, from Gold pipeline):",
    ]
    for r in rows:
        cap_id = (r.get("capability") or "?").upper()
        name = r.get("unit_name", "?")
        risk = int(r.get("risk", 0))
        conf = int(r.get("confidence", r.get("conf", 0)))
        verdict = r.get("verdict", "unknown")
        nf = r.get("n_facilities", "?")
        lines.append(
            f"• {cap_id}: {name} — risk {risk}, confidence {conf}, verdict {verdict}, facilities {nf}"
        )

    return {"answer": "\n".join(lines), "sql": sql, "rows": rows}


def _parse_capability(question: str) -> str | None:
    q = question.lower()
    for cap in CAPABILITIES:
        cid = cap["id"]
        label = cap.get("label", cid).lower()
        if cid in q or label in q:
            return cid
    return None


def _parse_state(question: str) -> str | None:
    q = question.lower()
    for state in sorted(_INDIAN_STATES, key=len, reverse=True):
        if state in q:
            return state.title()
    m = re.search(r"(?:in|for|across)\s+([A-Za-z][A-Za-z\s]{2,30})", question, re.I)
    if m:
        return m.group(1).strip().title()
    return None


def _parse_worst(question: str) -> bool:
    q = question.lower()
    if any(w in q for w in ("best", "lowest", "least", "served", "low risk")):
        return False
    return True


def _gold_fallback_answer(question: str) -> dict[str, Any] | None:
    cap = _parse_capability(question)
    state = _parse_state(question)
    if not cap:
        return None

    from app.backend import gold_reads

    worst = _parse_worst(question)
    state_filter = state or ""
    try:
        if state_filter:
            rows, sql = gold_reads.query_state_gaps(cap, state_filter, limit=5, worst=worst)
        else:
            sql = (
                f"SELECT unit_name, risk, confidence, verdict FROM gold_geo_capability "
                f"WHERE capability = '{cap}' AND grain = 'state' "
                f"ORDER BY risk {'DESC' if worst else 'ASC'} LIMIT 5"
            )
            rows = gold_reads.get_units(cap, "state")
            rows = sorted(rows, key=lambda r: int(r.get("risk", 0)), reverse=worst)[:5]
    except Exception as exc:
        return {
            "answer": f"Gold fallback query failed: {exc}",
            "sql": None,
            "rows": [],
        }

    if not rows:
        return {
            "answer": (
                f"No {cap.upper()} state rows matched"
                + (f" for {state_filter}" if state_filter else "")
                + ". Try another state or capability."
            ),
            "sql": sql if state_filter else None,
            "rows": [],
        }

    direction = "highest" if worst else "lowest"
    lines = [
        f"Top {len(rows)} {cap.upper()} care-gap units by {direction} risk"
        + (f" in {state_filter}" if state_filter else "")
        + " (from Gold pipeline, not LLM):",
    ]
    for i, r in enumerate(rows, 1):
        name = r.get("unit_name", r.get("name", "?"))
        risk = int(r.get("risk", 0))
        conf = int(r.get("confidence", r.get("conf", 0)))
        verdict = r.get("verdict", "unknown")
        lines.append(f"{i}. {name}: risk {risk}, confidence {conf}, verdict {verdict}")

    return {"answer": "\n".join(lines), "sql": sql, "rows": rows}


def _fallback_answer(question: str) -> dict[str, Any]:
    """Deterministic template when Genie space is not configured."""
    gold = _gold_fallback_answer(question)
    if gold:
        return gold

    q = question.lower()
    if "blind" in q or "thin" in q:
        return {
            "answer": (
                "Blind spots are units where care-gap risk >= 58 but data confidence < 58. "
                "Use the ranked list sorted by Priority or Low conf to find them. "
                "These require field verification before planning conclusions."
            ),
            "sql": None,
            "rows": [],
        }
    if "icu" in q or "maternity" in q or "emergency" in q:
        cap = next((c for c in ("icu", "maternity", "emergency") if c in q), "icu")
        return {
            "answer": (
                f"Select {cap.upper()} in the left rail and review units in the "
                "Confirmed desert quadrant (top-right) or blind spots (top-left). "
                "All scores come from Gold pipeline tables with cited facility evidence."
            ),
            "sql": None,
            "rows": [],
        }
    return {
        "answer": (
            "Ask about a capability (ICU, Maternity, etc.) and geography. "
            "Scores are deterministic from the Gold pipeline - risk, confidence, and verdict "
            "are never LLM-generated."
        ),
        "sql": None,
        "rows": [],
    }
