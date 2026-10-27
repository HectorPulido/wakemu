"""Fenced existing achievement facts for explicit reconstructed quest scenes.

This reads the authoritative achievement ledger; it never starts a quest,
completes an objective, accepts client snapshots or creates another ledger.
The caller owns the admission transaction and its checkpoint publication.
"""
from dataclasses import asdict, dataclass
import hashlib
import json


def canonical_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class AuthenticatedQuestFact:
    account_id: int
    character_id: int
    generation: str
    quest_id: int
    objective_id: int
    required_completed_objectives: tuple[int, ...]
    authority_revision: int
    snapshot_digest: str
    admitted_at_ms: int
    activation_criterion: str

    def record(self):
        return json.loads(json.dumps(asdict(self)))


def authenticated_quest_fact(
    store,
    db,
    *,
    account_id,
    generation,
    character_id,
    quest_id,
    objective_id,
    required_completed_objectives=(),
    activation_criterion=""
):
    """Return a trusted active/incomplete objective fact, or None if unavailable.

    Session/ownership failures raise. Ordinary unavailable quest/date facts deny
    the optional scene without preventing an unrelated ordinary fight.
    """
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.maps.dungeon_achievement_authority import queries_from_snapshot
    from wakfu_server.maps.dungeon_criteria import evaluate

    if (
        any(
            type(x) is not int or x <= 0
            for x in (account_id, character_id, quest_id, objective_id)
        )
        or type(required_completed_objectives) is not tuple
        or any(type(x) is not int or x <= 0 for x in required_completed_objectives)
        or not isinstance(activation_criterion, str)
    ):
        raise ValueError("Invalid typed quest scene scope")
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    lock_inventory_character(store, db, account_id, generation, character_id)
    row = db.execute(
        "SELECT snapshot,revision FROM character_achievement_authority "
        "WHERE character_id=%s FOR UPDATE",
        (character_id,),
    ).fetchone()
    if row is None:
        return None
    snapshot = row["snapshot"]
    queries = queries_from_snapshot(snapshot)
    if (
        not queries["IsAchievementRunning"](quest_id)
        or queries["IsAchievementObjectiveComplete"](objective_id)
        or not all(
            queries["IsAchievementObjectiveComplete"](x)
            for x in required_completed_objectives
        )
    ):
        return None
    now_ms = int(store.now().timestamp() * 1000)
    if activation_criterion and not evaluate(
        store, activation_criterion, now_ms=now_ms, queries=queries
    ):
        return None
    if type(row["revision"]) is not int or row["revision"] < 0:
        raise ValueError("Missing durable achievement revision")
    return AuthenticatedQuestFact(
        account_id,
        character_id,
        str(generation),
        quest_id,
        objective_id,
        required_completed_objectives,
        row["revision"],
        canonical_digest(snapshot),
        now_ms,
        activation_criterion,
    )
