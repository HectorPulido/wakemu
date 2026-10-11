"""Fresh Wakemu controller assignment for activated ordinary NPCs.

Native eGj.fqL delegates to eGZ.pHH; po.SX serializes that actual mutable
control value. Assignment here represents the real server tactical controller,
not an intrinsic creature property or a cast-criterion override.
"""


def initial_ai_actors(fight, monsters):
    if not monsters:
        return frozenset()
    from .combat_npc_attack import npc_spell_catalog
    from .combat_npc_activation import imports_enabled
    from wakfu_server.monsters import native_abilities

    policy = npc_spell_catalog().get("activation_policy")
    if policy is None:
        return frozenset()
    result = set()
    summons = getattr(fight, "native_summon_registrations", {})
    for identity, monster in monsters.items():
        actor = fight.actors[identity]
        if (
            actor.controlled
            or identity in summons
            or getattr(actor, "native_summon_action_book", None) is not None
        ):
            continue
        # The same owned repertoire and activation gate select the real
        # NativeProvider/ai-service cast implementation for this fresh NPC.
        if any(
            imports_enabled(
                policy, monster["ref"], actor.effective_level, ability["spell_id"]
            )
            for ability in native_abilities(monster["ref"], actor.effective_level)
        ):
            result.add(identity)
    return frozenset(result)
