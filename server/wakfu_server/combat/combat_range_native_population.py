"""Native eKn subclass population selection, before actor metadata projection."""
from .combat_state import Fight
from .combat_ordinary_authority import (
    OrdinaryActorAuthority,
    pure_ordinary_callback,
    _immutable_property_catalog,
)
from .combat_summon import RegisteredSummonAuthority
from .combat_global_pv_read_view import in_play_actors
from . import combat_carrying, combat_ordinary_death, combat_controller_registry

_RANGE_READERS = (
    (combat_carrying, "carrying_relations", combat_carrying.carrying_relations),
    (
        combat_ordinary_death,
        "owned_fighter_guards",
        combat_ordinary_death.owned_fighter_guards,
    ),
    (
        combat_controller_registry,
        "current_native_controller",
        combat_controller_registry.current_native_controller,
    ),
)


_ORDINARY = {
    name: getattr(OrdinaryActorAuthority, name)
    for name in (
        "__call__",
        "condition_projection",
        "properties",
        "world_properties",
        "_condition_fight_properties",
        "_condition_world_properties",
    )
}
_REGISTERED = {
    name: getattr(RegisteredSummonAuthority, name)
    for name in (
        "__call__",
        "condition_projection",
        "properties",
        "world_properties",
        "_ordinary_view",
        "_call_ordinary",
        "_condition_ordinary_property",
        "_condition_fight_properties",
        "_condition_world_properties",
    )
}
_IN_PLAY = Fight._in_play
_RECIPIENT_FACTS = OrdinaryActorAuthority._recipient_creation_facts


def _local_retired_population(fight, authority, actor):
    """A selected ordinary recipient needs no filtered summon roster."""
    registrations = getattr(fight, "native_summon_registrations", {})
    companions = getattr(fight, "native_companion_sources", {})
    return (
        type(registrations) is dict
        and actor.id not in registrations
        and type(companions) is dict
        and str(actor.id) not in companions
        and Fight.__getattribute__ is object.__getattribute__
        and RegisteredSummonAuthority.__getattribute__ is object.__getattribute__
        and OrdinaryActorAuthority.__getattribute__ is object.__getattribute__
        and "__getattr__" not in RegisteredSummonAuthority.__dict__
        and "__getattr__" not in OrdinaryActorAuthority.__dict__
    )


def _native_range_ordinary(fight, authority):
    """Return None for custom/legacy providers; never memoize a partial roster."""
    if (
        type(fight) is not Fight
        or not hasattr(fight, "native_global_pv_collections")
        or "_in_play" in vars(fight)
        or Fight._in_play is not _IN_PLAY
    ):
        return None
    from .combat_retained_collections import OwnedMap, bound_collections
    from .combat_npc_spellbook import ordinary_npc_spellbook

    actors = fight.actors
    if type(actors) is OwnedMap:
        if bound_collections(vars(fight)) is None:
            return None
        if any(
            name in vars(actors) or getattr(OwnedMap, name) is not getattr(dict, name)
            for name in ("values", "get", "__iter__", "__getitem__")
        ):
            return None
    elif type(actors) is not dict:
        return None
    ordinary = authority
    if type(authority) is RegisteredSummonAuthority:
        if any(
            name in vars(authority)
            or getattr(RegisteredSummonAuthority, name) is not method
            for name, method in _REGISTERED.items()
        ):
            return None
        ordinary = authority.ordinary
    elif type(authority) is not OrdinaryActorAuthority:
        return None
    if (
        ordinary.npc_spellbook is not None
        and ordinary.npc_spellbook is not ordinary_npc_spellbook
    ):
        return None
    if (
        ordinary.catalog is not _immutable_property_catalog()
        or not pure_ordinary_callback(ordinary, ordinary)
        or any(
            name in vars(ordinary)
            or getattr(OrdinaryActorAuthority, name) is not method
            for name, method in _ORDINARY.items()
        )
    ):
        return None
    return ordinary


def native_range_population(fight, authority):
    """Return None for custom providers, otherwise native IN_PLAY actors."""
    if _native_range_ordinary(fight, authority) is None:
        return None
    return in_play_actors(fight)


