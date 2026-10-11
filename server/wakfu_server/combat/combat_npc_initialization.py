"""Ordinary fresh bje.aQc initial states from activated native descriptors.

Native evidence: big.a(eGH) consumes cle short triples after bje.c(blj),
with SELF caster, null PL, flag==0 rBq and unconditional rBr. This is a
constructor boundary, before controller/team/QI insertion, not a combat turn.
Finite clocks deliberately retain the existing unsupported-timeline rejection.
"""
from dataclasses import asdict, replace


def initial_plans(fight, monsters):
    if not monsters:
        return {}
    from .combat_npc_attack import npc_spell_catalog
    from .combat_summon_initial_states import initial_state_plan

    policy = npc_spell_catalog().get("activation_policy")
    if policy is None:
        return {}
    if policy.get("schema") != "native-npc-activation-v1":
        raise ValueError("Invalid NPC initialization activation policy")
    result = {}
    for identity, monster in monsters.items():
        actor = fight.actors[identity]
        row = policy["enabled_monsters"].get(str(monster["ref"]))
        if row is None:
            continue
        if not row["min_level"] <= actor.effective_level <= row["max_level"]:
            continue
        raw = row.get("initial_state_triples", [])
        plan = initial_state_plan(raw, actor.effective_level)
        if plan:
            result[identity] = (monster["ref"], tuple(raw), plan)
    return result


def constructor_stat_context(fight, invocation):
    """Only actual detached SELF constructors may execute without a turn."""
    from .combat_summon_initialization import detached_actor

    actor = detached_actor(fight, invocation.caster_id)
    return actor is not None and invocation.target_id == actor.id


def _runtime(monsters, actor_id):
    import random
    from .combat_server_spell import (
        OrdinaryActorAuthority,
        ordinary_cast_authority,
        NativeEffectTimingProvider,
        NativeServerRuntimeAdapter,
        NativeEffectRuntimeFactory,
        characteristic_registry,
        states_catalog,
    )
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_random_group import RandomGroupAuthority
    from .combat_relative_probability import RelativeGroupAuthority

    actors = OrdinaryActorAuthority(
        characters={},
        monsters=monsters,
        decks={},
        excluded_decks={},
    )
    from .combat_summon import RegisteredSummonAuthority

    actors = RegisteredSummonAuthority(actors)
    states = states_catalog()
    rng = random.Random()
    authority = ordinary_cast_authority(
        actors=actors,
        timing=NativeEffectTimingProvider(states),
        rng=rng,
        critical=False,
    )
    adapter = NativeServerRuntimeAdapter(
        actor_authority=actors,
        cast=authority,
        viewer_id=actor_id,
    )
    compiled = npc_runtime_catalog(imported=True)
    factory = NativeEffectRuntimeFactory(
        effects=compiled.source_effects,
        state_catalog=states,
        characteristic_registry=characteristic_registry(),
        compiled_effects=compiled,
        action_id=1,
        contexts=adapter.contexts(),
        displacement_authority=actors,
        summon_authority=actors,
        transaction_rng=rng,
    )
    factory.native_rail_movement_authority = actors
    factory.relative_group_children = RelativeGroupAuthority(
        effects=factory.effects,
        actor_authority=actors,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randint(1, total),
        draw_fraction=lambda fraction: rng.random() < fraction,
    )
    factory.random_group_children = RandomGroupAuthority(
        effects=factory.effects,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randrange(total),
    )
    return factory, actors


def initialize_ordinary_npcs(fight, monsters, plans):
    """Mutate only the caller-owned private constructor preview."""
    from .combat_summon_creation import native_fresh_summon_authority
    from .combat_summon_initialization import (
        detached_summon_scope,
        install_initial_states,
    )
    from .combat_native_death_status import initialize_fresh_bje_death_status
    from .combat_property_stack import add_property

    receipts = {}
    actor_order = tuple(fight.actors)
    for identity, (reference, raw, plan) in plans.items():
        actor = fight.actors[identity]
        factory, actors = _runtime(monsters, identity)
        from .combat_ordinary_authority import native_property_catalog

        profile = native_property_catalog()["npc"][str(reference)]
        for kind in ("fight", "world"):
            counts = {}
            for prop in profile[kind + "_properties"]:
                add_property(counts, prop)
            setattr(actor, "native_" + kind + "_property_counts", counts)
            setattr(actor, "native_" + kind + "_properties", frozenset(counts))
        initialize_fresh_bje_death_status(actor)
        authority = replace(
            native_fresh_summon_authority(actor, reference),
            is_summon=False,
            summon_root_id=actor.id,
            targeting=dict(
                native_fresh_summon_authority(actor, reference).targeting,
                bEe=42 not in actor.native_fight_properties,
                UNTARGETTABLE_BY_OTHER=21 in actor.native_fight_properties,
            ),
        )
        applications = []
        team = actor.team
        del fight.actors[identity]
        actor.team = -1
        try:
            with detached_summon_scope(fight, actor, authority):
                # The client bje constructor performs these same notifications.
                # Keep all authoritative state/effect writes, discard its outbox.
                install_initial_states(
                    fight,
                    actor,
                    plan,
                    runtime_factory=factory,
                    application_results=applications,
                )
                if len(applications) != len(plan) or any(
                    item["applied"] is not True for item in applications
                ):
                    raise ValueError("Native ordinary initial state was not applied")
        finally:
            actor.team = team
            fight.actors[identity] = actor
            fight.actors = {key: fight.actors[key] for key in actor_order}
        receipts[identity] = dict(
            ref=reference,
            descriptor_level=actor.effective_level,
            raw_triples=list(raw),
            resolved_states=[asdict(item) for item in plan],
            applications=applications,
            initialized=True,
        )
    fight.native_npc_initialization_receipts = receipts
