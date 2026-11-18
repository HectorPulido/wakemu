"""Durable counts for reviewed direct objectives, separate from native variables.

The authenticated producer owns the character lock and transaction. Counters
are persisted only after the existing event receipt is claimed, so operation
replays, failed payments and failed rewards cannot earn another count.
"""


def load(db, character_id, objective_ids):
    identities = sorted(set(objective_ids))
    if (
        type(character_id) is not int
        or character_id <= 0
        or any(type(identity) is not int or identity <= 0 for identity in identities)
    ):
        raise ValueError("Invalid server objective counter identity")
    if not identities:
        return {}
    rows = db.execute(
        "SELECT objective_id,count FROM character_mission_objective_counts "
        "WHERE character_id=%s AND objective_id=ANY(%s) FOR UPDATE",
        (character_id, identities),
    ).fetchall()
    counts = {identity: 0 for identity in identities}
    for row in rows:
        value = row["count"]
        if type(value) is not int or not 0 <= value < 2**31:
            raise ValueError("Invalid persisted server objective counter")
        counts[row["objective_id"]] = value
    return counts


def store(db, character_id, before, after):
    """Persist monotonic changed counts; native completion state is untouched."""
    if type(character_id) is not int or character_id <= 0 or set(before) != set(after):
        raise ValueError("Invalid server objective count snapshot")
    for identity, value in after.items():
        if (
            type(identity) is not int
            or identity <= 0
            or type(value) is not int
            or not 0 <= value < 2**31
            or type(before[identity]) is not int
            or not 0 <= before[identity] < 2**31
            or value < before[identity]
        ):
            raise ValueError("Invalid or regressing server objective count")
        if value != before[identity]:
            db.execute(
                "INSERT INTO character_mission_objective_counts(character_id,objective_id,count) "
                "VALUES(%s,%s,%s) ON CONFLICT(character_id,objective_id) "
                "DO UPDATE SET count=EXCLUDED.count",
                (character_id, identity, value),
            )
