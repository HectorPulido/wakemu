"""Explicit boss-carrier adaptation of selected installed native stele states.

Native selectors, conditions, triggers and state arithmetic stay unchanged.
The boss-only carrier assignment is Wakemu policy, not an asserted official
server contract. The caller supplies the complete fight's native runtime.
"""
from copy import deepcopy
from hashlib import sha256
import json

POLICY = "wakemu-native-stele-boss-carrier-v1"


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def plan(fight, monsters, snapshot, rooms, states):
    if fight.phase != "active" or snapshot["fight_id"] != fight.id:
        raise ValueError("Stele states require the owned first active encounter")
    selected = sorted(
        {i for selection in snapshot["selections"] for i in selection["state_ids"]}
    )
    boss_refs = {m["ref_id"] for m in rooms[-1]["monsters"] if m["role"] == "boss"}
    carriers = sorted(i for i, m in monsters.items() if m["ref"] in boss_refs)
    if selected and len(carriers) != 1:
        raise ValueError("Stele policy requires one unambiguous frozen boss carrier")
    closure = {}
    for identity in selected:
        state = states["states"].get(str(identity))
        if state is None or state["maximum_level"] < 1:
            raise ValueError(
                "Selected stele state is absent from the installed catalog"
            )
        effects, todo = {}, list(state["effect_ids"])
        while todo:
            reference = str(todo.pop())
            if reference in effects:
                continue
            effect = states["effects"].get(reference)
            if effect is None:
                raise ValueError("Selected stele native effect closure is incomplete")
            effects[reference] = effect
            todo.extend(effect["children"])
        closure[str(identity)] = dict(state=state, effects=effects)
    for identity in carriers:
        actor = fight.actors.get(identity)
        if identity >= 0 or actor is None or actor.team == snapshot["player_team"]:
            raise ValueError("Stele carrier is not an owned enemy boss actor")
    return dict(
        policy=POLICY,
        fight_id=fight.id,
        initialized=True,
        snapshot_sha256=_digest(snapshot),
        state_ids=selected,
        actor_ids=carriers,
        native_sha256=_digest(closure),
    )


def initialize(db, fight, monsters, *, runtime_factory):
    """Apply once after ready(), before native fight-start delivery.

    Return (private_preview, receipt, packets). runtime_factory(preview,boss_id)
    supplies the complete native player/NPC factory. Replays emit no packets.
    """
    from wakfu_server import dungeon_stele

    snapshot = dungeon_stele.encounter_snapshot(db, fight.id)
    if snapshot is None or not snapshot["selections"]:
        return fight, None, []
    from wakfu_server.combat_server_spell import states_catalog

    run = db.execute(
        "SELECT rooms FROM dungeon_room_runs WHERE instance_id=%s",
        (snapshot["instance_id"],),
    ).fetchone()
    if run is None:
        raise ValueError("Stele encounter lacks its frozen dungeon roster")
    states = states_catalog()
    receipt = plan(fight, monsters, snapshot, run["rooms"], states)
    prior = getattr(fight, "native_dungeon_stele_receipt", None)
    if prior is not None:
        if prior != receipt:
            raise ValueError("Stele initialization replay changed frozen authority")
        return fight, receipt, []
    if (
        fight.turn_id != 1
        or fight.native_start_event_delivered
        or fight.current is None
    ):
        raise ValueError(
            "Stele activation requires the first active pre-start boundary"
        )
    if not callable(runtime_factory):
        raise ValueError("Stele initialization requires complete native fight runtime")
    from .dungeon_combat_scaling import validates_constructor_receipt

    if any(
        not validates_constructor_receipt(fight, identity)
        for identity in receipt["actor_ids"]
    ):
        raise ValueError(
            "Stele activation requires the completed dungeon constructor proof"
        )
    from wakfu_server.combat_definitions import state_profile
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_state_handler import StateCarrierContext
    from wakfu_server.combat_native_timing_context import native_time_payload

    preview = deepcopy(fight)
    packets = []
    for identity in receipt["actor_ids"]:
        actor = preview.actors[identity]
        factory = runtime_factory(preview, identity)
        sources = getattr(
            getattr(factory, "displacement_authority", None), "ordinary", None
        )
        if (
            sources is None
            or set(sources.characters) != {i for i in preview.actors if i > 0}
            or set(sources.monsters) != set(monsters)
        ):
            raise ValueError(
                "Stele native runtime lacks the complete owned player/NPC roster"
            )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        handler, retention = (
            dispatcher.native_state_handler,
            dispatcher.native_retention,
        )
        if handler.fight is not preview or retention is None:
            raise ValueError("Stele activation requires its owned native state manager")
        with preview.effect_resolution():
            for state_id in receipt["state_ids"]:
                profile = state_profile(states, state_id, 1)
                context = StateCarrierContext(
                    profile["duration"],
                    profile["realtime_duration"],
                    False,
                    None,
                    None,
                    False,
                    False,
                    False,
                    0,
                    native_time_payload(
                        realtime_remaining=profile["realtime_duration"]
                    ),
                )
                applied = retention.apply_state_reference(
                    handler,
                    EffectInvocation(2226, 1, identity, identity, actor.position),
                    state_id,
                    1,
                    carrier_context=context,
                    protected=None,
                )
                if applied is not True:
                    raise ValueError("Selected native stele state was not installed")
        packets.extend(outbox)
    preview.native_dungeon_stele_receipt = receipt
    return preview, receipt, packets
