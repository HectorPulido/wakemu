"""Native earning/admission criterion, including the client's mercenary loader.

aZx.a(aJM, Multimap) adds effective level, optional licence possession and
every lower rank in the same category to cjI for cjW definitions. aHe remains
visibility only. The small reviewed index includes all 95 native contracts,
including unpublished/invisible ones; runtime never scans a combat catalogue.
"""

from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _index():
    document = json.loads(
        Path(__file__).with_name("native_mercenary_ranks.json").read_text()
    )
    if (
        document.get("schema_version") != 1
        or document.get("policy") != "native_aZx_mercenary_eligibility_v1"
    ):
        raise ValueError("Unqualified native mercenary rank source")
    result = {}
    for row in document["definitions"]:
        if (
            set(row) != {"d", "cjG", "cjY", "cjP", "cjX", "cjI"}
            or any(
                type(row[k]) is not int or row[k] < 0
                for k in ("d", "cjG", "cjY", "cjP", "cjX")
            )
            or not row["d"]
            or not row["cjG"]
            or not row["cjY"]
            or not row["cjP"]
            or type(row["cjI"]) is not str
            or row["d"] in result
        ):
            raise ValueError("Invalid native mercenary rank source")
        result[row["d"]] = row
    return result


def criterion(definition):
    """Return the effective criterion without rewriting the native definition.

    An unknown or changed mercenary definition fails closed until its complete
    rank index is reviewed. Non-mercenary definitions preserve cjI verbatim.
    GetLevel requires the evaluator's explicit owned effective-level context.
    """
    raw = definition["cjI"]
    if type(raw) is not str:
        raise ValueError("Invalid native quest availability")
    flag = definition.get("cjW", False)
    if type(flag) is not bool:
        raise ValueError("Invalid native mercenary flag")
    index = _index()
    if not flag:
        if definition.get("d") in index:
            raise ValueError("Missing native mercenary eligibility flag")
        return raw
    row = index.get(definition.get("d"))
    if row is None or any(
        type(definition.get(key)) is not type(value) or definition.get(key) != value
        for key, value in row.items()
    ):
        raise ValueError("Unqualified native mercenary eligibility")
    parts = [f"GetLevel() >= {row['cjP']}"]
    if row["cjX"] > 0:
        parts.append(f"GetItemQuantity({row['cjX']}) > 0")
    parts.extend(
        f"IsAchievementComplete({identity})"
        for identity, other in sorted(index.items())
        if other["cjG"] == row["cjG"] and other["cjY"] < row["cjY"]
    )
    generated = "(" + " && ".join(parts) + ")"
    return generated if not raw else generated + " && (" + raw + ")"
