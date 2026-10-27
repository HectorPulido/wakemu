"""Canonical actor/species pairs, independent from sorted wave identity sets.

The old roster arrays sorted only IDs. Missing associations are recoverable
only from an actual accepted fight's native sources and actors, checked against
the frozen wave selection; ordering the two old arrays together is not proof.
"""

from collections import Counter, defaultdict, deque


def _roster(run, roster):
    from wakfu_server.rift_policy import select_wave

    wave, identities, references = (
        roster.get("wave"),
        roster.get("actor_ids"),
        roster.get("species_refs"),
    )
    if (
        type(wave) is not int
        or wave <= 0
        or not isinstance(identities, (list, tuple))
        or not identities
        or any(type(identity) is not int or identity >= 0 for identity in identities)
        or len(set(identities)) != len(identities)
        or list(identities) != sorted(identities)
        or not isinstance(references, (list, tuple))
        or len(references) != len(identities)
        or any(type(reference) is not int or reference <= 0 for reference in references)
        or tuple(references)
        != select_wave(run["catalog"], run["policy"], run["seed"], wave)
    ):
        raise ValueError("Rift roster differs from its frozen native wave")
    return wave, tuple(identities), tuple(references)


def _validate_pairs(identities, references, pairs):
    pairs = tuple(tuple(pair) for pair in pairs)
    if (
        len(pairs) != len(identities)
        or any(
            len(pair) != 2 or any(type(value) is not int for value in pair)
            for pair in pairs
        )
        or {pair[0] for pair in pairs} != set(identities)
        or tuple(pair[1] for pair in pairs) != references
    ):
        raise ValueError("Rift actor/species association changed its native roster")
    return pairs


def _stored(db, instance_id, wave):
    return db.execute(
        "SELECT ordinal,actor_id,species_reference FROM rift_wave_actor_bindings "
        "WHERE instance_id=%s AND wave=%s ORDER BY ordinal",
        (instance_id, wave),
    ).fetchall()


def _write(db, instance_id, wave, pairs, source):
    for ordinal, (identity, reference) in enumerate(pairs):
        db.execute(
            "INSERT INTO rift_wave_actor_bindings"
            "(instance_id,wave,ordinal,actor_id,species_reference,binding_source) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (instance_id, wave, ordinal, identity, reference, source),
        )


def freeze_spawn(db, run, roster, actors):
    """Bind the actual accepted spawn, preserving native species selection order."""
    wave, identities, references = _roster(run, roster)
    pairs = _validate_pairs(identities, references, actors)
    old = _stored(db, run["instance_id"], wave)
    if old:
        stored = _validate_pairs(
            identities,
            references,
            ((row["actor_id"], row["species_reference"]) for row in old),
        )
        if dict(stored) != dict(pairs):
            raise ValueError("Rift wave replay changed actor/species associations")
        return stored
    _write(db, run["instance_id"], wave, pairs, "native_spawn")
    return pairs


def verify_replay(db, run, roster, actors):
    """Check a known association; do not guess/backfill an old array pair."""
    wave, identities, references = _roster(run, roster)
    pairs = _validate_pairs(identities, references, actors)
    old = _stored(db, run["instance_id"], wave)
    if old and dict(
        _validate_pairs(
            identities,
            references,
            ((row["actor_id"], row["species_reference"]) for row in old),
        )
    ) != dict(pairs):
        raise ValueError("Rift wave replay changed actor/species associations")


def _checkpoint_pairs(fight, run, roster, identities, references):
    from wakfu_server.combat_reward_context import _summon
    from wakfu_server.combat_encounter_roles import assigned_roles

    state, sources = getattr(fight, "rift_wave_state", None), getattr(
        fight, "rift_monsters", None
    )
    if (
        fight.id != run["fight_id"]
        or not isinstance(state, dict)
        or state.get("instance_id") != run["instance_id"]
        or not isinstance(sources, dict)
    ):
        raise ValueError("Legacy rift associations require their actual checkpoint")
    source_pairs = {}
    npc_team = assigned_roles(fight).npc_team
    for identity in identities:
        source, actor = sources.get(identity), fight.actors.get(identity)
        if (
            not isinstance(source, dict)
            or actor is None
            or actor.id != identity
            or actor.controlled
            or actor.team != npc_team
            or _summon(actor)
            or source.get("id") != identity
            or type(source.get("ref")) is not int
            or source["ref"] <= 0
            or source.get("instance_id") != run["instance_id"]
            or source.get("level") != actor.effective_level
        ):
            raise ValueError("Legacy rift actor lacks its trusted native source")
        source_pairs[identity] = source["ref"]
    if Counter(source_pairs.values()) != Counter(references):
        raise ValueError("Legacy rift sources differ from the frozen species pool")
    # Later waves retain their exact accepted ordered birth facts. A current
    # first wave also carries its actual order. Neither order comes from SQL's
    # independently sorted legacy actor_ids array.
    candidates = [
        (row.get("next_actor_ids"), row.get("next_species_refs"))
        for row in state.get("staged_receipts", ())
        if row.get("completed_wave") == roster["wave"] - 1
    ]
    if state.get("wave") == roster["wave"] and state.get("wave_actor_ids") is not None:
        candidates.append((state["wave_actor_ids"], state.get("wave_species_refs")))
    selected = None
    for ids, refs in candidates:
        if (
            not isinstance(ids, (list, tuple))
            or not isinstance(refs, (list, tuple))
            or len(ids) != len(refs)
        ):
            raise ValueError("Legacy rift checkpoint has malformed birth facts")
        pairs = _validate_pairs(identities, references, zip(ids, refs))
        if dict(pairs) != source_pairs:
            raise ValueError("Legacy rift birth facts disagree with actual sources")
        selected = pairs if selected is None else selected
    if selected is not None:
        return selected
    # Older first-wave snapshots have no separate initial ordered birth row.
    # Exact actor->species pairs still come from the trusted checkpoint. Frozen
    # selection order assigns ordinals; equal species are interchangeable here.
    by_reference = defaultdict(deque)
    for identity, reference in sorted(source_pairs.items()):
        by_reference[reference].append(identity)
    return tuple(
        (by_reference[reference].popleft(), reference) for reference in references
    )


def load(db, run, roster, *, fight=None):
    """Read canonical pairs, or recover an old row from its real checkpoint."""
    wave, identities, references = _roster(run, roster)
    stored = _stored(db, run["instance_id"], wave)
    if stored:
        if [row["ordinal"] for row in stored] != list(range(len(stored))):
            raise ValueError("Rift association ordinals are incomplete")
        return _validate_pairs(
            identities,
            references,
            ((row["actor_id"], row["species_reference"]) for row in stored),
        )
    if fight is None:
        raise ValueError(
            "Legacy rift roster needs trusted checkpoint association recovery"
        )
    pairs = _checkpoint_pairs(fight, run, roster, identities, references)
    _write(db, run["instance_id"], wave, pairs, "checkpoint_recovery")
    return pairs


def rosters(db, run, *, fight=None):
    """Return durable wave identity sets plus explicit canonical associations."""
    result = []
    for row in db.execute(
        "SELECT wave,actor_ids,species_refs FROM rift_wave_rosters WHERE instance_id=%s ORDER BY wave",
        (run["instance_id"],),
    ).fetchall():
        result.append(dict(row, actor_species_pairs=load(db, run, row, fight=fight)))
    return tuple(result)
