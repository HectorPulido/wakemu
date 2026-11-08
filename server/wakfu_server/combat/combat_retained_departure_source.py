"""Attested source metadata for an existing effect whose caster has departed.

This grants no active actor authority. Only the original retained group and
its dispatched descendants may read the captured constructor properties.
"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import fields

from .combat_runtime_adapter import NativeActorAuthority
from .combat_spell_level import NativeSpellBook


POLICY = "wakemu.retained-departure-source.v1"
_MAP_FIELDS = (
    "summon_counts_by_breed",
    "native_selected_cosmetics",
    "native_active_cosmetics",
)


def _encode_authority(authority):
    if type(authority) is not NativeActorAuthority:
        raise ValueError("Missing retained departure constructor authority")
    result = {
        field.name: deepcopy(getattr(authority, field.name))
        for field in fields(authority)
    }
    for name in ("deck_spell_ids", "excluded_deck_spell_ids"):
        result[name] = sorted(result[name])
    for name in _MAP_FIELDS:
        if result[name] is not None:
            result[name] = [[key, value] for key, value in result[name].items()]
    book = authority.native_spellbook
    if book is not None:
        if type(book) is not NativeSpellBook:
            raise ValueError("Unknown retained departure spellbook")
        result["native_spellbook"] = dict(
            levels=None
            if book.levels is None
            else list(map(list, book.levels.items())),
            progression_levels=None
            if book.progression_levels is None
            else list(map(list, book.progression_levels.items())),
            player_character=book.player_character,
            deck_cap=book.deck_cap,
        )
    for name in ("native_social_context", "native_captured_roster"):
        value = getattr(authority, name)
        if value is not None:
            result[name] = value.to_record()
    return result


def _decode_authority(record, actor):
    result = deepcopy(record)
    if set(result) != {field.name for field in fields(NativeActorAuthority)}:
        raise ValueError("Incomplete retained departure constructor snapshot")
    for name in ("deck_spell_ids", "excluded_deck_spell_ids"):
        result[name] = frozenset(result[name])
    for name in _MAP_FIELDS:
        if result[name] is not None:
            result[name] = dict(result[name])
    book = result["native_spellbook"]
    if book is not None:
        for name in ("levels", "progression_levels"):
            if book[name] is not None:
                book[name] = dict(book[name])
        result["native_spellbook"] = NativeSpellBook(**book)
    if result["native_social_context"] is not None:
        from wakfu_server.owned_social_context import OwnedSocialContext

        result["native_social_context"] = OwnedSocialContext.from_record(
            result["native_social_context"]
        ).require_owner(actor.id, actor.owner_id)
    if result["native_captured_roster"] is not None:
        from wakfu_server.captured_roster import OwnedCapturedRoster

        result["native_captured_roster"] = OwnedCapturedRoster.from_record(
            result["native_captured_roster"], expected_owner_id=actor.id
        )
    return NativeActorAuthority(**result)


def _group_identity(row):
    invocation = row["invocation"]
    return dict(
        reference=invocation["reference"],
        level=invocation["level"],
        caster_id=invocation["caster_id"],
        target_id=invocation["target_id"],
        effect_class=row["effect_class"],
        manager_target=row.get("target_id"),
        state_uid=row.get("state_uid"),
    )


def capture_departure_sources(fight, actor_ids, authority):
    departing = frozenset(actor_ids)
    groups = {}
    for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
        invocation = row["invocation"]
        caster, target = invocation["caster_id"], invocation["target_id"]
        survivor = fight.actors.get(target)
        if (
            caster in departing
            and target not in departing
            and survivor is not None
            and not getattr(survivor, "pve_withdrawn", False)
        ):
            groups.setdefault(caster, {})[str(uid)] = _group_identity(row)
    if not groups:
        return
    if not callable(getattr(authority, "condition_projection", None)):
        raise ValueError("Retained departure requires native source projection")
    records = deepcopy(getattr(fight, "native_retained_departure_sources", {}))
    for identity, grants in groups.items():
        actor = fight.actors[identity]
        if getattr(actor, "pve_withdrawn", False) or str(identity) in records:
            raise ValueError("Retained departure source was already retired")
        metadata, world, current = authority.condition_projection(fight, actor)
        if type(world) is not frozenset or type(current) is not frozenset:
            raise ValueError("Missing historical native source properties")
        records[str(identity)] = dict(
            policy=POLICY,
            actor_id=identity,
            owner_id=actor.owner_id,
            authority=_encode_authority(metadata),
            world_properties=sorted(world),
            fight_properties=sorted(current),
            groups=grants,
        )
    fight.native_retained_departure_sources = records


_ACTIVATION = ContextVar("retained_departure_activation", default=None)
_DESCENDANT = ContextVar("retained_departure_descendant", default=None)


@contextmanager
def retained_activation_scope(fight, dispatcher, invocation):
    """Bind an actual Qe root; validate authority only if metadata is read."""
    actor = fight.actors.get(invocation.caster_id)
    scope = None
    if actor is not None and getattr(actor, "pve_withdrawn", False):
        # Merely replaying a root never grants actor authority. Some native
        # effects need no source metadata; preserve their existing execution.
        # Every actual historical read still checks the captured live group.
        scope = (fight, dispatcher, invocation)
    token = _ACTIVATION.set(scope)
    descendant = _DESCENDANT.set(None)
    try:
        yield
    finally:
        _DESCENDANT.reset(descendant)
        _ACTIVATION.reset(token)


def retained_descendant_scope(dispatcher, invocation, ancestors):
    """Bind fresh children to their declared, currently executing root chain."""
    activation = _ACTIVATION.get()
    if activation is None:
        return nullcontext()
    proof = None
    if activation is not None and activation[1] is dispatcher:
        fight, _dispatcher, root = activation
        chain = (*ancestors, invocation.reference)
        if chain and chain[0] == root.reference:
            valid = True
            for parent, child in zip(chain, chain[1:]):
                effect = dispatcher.effects.get(str(parent))
                if effect is None or child not in effect.get("children", ()):
                    valid = False
                    break
            if valid and invocation.caster_id == root.caster_id:
                proof = (activation, invocation)

    @contextmanager
    def bound():
        token = _DESCENDANT.set(proof)
        try:
            yield
        finally:
            _DESCENDANT.reset(token)

    return bound()


def _descendant_root_uid(fight, actor, invocation):
    proof = _DESCENDANT.get()
    if proof is None:
        return None
    activation, executing = proof
    if (
        activation is not _ACTIVATION.get()
        or activation[0] is not fight
        or activation[2].caster_id != actor.id
        or invocation.reference != executing.reference
        or invocation.level != executing.level
        or invocation.caster_id != executing.caster_id
        or invocation.state_uid != executing.state_uid
    ):
        return None
    return activation[2].base_uid


def retained_departure_source(fight, actor, invocation):
    if not getattr(actor, "pve_withdrawn", False):
        return None
    from .combat_pve_departure import retired_pve_actor_ids

    if fight.actors.get(actor.id) is not actor or actor.id not in retired_pve_actor_ids(
        fight
    ):
        raise ValueError("Unattested retained departure source")
    record = getattr(fight, "native_retained_departure_sources", {}).get(str(actor.id))
    uid = getattr(invocation, "base_uid", None)
    if uid is None:
        uid = _descendant_root_uid(fight, actor, invocation)
    if (
        not isinstance(record, dict)
        or record.get("policy") != POLICY
        or record.get("actor_id") != actor.id
        or record.get("owner_id") != actor.owner_id
        or getattr(invocation, "caster_id", None) != actor.id
        or getattr(invocation, "target_id", None) == actor.id
        or type(uid) is not int
        or uid <= 0
    ):
        raise ValueError("Missing exact retained departure source proof")
    expected = record["groups"].get(str(uid))
    row = getattr(fight, "native_owned_group_effects", {}).get(uid)
    if expected is None or row is None or _group_identity(row) != expected:
        raise ValueError("Retained departure invocation lacks its original group")
    if expected["caster_id"] != actor.id:
        raise ValueError("Retained departure group caster changed")
    return (
        _decode_authority(record["authority"], actor),
        frozenset(record["world_properties"]),
        frozenset(record["fight_properties"]),
    )
