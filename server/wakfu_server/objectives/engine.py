"""Match immutable, server-authored facts without client authority."""


def increment(objective, payload):
    if objective["event"] != payload.get("kind"):
        return 0
    filters = objective["filters"]
    from .progression import ABSOLUTE_EVENTS

    if payload["kind"] in ABSOLUTE_EVENTS:
        return payload["count"] if _matches(filters, payload) else 0
    if payload["kind"] == "original_monster_killed":
        references = filters.get("references")
        remaining = {k: v for k, v in filters.items() if k != "references"}
        if not _matches(remaining, payload):
            return 0
        return sum(
            references is None or actor["reference"] in references
            for actor in payload["actors"]
        )
    if payload["kind"] == "monster_seed_planted" and "family_id" in filters:
        if filters["family_id"] not in payload.get("family_ids", []):
            return 0
        filters = {k: v for k, v in filters.items() if k != "family_id"}
    return int(_matches(filters, payload))


def _matches(filters, payload):
    return all(
        field in payload
        and (
            any(
                type(payload[field]) is type(value) and payload[field] == value
                for value in expected
            )
            if type(expected) is list
            else type(payload[field]) is type(expected) and payload[field] == expected
        )
        for field, expected in filters.items()
    )
