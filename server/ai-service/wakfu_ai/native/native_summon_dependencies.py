"""Imported NPC dependencies scoped to an attested registered caster chain."""
from .native_actor_source import registered_source


def registered_dependency_enabled(fight, actor, monsters, policy, spell, level):
    """Authorize a dependency book without enabling its ordinary wild profile.

    Player/class roots and unrelated registrations never gain NPC imports.
    The immutable policy is produced from the original typed dependency graph;
    actual creation, ownership and descriptor level remain live authorities.
    """
    from wakfu_server.combat_summon_spellbook import actor_action_book

    registrations = getattr(fight, "native_summon_registrations", {})
    if (
        fight.actors.get(actor.id) is not actor
        or actor.controlled
        or actor.id not in registrations
        or type(spell) is not int
        or type(level) is not int
        or not isinstance(policy, dict)
        or policy.get("schema") != "native-npc-activation-v1"
    ):
        return False
    chain = []
    seen = set()
    current = actor
    while current.id in registrations:
        if current.id in seen or current.controlled:
            return False
        seen.add(current.id)
        descriptor = registered_source(current, registrations[current.id])
        if (
            descriptor.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
        ):
            return False
        book = actor_action_book(current)
        if not isinstance(book.get("actions"), list):
            return False
        chain.append((descriptor, book))
        current = fight.actors.get(descriptor.get("caster_id"))
        if current is None:
            return False
    root = monsters.get(current.id)
    if (
        current.controlled
        or not isinstance(root, dict)
        or root.get("id") != current.id
        or type(root.get("ref")) is not int
    ):
        return False
    parents = policy.get("enabled_monsters")
    entry = parents.get(str(root["ref"])) if isinstance(parents, dict) else None
    if (
        not isinstance(entry, dict)
        or type(entry.get("min_level")) is not int
        or type(entry.get("max_level")) is not int
        or not entry["min_level"] <= current.effective_level <= entry["max_level"]
        or not isinstance(entry.get("spell_ids"), list)
        or not entry["spell_ids"]
    ):
        return False
    scopes = entry.get("registered_summon_profiles")
    if not isinstance(scopes, dict):
        return False
    for descriptor, book in chain:
        scope = scopes.get(str(descriptor["ref"]))
        if (
            not isinstance(scope, dict)
            or type(scope.get("min_level")) is not int
            or type(scope.get("max_level")) is not int
            or not 0
            <= scope["min_level"]
            <= descriptor["level"]
            <= scope["max_level"]
            <= 32767
            or (
                "descriptor_levels" in scope
                and (
                    not isinstance(scope["descriptor_levels"], list)
                    or any(
                        type(value) is not int for value in scope["descriptor_levels"]
                    )
                    or descriptor["level"] not in scope["descriptor_levels"]
                )
            )
            or not isinstance(scope.get("spell_ids"), list)
            or any(type(value) is not int for value in scope["spell_ids"])
            or {action["reference"] for action in book["actions"]}
            != set(scope["spell_ids"])
        ):
            return False
    return any(
        action["reference"] == spell and action["level"] == level
        for action in chain[0][1]["actions"]
    )