def retired_range_facts(fight, authority, actor):
    """Project only ordinary OUT range facts, never PA or executable authority.

    Native state(False) predicates observe these actors but do not read their
    damage characteristics, spellbooks, cosmetics or social services. Supplied
    authority hooks and nonordinary managers retain the complete legacy path.
    The caller must use the result immediately, without intervening callbacks.
    """
    from .combat_state import Actor
    from .combat_carrying import carry_population_scope

    if (
        type(actor) is not Actor
        or Actor.__getattribute__ is not object.__getattribute__
        or "__getattr__" in Actor.__dict__
        or actor.hp != 0
        or actor.controlled is not False
        or getattr(actor, "pve_withdrawn", False)
        or any(
            type(vars(actor).get(name)) is not dict
            for name in ("effect_stats", "effect_maxima", "effect_minima")
        )
        or type(vars(actor).get("effect_frozen")) not in (set, frozenset)
        or getattr(actor, "native_summon_source", None) is not None
        or getattr(actor, "native_companion_source", None) is not None
    ):
        return None
    if any(
        getattr(module, name) is not method for module, name, method in _RANGE_READERS
    ):
        return None
    ordinary = _native_range_ordinary(fight, authority)
    if (
        ordinary is None
        or "_recipient_creation_facts" in vars(ordinary)
        or OrdinaryActorAuthority._recipient_creation_facts is not _RECIPIENT_FACTS
    ):
        return None
    if type(authority) is RegisteredSummonAuthority:
        with carry_population_scope(fight):
            # The same selected-recipient route used by native event delivery.
            # Carry scope retains real summon partners; life/controller tables
            # and selected source identity are shared by the former shallow view.
            view = (
                fight
                if _local_retired_population(fight, authority, actor)
                else authority._ordinary_view(fight, _pure_callback=ordinary)
            )
            facts = ordinary._recipient_creation_facts(view, actor)
    else:
        facts = ordinary._recipient_creation_facts(fight, actor)
    if facts is None:
        return None
    player, source, carrying, properties, life = facts
    if life["baK"] is not True:
        return None
    if (
        type(source.get("ref")) is not int
        or type(carrying.get("is_carried")) is not bool
        or type(life.get("baF")) is not bool
    ):
        raise ValueError("Missing native retired range facts")
    from types import SimpleNamespace

    # These are the exact fields consumed by RangeFighter below. In particular
    # in_play is the current native status, not inferred from numerical HP.
    return (
        SimpleNamespace(
            native_in_play=life["baF"],
            breed_id=source["ref"],
            is_carried=carrying["is_carried"],
            native_actor_type=1,
        ),
        properties,
    )


from .combat_state_ledger import StateLedger, RunningState

_STATE_ENTRIES = StateLedger.__dict__["entries"]
_STATE_LEDGER_GET = StateLedger.__getattribute__
_RUNNING_STATE_GET = RunningState.__getattribute__


def native_state_no_match(fight, authority, actor, reference, level, caster):
    """A native ledger negative cannot gain a match through Qf registration.

    Only negatives short-circuit. Matching or opaque ledgers retain the complete
    registered-carrier query and all normal actor projections, in original order.
    """
    from .combat_state import Actor

    if (
        type(reference) is not int
        or type(level) is not int
        or (caster is not None and type(caster) is not int)
        or type(actor) is not Actor
        or Actor.__getattribute__ is not object.__getattribute__
        or "state_ledger" in Actor.__dict__
        or "__getattr__" in Actor.__dict__
        or StateLedger.__getattribute__ is not _STATE_LEDGER_GET
        or _STATE_LEDGER_GET is not object.__getattribute__
        or StateLedger.__dict__.get("entries") is not _STATE_ENTRIES
        or "_entries" in StateLedger.__dict__
        or "__getattr__" in StateLedger.__dict__
        or RunningState.__getattribute__ is not _RUNNING_STATE_GET
        or _RUNNING_STATE_GET is not object.__getattribute__
        or any(
            name in RunningState.__dict__
            for name in ("reference", "level", "caster_id", "__getattr__")
        )
    ):
        return False
    ledger = actor.state_ledger
    if type(ledger) is not StateLedger or type(ledger.entries) is not tuple:
        return False
    for state in ledger.entries:
        if type(state) is not RunningState or any(
            type(value) is not int
            for value in (state.reference, state.level, state.caster_id)
        ):
            return False
        if (
            state.reference == reference
            and (level < 0 or state.level == level)
            and (caster is None or state.caster_id == caster)
        ):
            return False
    if any(
        getattr(module, name) is not method for module, name, method in _RANGE_READERS
    ):
        return False
    ordinary = _native_range_ordinary(fight, authority)
    if ordinary is None:
        return False
    # Pure native method identities do not certify supplied source mappings.
    # Do not skip an observable custom source lookup or summon authority hook.
    characters = ordinary.characters
    monsters = (
        ordinary.monsters
        if getattr(fight, "rift_wave_state", None) is None
        else getattr(fight, "rift_monsters", None)
    )
    companions = getattr(fight, "native_companion_sources", {})
    registrations = getattr(fight, "native_summon_registrations", {})
    if (
        type(characters) is not dict
        or type(monsters) is not dict
        or type(companions) is not dict
        or type(registrations) is not dict
        or actor.id in registrations
        or str(actor.id) in companions
        or getattr(actor, "native_summon_source", None) is not None
        or getattr(actor, "native_companion_source", None) is not None
    ):
        return False
    source = (
        characters.get(actor.id) if actor.id in characters else monsters.get(actor.id)
    )
    return type(source) is dict
