"""Environmental participation follows the real loaded owned hero company."""
from dataclasses import replace


def loaded_ids(db, account_id, main_character_id):
    """A stored company belonging to another selected leader loads nobody."""
    rows = db.execute(
        "SELECT h.character_id,c.account_id,c.deleted_at FROM account_hero_rosters r "
        "JOIN account_hero_slots h USING(account_id) JOIN characters c ON c.id=h.character_id "
        "WHERE r.account_id=%s AND r.leader_id=%s ORDER BY h.slot",
        (account_id, main_character_id),
    ).fetchall()
    identities = tuple(row["character_id"] for row in rows)
    from wakfu_server.characters.heroes import NATIVE_HERO_CAP

    if (
        len(identities) > NATIVE_HERO_CAP
        or len(set(identities)) != len(identities)
        or main_character_id in identities
        or any(
            r["account_id"] != account_id or r["deleted_at"] is not None for r in rows
        )
    ):
        raise ValueError("Invalid loaded environmental hero company")
    return identities


def project_interaction(db, fact):
    """Project a genuine committed main action to its currently loaded heroes.

    This runs inside the action's owner transaction, not on receipt replay or a
    client completion request. Enrollment and each hero's level eligibility are
    independently checked by the shared contribution engine.
    """
    from .environmental_gameplay import GameplayFact
    from . import environmental_presence as presence

    if type(fact) is not GameplayFact or fact.kind not in (
        "resource_collected",
        "resource_planted",
        "monster_destroyed",
    ):
        raise ValueError(
            "Environmental company projection requires its committed interaction"
        )
    if presence.capture(fact.map_id, fact.instance_id) is None:
        return ()
    selected = db.execute(
        "SELECT 1 FROM sessions WHERE account_id=%s AND character_id=%s "
        "AND expires_at>to_timestamp(%s/1000.0)",
        (fact.account_id, fact.character_id, fact.occurred_at_ms),
    ).fetchone()
    heroes = (
        () if selected is None else loaded_ids(db, fact.account_id, fact.character_id)
    )
    return (fact, *(replace(fact, character_id=identity) for identity in heroes))
