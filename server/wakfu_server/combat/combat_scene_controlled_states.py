"""Source-pinned server state application to an owned scene's actual player.

This is a reviewed external encounter publisher, not a claim that a player has
NPC constructor innates. Original state programs own resources and spellbooks.
"""

from copy import deepcopy
from contextvars import ContextVar
from contextlib import contextmanager


_placement_application = ContextVar(
    "controlled_scene_placement_application", default=None
)


@contextmanager
def _application_scope(fight, characters, plans, row):
    if row not in plans or prepare(fight, characters) != tuple(plans):
        raise ValueError("Controlled placement authority changed")
    identity = next(iter(characters))
    token = _placement_application.set((fight, identity, row["state_id"], row["level"]))
    try:
        yield
    finally:
        _placement_application.reset(token)


def placement_application_authorized(fight, source_id, target_id, reference, level):
    """Permit only the exact declared SELF carrier inside its checked publisher."""
    scope = _placement_application.get()
    if (
        scope is None
        and fight.phase == "placement"
        and getattr(fight, "native_order_trial_constructor", None) is not None
    ):
        from .native_order_trial_placement import application_authorized

        return application_authorized(fight, source_id, target_id, reference, level)
    return (
        scope is not None
        and scope[0] is fight
        and fight.phase == "placement"
        and source_id == target_id == scope[1]
        and (reference, level) == scope[2:]
    )


def placement_stat_context(fight, invocation):
    """Native children of the checked SELF publisher can initialize its stats."""
    scope = _placement_application.get()
    if (
        scope is None
        and fight.phase == "placement"
        and getattr(fight, "native_order_trial_constructor", None) is not None
    ):
        from .native_order_trial_placement import stat_context

        return stat_context(fight, invocation)
    return (
        scope is not None
        and scope[0] is fight
        and fight.phase == "placement"
        and invocation.caster_id == invocation.target_id == scope[1]
        and fight.actors.get(scope[1]) is not None
    )


def declarations(descriptor):
    rows = descriptor.get("controlled_state_programs", ())
    if type(rows) not in (list, tuple):
        raise ValueError("Invalid controlled scene state declarations")
    seen = set()
    for row in rows:
        if (
            type(row) is not dict
            or set(row)
            != {"state_id", "level", "protected", "source_sha256", "evidence"}
            or type(row["state_id"]) is not int
            or row["state_id"] <= 0
            or row["state_id"] in seen
            or type(row["level"]) is not int
            or not 0 <= row["level"] <= 32767
            or type(row["protected"]) is not bool
            or type(row["source_sha256"]) is not str
            or len(row["source_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["source_sha256"])
            or type(row["evidence"]) is not str
            or not row["evidence"].strip()
            or descriptor.get("full_room_scope") is not True
        ):
            raise ValueError("Controlled state lacks its exact reviewed source")
        seen.add(row["state_id"])
    return rows


def prepare(fight, characters, *, catalog=None):
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles
    from .combat_encounter_scene_states import native_state_source_digest
    from .combat_definitions import state_profile

    descriptor = frozen_scene(fight)
    if descriptor is None:
        return ()
    rows = declarations(descriptor)
    if not rows:
        return ()
    if getattr(fight, "native_controlled_scene_state_receipt", None) is not None:
        raise ValueError("Controlled scene states were already published")
    roles = assigned_roles(fight)
    if len(characters) != 1:
        raise ValueError("Controlled scene states require the actual solo player")
    identity, source = next(iter(characters.items()))
    actor = fight.actors.get(identity)
    if (
        fight.phase != "placement"
        or actor is None
        or actor.controlled is not True
        or actor.team != roles.player_team
        or source.get("id") != identity
        or source.get("account_id") != actor.owner_id
        or source.get("map_id") != roles.map_id
        or source.get("instance_id")
        != fight.native_encounter_scene["scope"]["instance_id"]
        or type(source.get("instance_id")) is not int
        or source["instance_id"] <= 0
    ):
        raise ValueError("Controlled scene states lost their original player scope")
    if catalog is None:
        from .combat_server_spell import states_catalog

        catalog = states_catalog()
    for row in rows:
        if native_state_source_digest(catalog, row["state_id"]) != row["source_sha256"]:
            raise ValueError("Controlled scene state source changed")
        native = state_profile(catalog, row["state_id"], row["level"])
        # Native negative realtime values also denote an indefinite carrier.
        if native["duration"] >= 0 or native["realtime_duration"] > 0:
            raise ValueError(
                "Controlled scene state requires an indefinite native carrier"
            )
    return tuple(deepcopy(rows))


def install(fight, characters, monsters, plans):
    if not plans:
        return
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_npc_initialization import _runtime
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload
    from .combat_qi_fight import current_registry

    if tuple(declarations(frozen_scene(fight))) != tuple(plans):
        raise ValueError("Controlled scene state plans changed before installation")
    identity = next(iter(characters))
    actor = fight.actors[identity]
    if getattr(fight, "native_controlled_scene_state_receipt", None) is not None:
        raise ValueError("Controlled scene states already installed")
    current_registry(fight)
    factory, _ = _runtime(monsters, identity, characters=characters)
    dispatcher, _outbox = factory(
        fight, {"native_retained_container": {"present": False}}
    )
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if prepare(fight, characters, catalog=handler.catalog) != tuple(plans):
        raise ValueError("Controlled scene state authority changed after registration")
    before = {entry.uid for entry in actor.state_ledger.entries}
    for row in plans:
        native = state_profile(handler.catalog, row["state_id"], row["level"])
        context = StateCarrierContext(
            native["duration"],
            native["realtime_duration"],
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=native["realtime_duration"]),
        )
        invocation = EffectInvocation(
            2226,
            row["level"],
            identity,
            identity,
            actor.position,
            native_retained_container={"present": False},
        )
        with _application_scope(fight, characters, plans, row):
            if not retention.apply_state_reference(
                handler,
                invocation,
                row["state_id"],
                row["level"],
                carrier_context=context,
                protected=True if row["protected"] else None,
            ):
                raise ValueError("Original controlled scene state application rejected")
    fight.native_controlled_scene_state_receipt = dict(
        source="wakemu.reviewed_controlled_scene_state.v1",
        actor_id=identity,
        scene_sha256=fight.native_encounter_scene["sha256"],
        programs=deepcopy(list(plans)),
        state_uids=[
            entry.uid for entry in actor.state_ledger.entries if entry.uid not in before
        ],
    )
