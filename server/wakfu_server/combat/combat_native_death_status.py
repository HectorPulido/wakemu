"""Actual eGz.mwD state writes and eGj.dsA composition; never HP inference."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FreshPlayerDeathConstructor:
    """Original bjo source selected by the validated player snapshot builder."""

    actor_id: int
    world_properties: tuple


def fresh_player_death_constructor(actor_id):
    from .combat_ordinary_authority import native_property_catalog

    return FreshPlayerDeathConstructor(
        actor_id, tuple(native_property_catalog()["player"]["world_properties"])
    )


def validate_fresh_player_death_constructor(actor, constructor):
    from .combat_ordinary_authority import native_property_catalog
    from .combat_property_stack import add_property

    if (
        type(constructor) is not FreshPlayerDeathConstructor
        or type(constructor.actor_id) is not int
        or constructor.actor_id <= 0
        or actor.id != constructor.actor_id
        or actor.controlled is not True
        or getattr(actor, "native_summon_source", None) is not None
        or getattr(actor, "is_summon", False) is True
        or type(constructor.world_properties) is not tuple
        or constructor.world_properties
        != tuple(native_property_catalog()["player"]["world_properties"])
    ):
        raise ValueError(
            "Fresh player death status requires its actual bjo constructor"
        )
    counts = {}
    for identity in constructor.world_properties:
        add_property(counts, identity)
    return counts


def initialize_fresh_player_death_status(actor, *, constructor):
    """Record actual JVM defaults only at the fresh owned bjo boundary.

    Existing assigned story status/world counters are never reset by a player
    snapshot. Direct repeated constructor calls reject rather than relabeling a
    restored actor; checkpoint hydration does not invoke this constructor.
    """
    counts = validate_fresh_player_death_constructor(actor, constructor)
    if hasattr(actor, "native_death_status"):
        raise ValueError("Fresh native death status already initialized")
    if (
        getattr(actor, "native_world_property_counts", None) is None
        and getattr(actor, "native_world_properties", None) is None
    ):
        # Materialize the same complete original profile used by ordinary
        # authority's fresh-player fallback, not an inferred empty PB manager.
        actor.native_world_property_counts = counts
        actor.native_world_properties = frozenset(
            identity for identity, count in counts.items() if count != 0
        )
    actor.native_death_status = dict(
        source="fresh.bjo.constructor",
        actor_kind="bjo",
        mwD=False,
        dtM_status=None,
        last_writer="fresh.bjo.constructor",
    )


def initialize_fresh_bje_death_status(actor):
    if hasattr(actor, "native_death_status"):
        raise ValueError("Fresh native death status already initialized")
    actor.native_death_status = dict(
        source="fresh.bjm.constructor",
        actor_kind="bje",
        mwD=False,
        dtM_status=None,
        last_writer="fresh.bjm.constructor",
    )
    from .combat_restore_strategy import initialize_restore_strategy

    initialize_restore_strategy(actor)


def apply_native_fighter_state_transition(actor, state):
    """aTS.F:0/3 preserve mwD;1 gg(false);2 gg(true)."""
    if type(state) is not int or state not in (0, 1, 2, 3):
        raise ValueError("Unknown native fighter state transition")
    snapshot = getattr(actor, "native_death_status", None)
    if snapshot is None:
        # Actual gg is known even when old restoration lacks kind/dtM facts.
        snapshot = dict(
            source="owned.aTS.F",
            actor_kind=None,
            mwD=None,
            dtM_status="unknown",
            last_writer=None,
        )
        actor.native_death_status = snapshot
    if not isinstance(snapshot, dict):
        raise ValueError("Malformed actual native death status")
    if state in (0, 3):
        # Record the actual wire transition without changing native mwD.
        # This checkpointed writer distinguishes reversible KO from final2.
        snapshot["last_writer"] = f"owned.aTS.F.type{state}"
    if state in (1, 2):
        requested = state == 2
        # eGj.gg first compares COMPOUND dsA to the requested value. A
        # world DEAD flag can therefore suppress a write to eGz.mwD.
        current = native_is_dead(actor)
        if requested is False:
            # A no-op means dsA=false, which already implies mwD=false;
            # the other branch explicitly writes false. Both close mwD.
            snapshot["mwD"] = False
        elif current is not None and current != requested:
            snapshot["mwD"] = requested
        elif current is None and snapshot.get("mwD") is not requested:
            snapshot["mwD"] = None
        snapshot["last_writer"] = f"owned.aTS.F.type{state}"


def native_is_dead(actor):
    """Three-valued actual dsA from status, dtM and complete world properties."""
    world = getattr(actor, "native_world_properties", None)
    if world is not None and 19 in world:
        return True
    snapshot = getattr(actor, "native_death_status", None)
    if not isinstance(snapshot, dict):
        return None
    source = snapshot.get("source")
    fresh_kinds = {"fresh.bjm.constructor": "bje", "fresh.bjo.constructor": "bjo"}
    if source not in (*fresh_kinds, "owned.aTS.F"):
        raise ValueError("Missing actual native death-status provenance")
    if source in fresh_kinds and snapshot.get("actor_kind") != fresh_kinds[source]:
        raise ValueError("Native death-status constructor kind differs from its source")
    status = snapshot.get("mwD")
    story = snapshot.get("dtM_status", "unknown")
    if status is True or story == 4:
        return True
    if status is not False or story == "unknown" or world is None:
        return None
    if story is None and not (
        snapshot.get("actor_kind") == "bje"
        or (source == "fresh.bjo.constructor" and snapshot.get("actor_kind") == "bjo")
    ):
        return None  # Null dtM needs its actual constructor-kind proof.
    if story is not None and type(story) is not int:
        raise ValueError("Malformed native dtM status")
    return False
