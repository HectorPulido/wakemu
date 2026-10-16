"""Native gift-window sections and deterministic objective pagination."""
import math

SECTIONS = (
    "overview",
    "tasks",
    "achievements",
    "missions",
    "pvp",
    "daily",
    "weekly",
    "almanax",
)
PAGE_SIZE = 20


def parse(arguments):
    if len(arguments) > 2:
        raise ValueError(
            "Usage: !tasks [overview|tasks|achievements|missions|pvp|daily|weekly|almanax] [page]"
        )
    section = arguments[0].lower() if arguments else "overview"
    if section not in SECTIONS:
        raise ValueError("Unknown objectives section. Choose: " + ", ".join(SECTIONS))
    try:
        page = int(arguments[1]) if len(arguments) == 2 else 1
    except ValueError as exc:
        raise ValueError("Objective page must be a positive integer") from exc
    if not 1 <= page <= 1000000:
        raise ValueError("Objective page must be a positive integer")
    return section, page


def category(definition):
    kind = definition["kind"]
    if kind == "pvp":
        return "pvp"
    if kind == "almanax":
        return "almanax"
    schedule = definition["schedule"]["type"]
    if schedule == "daily" or kind == "daily":
        return "daily"
    if schedule == "weekly":
        return "weekly"
    return {"achievement": "achievements", "mission": "missions"}.get(kind, "tasks")


def _card(key, title, description):
    return {
        "key": key,
        "title": title,
        "description": description,
        "target": 1,
        "count": 0,
        "completed": False,
    }


def project(snapshot, definitions, section, page):
    if section not in SECTIONS or type(page) is not int or page < 1:
        raise ValueError("Invalid objective section or page")
    # Backend uppercase keys have a private native identity; match both forms.
    import hashlib

    groups = {}
    for row in definitions:
        key = row["key"]
        groups[key] = category(row["definition"])
        groups["objective:" + hashlib.sha256(key.encode()).hexdigest()] = groups[key]
    selected = (
        snapshot
        if section == "overview"
        else [row for row in snapshot if groups.get(row["key"]) == section]
    )
    selected = sorted(selected, key=lambda row: (row["completed"], row["key"]))
    pages = max(1, math.ceil(len(selected) / PAGE_SIZE))
    # Calendar rollover and admin edits may shrink an already selected section.
    page = min(page, pages)
    counts = []
    for name in SECTIONS[1:]:
        rows = [row for row in snapshot if groups.get(row["key"]) == name]
        if rows:
            counts.append(
                f"{name}: {sum(row['completed'] for row in rows)}/{len(rows)} completed — !tasks {name}"
            )
    header = _card(
        "objectives.navigation",
        f"Objectives: {section} — page {page}/{pages}",
        "\n".join(counts)
        + "\nUse !tasks <section> <page> to change this Gifts window. "
        "Rewards are delivered automatically. Use !adventures for your account dashboard.",
    )
    result = [header] + selected[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    if not selected:
        result.append(
            _card(
                "objectives.empty",
                "No objectives in this section",
                "There are no active objectives for your level and the current period.",
            )
        )
    return result


def weekly_ranking(db, account_id, now):
    from wakfu_server.objectives.rankings import week_key, list_rankings

    week = week_key(now)
    rows = list_rankings(db, week=week, limit=1000)
    lines = [
        f"Week: {week}. Completed objectives add points to your shared account total."
    ]
    for row in rows:
        if row["rank"] > 10 and row["account_id"] != account_id:
            continue
        label = (
            "You"
            if row["account_id"] == account_id
            else f"Account #{row['account_id']}"
        )
        lines.append(f"#{row['rank']}: {label}, {row['points']} points")
    if len(lines) == 1:
        lines.append(
            "No points yet this week. Complete your assigned objectives to join the ranking."
        )
    return _card(
        "objectives.weekly.ranking", "Weekly account ranking", "\n".join(lines)
    )
