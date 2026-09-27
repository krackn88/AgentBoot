from __future__ import annotations

import json
import re
from typing import Any

from gadgetforge.checker.jsonpath import get_path
from gadgetforge.checker.models import CheckOutcome, CheckerRecipe, ClassifyRule


def classify_response(
    recipe: CheckerRecipe,
    step_id: str,
    status: int,
    body: str | bytes | None,
    rules: list[ClassifyRule] | None = None,
) -> CheckOutcome:
    rules = rules or recipe.classify
    ordered = sorted(rules, key=lambda r: r.priority)
    text = ""
    data: Any = None
    if body:
        if isinstance(body, bytes):
            text = body.decode("utf-8", errors="replace")
        else:
            text = body
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None

    for rule in ordered:
        if rule.step_id and rule.step_id != step_id:
            continue
        if rule.status_codes and status not in rule.status_codes:
            continue
        if rule.body_contains:
            if not any(s.lower() in text.lower() for s in rule.body_contains):
                continue
        if rule.body_regex:
            if not re.search(rule.body_regex, text, re.I):
                continue
        if rule.json_path:
            if data is None:
                continue
            val = get_path(data, rule.json_path)
            if rule.json_exists and val in (None, "", []):
                continue
            if not rule.json_exists and val not in (None, "", []):
                continue
        return rule.outcome
    return CheckOutcome.UNKNOWN
