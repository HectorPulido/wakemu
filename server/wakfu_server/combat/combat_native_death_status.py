"""Actual eGz.mwD state writes and eGj.dsA composition; never HP inference."""


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
    if snapshot.get("source") not in ("fresh.bjm.constructor", "owned.aTS.F"):
        raise ValueError("Missing actual native death-status provenance")
    status = snapshot.get("mwD")
    story = snapshot.get("dtM_status", "unknown")
    if status is True or story == 4:
        return True
    if status is not False or story == "unknown" or world is None:
        return None
    if story is None and snapshot.get("actor_kind") != "bje":
        return None  # Null dtM is proved for bje, not an arbitrary restored kind.
    if story is not None and type(story) is not int:
        raise ValueError("Malformed native dtM status")
    return False
