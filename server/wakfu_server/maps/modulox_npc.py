"""Mod'Ulo daily offers from the native haven-bag dialogue.

The speaker-to-root binding and NPC placement are reconstructed. Daily target
selection and completion use the existing persisted recurring-hunt authority.
"""
import struct
from wakfu_server import npc_dialogue, npc_world
from wakfu_server.achievements import storage
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_recurring_storage as recurring

ACTOR = -2251799934994399
REFERENCE = 4399
ACTION = 884
ROOT = 3972
SETTING = "reconstructed_modulox_provider_v1"
CHOICES = {
    10124: (684, 51),
    10019: (685, 96),
    10020: (686, 141),
    10441: (687, 186),
    11972: (810, 231),
}
# Original format-11 capture: map 9, actor 4399.
POSITION = (0, -5, 4)
DIRECTION = 1


def enabled(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    return bool(
        row
        and row["value"]
        == {"enabled": True, "reference_id": REFERENCE, "action_id": ACTION}
    )


def _owns(bag, character):
    return bag is not None and bag.is_owner and bag.owns(character)


def _nearby(bag, character):
    return (
        _owns(bag, character)
        and abs(character["z"] - POSITION[2]) <= 1
        and abs(character["x"] - POSITION[0]) + abs(character["y"] - POSITION[1]) <= 4
    )


def row(character):
    return dict(
        actor_id=ACTOR,
        reference_id=REFERENCE,
        map_id=9,
        instance_id=character["instance_id"],
        x=POSITION[0],
        y=POSITION[1],
        z=POSITION[2],
        direction=DIRECTION,
        interaction_range=4,
        dialogue_root=ROOT,
        action_ids=[ACTION],
        native_capture_id=None,
    )


def scene_packet(db, bag, character):
    if not _owns(bag, character) or not enabled(db):
        return None
    return npc_world.spawn(row(character), enabled_actions=(ACTION,))


def recognizes(store, opcode, body, session):
    if (
        opcode == 12058
        and session is not None
        and getattr(session, "modulox_npc", False)
    ):
        return True
    if opcode == 13222:
        matches = len(body) == 16 and struct.unpack(">qq", body) == (ACTOR, ACTION)
    elif opcode == 12535:
        matches = len(body) == 13 and struct.unpack(">ibq", body) == (ROOT, 2, ACTOR)
    else:
        matches = False
    if not matches:
        return False
    with store.connection() as db:
        return enabled(db)


def _offers(db, store, character, bag):
    selected = selection.select_for_character(db, store, character, bag_session=bag)
    return {
        x["category_id"]: dict(x)
        for x in selected
        if x["category_id"] in {value[0] for value in CHOICES.values()}
        and x["eligible"]
    }


def begin(
    store,
    account_id,
    generation,
    character,
    actor_id,
    action_id,
    *,
    bag_session,
    character_provider,
):
    if (actor_id, action_id) != (ACTOR, ACTION) or not _nearby(bag_session, character):
        raise ValueError("Mod'Ulo no está disponible aquí")
    with store.connection() as db:
        if not enabled(db):
            raise ValueError("Mod'Ulo no está disponible")
        offers = _offers(db, store, character, bag_session)
        packets = recurring.synchronize(db, store, character)
        state = storage.load_locked(db, character["id"])
        choices = {}
        for cid, (category, minimum) in CHOICES.items():
            if character["level"] < minimum or category not in offers:
                continue
            offer = offers[category]
            source, contract, _ = recurring._load(
                db, offer["definition_id"], offer["version"]
            )
            from wakfu_server.objectives.environmental_modulox_contracts import (
                accept_category,
            )

            if source[
                "interpretation_policy"
            ] == recurring.MODULOX_POLICY and accept_category(
                db,
                character,
                source["daily_target_authority"],
                now_ms=recurring._now(db),
            ):
                choices[cid] = offer
    native = npc_dialogue.catalog()["node_index"]
    graph = {(ROOT, cid): 0 for cid in choices}
    graph[ROOT, 10023] = 0
    owner = character["id"], account_id

    def speaker(speaker_id, node_id):
        current = character_provider()
        return (
            speaker_id == ACTOR
            and node_id == ROOT
            and (current["id"], current["account_id"]) == owner
            and _nearby(bag_session, current)
        )

    session = npc_dialogue.DialogueSession(
        native,
        graph,
        authorize_node=lambda node: node["id"] == ROOT and not node.get("criteria"),
        authorize_choice=lambda choice: choice["id"] in choices
        or choice["id"] == 10023,
    )
    packet = session.open(ROOT, ACTOR, speaker)
    session.modulox_npc = True
    session.modulox_offers = choices
    return session, packets + [packet]


def choose(store, account_id, generation, character, session, body, *, bag_session):
    request = npc_dialogue.decode_request(12058, body)
    prior = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            if not enabled(db) or not _nearby(bag_session, character):
                raise ValueError("Mod'Ulo ya no está disponible")
            offered = session.modulox_offers.get(request["choice_id"])
            packet = session.choose(**request)
            packets = []
            if offered is not None:
                selected = _offers(db, store, character, bag_session)
                current = selected.get(offered["category_id"])
                if current is None or any(
                    current[k] != offered[k]
                    for k in ("definition_id", "version", "utc_day")
                ):
                    raise ValueError("La oferta diaria ya cambió")
                source, contract, _ = recurring._load(
                    db, current["definition_id"], current["version"]
                )
                now_ms = recurring._now(db)
                period = contract.period(now_ms)
                if period is None:
                    raise ValueError("La oferta diaria no está disponible")
                key = f"native-modulox-npc:{current['definition_id']}:{period}"
                fact = dict(
                    kind="native_recurring_acceptance",
                    definition_id=current["definition_id"],
                    real_level=character["level"],
                    source_kind="npc_dialogue",
                    source_reference=REFERENCE,
                    action_id=ACTION,
                    node_id=ROOT,
                    choice_id=request["choice_id"],
                    actor_id=ACTOR,
                    reconstruction="modulox-owned-haven-bag-v1",
                )
                if not storage.record_event(db, character["id"], key, fact):
                    raise ValueError("Esta misión ya fue aceptada")
                result = recurring.accept_from_receipt(
                    db, store, character, current["definition_id"], receipt_key=key
                )
                packets.extend(result["packets"])
            if packet is not None:
                packets.append(packet)
            return {"packets": packets}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = prior
        raise
