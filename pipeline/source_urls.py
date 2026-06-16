"""Parse facility source_urls (JSON array, comma-list, or plain URL)."""

from __future__ import annotations

import json
import re
from typing import Any

_HTTP = re.compile(r"^https?://", re.I)


def first_source_url(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if _HTTP.match(s):
        return s
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                for item in parsed:
                    u = str(item).strip().strip("\"'")
                    if _HTTP.match(u):
                        return u
        except json.JSONDecodeError:
            pass
    for part in re.split(r"[,;]", s):
        u = part.strip().strip("\"'[]")
        if _HTTP.match(u):
            return u
    return None
