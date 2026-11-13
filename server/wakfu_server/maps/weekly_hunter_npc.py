"""Reconstructed native weekly hunter offers at the existing Magnum actor.

The speaker-to-offer root is a Wakemu reconstruction; all offer IDs, criteria,
quest contracts, progress and rewards are supplied by the native catalog.
"""
import struct

from wakfu_server import npc_dialogue
from wakfu_server.achievements import storage
from wakfu_server.achievements.service import _owner
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.objectives.environmental_recurring_offers import (
    hunter_acceptance_condition,
)

ACTOR = -1724034232352753
REFERENCE = 3819
ACTION = 703
SETTING = "reconstructed_weekly_hunter_provider_v1"


def enabled(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    return bool(
        row
        and row["value"] == {"enabled": True, "actor_id": ACTOR, "action_id": ACTION}
    )


def select_offers(rows, level):
    """Highest original bracket is an explicit local presentation policy."""
    if type(level) is not int or level <= 0:
        raise ValueError("Invalid hunter level")
    eligible = []
    for source in rows:
        row = dict(source)
        minimum, category = hunter_acceptance_condition(
            row["criterion"], definition_id=row["definition_id"]
        )
        if minimum != row["minimum_level"] or category != row["category_id"]:
            raise ValueError("Hunter offer differs from its native criterion")
        if minimum <= level:
            eligible.append(row)
    if not eligible:
        raise ValueError("No eligible hunter offer")
    root = max(eligible, key=lambda x: x["minimum_level"])["node_id"]
    return [row for row in eligible if row["node_id"] == root]


def _offers(db, level):
    rows = db.execute(
        "SELECT o.* FROM recurring_hunter_native_offers o "
        "JOIN recurring_hunter_contracts c USING(definition_id,version) "
        "WHERE c.period_ms=604800000 AND o.version=(SELECT max(o2.version) "
        "FROM recurring_hunter_native_offers o2 WHERE o2.definition_id=o.definition_id)"
    ).fetchall()
    return select_offers(rows, level)


def _actor(db):
    from wakfu_server import npc_placements

    row = db.execute(
        "SELECT * FROM world_native_npc_placements WHERE actor_id=%s AND enabled FOR SHARE",
        (ACTOR,),
    ).fetchone()
    if row is None or not enabled(db):
        raise ValueError("Hunter NPC unavailable")
    npc_placements.validate(row)
    if row["reference_id"] != REFERENCE or ACTION not in row["native_action_ids"]:
        raise ValueError("Hunter NPC source differs")
    return row


def _nearby(character, row):
    return (
        (character["map_id"], character.get("instance_id", 0))
        == (row["map_id"], row["instance_id"])
        and abs(character["z"] - row["z"]) <= 1
        and abs(character["x"] - row["x"]) + abs(character["y"] - row["y"]) <= 4
    )


def recognizes(store, opcode, body, session):
    if (
        opcode == 12058
        and session is not None
        and getattr(session, "weekly_hunter", False)
    ):
        return True
    if (
        opcode != 13222
        or len(body) != 16
        or struct.unpack(">qq", body) != (ACTOR, ACTION)
    ):
        return False
    with store.connection() as db:
        return enabled(db)


def begin(
    store, account_id, generation, character, actor_id, action_id, *, character_provider
):
    if (actor_id, action_id) != (ACTOR, ACTION):
        raise ValueError("Unknown hunter NPC action")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        actual = store.character(account_id, character["id"], db)
        _owner(db, actual)
        row = _actor(db)
        if not _nearby(actual, row):
            raise ValueError("Hunter NPC fuera de alcance")
        packets = recurring.synchronize(db, store, actual)
        offers = _offers(db, actual["level"])
    native = npc_dialogue.catalog()["node_index"]
    root = offers[0]["node_id"]
    choices = {o["choice_id"]: o for o in offers}
    for choice_id, offer in choices.items():
        native_choice = next(
            (c for c in native[root]["choices"] if c["id"] == choice_id), None
        )
        if (
            native_choice is None
            or native_choice["type"] != 5
            or native_choice["criteria"] != offer["criterion"]
        ):
            raise ValueError("Hunter native choice has changed")
    graph = {(root, identity): 0 for identity in choices}
    # Permit native unconditional exit choices without inventing an offer.
    for choice in native[root]["choices"]:
        if choice["type"] == 10 and not choice["criteria"]:
            graph[root, choice["id"]] = 0

    def speaker(speaker_id, node_id):
        current = character_provider()
        return (
            speaker_id == ACTOR
            and node_id == root
            and current["id"] == character["id"]
            and current["account_id"] == account_id
            and _nearby(current, row)
        )

    session = npc_dialogue.DialogueSession(
        native,
        graph,
        authorize_node=lambda node: node["id"] == root and not node.get("criteria"),
        authorize_choice=lambda choice: choice["id"] in choices
        or (choice["type"] == 10 and not choice["criteria"]),
    )
    packet = session.open(root, ACTOR, speaker)
    session.weekly_hunter = True
    session.weekly_hunter_offers = choices
    return session, packets + [packet]


def choose(store, account_id, generation, character, session, body):
    request = npc_dialogue.decode_request(12058, body)
    prior = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            _owner(db, current)
            row = _actor(db)
            if not _nearby(current, row):
                raise ValueError("Hunter NPC fuera de alcance")
            # Validate the exact offered edge and speaker before mutating state.
            packet = session.choose(**request)
            offer = session.weekly_hunter_offers.get(request["choice_id"])
            packets = []
            if offer is not None:
                fresh = _offers(db, current["level"])
                if offer not in fresh or request["node_id"] != offer["node_id"]:
                    raise ValueError("Hunter offer no longer available")
                packets.extend(recurring.synchronize(db, store, current))
                before = storage.load_locked(db, current["id"])
                from wakfu_server.maps import daily_hunter_npc

                daily_enabled = daily_hunter_npc.enabled(db)
                active_ids = before["running"]
                if active_ids and not daily_enabled:
                    categories = db.execute(
                        "SELECT definition_id FROM native_quest_metadata_definitions WHERE revision="
                        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
                        "AND definition_id=ANY(%s) AND (data->'native'->>'cjG')::integer=%s",
                        (active_ids, offer["category_id"]),
                    ).fetchall()
                    if categories:
                        raise ValueError("Ya hay una misión de esta categoría activa")
                source, contract, _ = recurring._load(
                    db, offer["definition_id"], offer["version"]
                )
                now_ms = recurring._now(db)
                period = contract.period(now_ms)
                if period is None:
                    raise ValueError("Hunter offer period unavailable")
                previous = db.execute(
                    "SELECT 1 FROM recurring_hunter_acceptances WHERE character_id=%s AND definition_id=%s AND period_index=%s",
                    (current["id"], offer["definition_id"], period),
                ).fetchone()
                weekly_exists = (
                    previous is not None
                    or offer["definition_id"] in before["completed"]
                    or offer["definition_id"] in before["running"]
                )
                if weekly_exists and not daily_enabled:
                    raise ValueError("Ya aceptaste esta misión en el periodo actual")
                if not weekly_exists:
                    key = f"native-hunter-npc:{offer['definition_id']}:{period}"
                    fact = dict(
                        kind="native_recurring_acceptance",
                        definition_id=offer["definition_id"],
                        real_level=current["level"],
                        source_kind="npc_dialogue",
                        source_reference=REFERENCE,
                        action_id=ACTION,
                        node_id=request["node_id"],
                        choice_id=request["choice_id"],
                        actor_id=ACTOR,
                        reconstruction="highest_eligible_weekly_bracket_v1",
                    )
                    if not storage.record_event(db, current["id"], key, fact):
                        raise ValueError("Hunter acceptance already recorded")
                    result = recurring.accept_from_receipt(
                        db, store, current, offer["definition_id"], receipt_key=key
                    )
                    packets.extend(result["packets"])
                if daily_enabled:
                    packets.extend(
                        daily_hunter_npc.accept_for_choice(
                            db,
                            store,
                            current,
                            offer,
                            actor_id=ACTOR,
                            reference_id=REFERENCE,
                            action_id=ACTION,
                        )
                    )
            if packet is not None:
                packets.append(packet)
            return {
                "packets": packets,
                "definition_id": None if offer is None else offer["definition_id"],
            }
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = prior
        raise
