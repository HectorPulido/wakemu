"""Advisory native spell capabilities; never authorizes or simulates a cast.

Capabilities are multi-label. Unknown effects/conditions remain explicit and
must be resolved by the transaction dispatcher, not skipped by this metadata.
"""
from functools import lru_cache
from copy import deepcopy


def classify_roots(
    roots, effects, *, states=None, registry=None, level=1, max_nodes=128
):
    from .combat_damage_healing import DAMAGE_FAMILIES, HEAL_ELEMENTS
    from .combat_displacement import FAMILIES as DISPLACEMENTS

    tags, unknown, visited = set(), set(), set()
    stack = [(reference, frozenset()) for reference in roots]
    conditional = False
    while stack:
        reference, ancestors = stack.pop()
        if reference in ancestors:
            unknown.add("cyclic_effect_tree")
            continue
        if reference in visited:
            continue
        if len(visited) >= max_nodes:
            unknown.add("capability_node_limit")
            break
        visited.add(reference)
        effect = effects.get(str(reference))
        if effect is None:
            unknown.add("missing_effect:" + str(reference))
            continue
        family = effect.get("effect_class")
        conditional = conditional or bool(effect.get("criteria"))
        if family in DAMAGE_FAMILIES:
            tags.add("damage")
        elif family in HEAL_ELEMENTS:
            tags.add("heal")
        elif family in DISPLACEMENTS:
            tags.add("displacement")
        elif family == 307:
            tags.add("summon")
        elif family in (910, 912, 999):
            tags.add("area")
        elif family == 304:
            tags.add("state")
            # State linkage is level-dependent; no benefit is inferred solely
            # from application or the name of a state.
            try:
                from .combat_definitions import effect_profile, state_profile

                parameters = effect_profile(effect, level)["parameters"]
                if states is None or len(parameters) < 2:
                    raise ValueError("Missing state metadata")
                state = state_profile(states, parameters[0], parameters[1])
                stack.extend(
                    (root, ancestors | {reference}) for root in state["effects"]
                )
            except (ValueError, KeyError, TypeError):
                unknown.add("unresolved_state")
        elif registry is not None and str(family) in registry:
            row = registry[str(family)]
            statistic, operation = row.get("fixed_stat_id"), row.get("operation")
            if statistic == 97 and operation == "gain_current":
                tags.add("armor")
            elif statistic in (2, 3, 4) and operation == "lose_current":
                tags.add("control")
            elif operation == "gain_current":
                tags.add("buff")
            elif operation == "lose_current":
                tags.add("debuff")
            else:
                tags.add("special")
        else:
            # Containers may add children with useful capabilities; the
            # unknown container never certifies that those children execute.
            unknown.add("unclassified_family:" + str(family))
        if effect.get("native_area") or effect.get("area"):
            tags.add("area")
        stack.extend(
            (child, ancestors | {reference}) for child in effect.get("children", ())
        )
    if not tags and not unknown:
        unknown.add("empty_effect_tree")
    if unknown:
        tags.add("unknown")
    return dict(
        tags=sorted(tags), unknownDependencies=sorted(unknown), conditional=conditional
    )


@lru_cache(maxsize=1024)
def describe_spell(spell, level):
    from .combat_native_spell_casting import catalog
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_static_catalogs import characteristic_registry

    row = catalog().get(str(spell))
    if row is None or not 1 <= level <= len(row["levels"]):
        return dict(
            spellId=spell,
            level=level,
            minimum=0,
            maximum=0,
            tags=["unknown"],
            unknownDependencies=["missing_casting_table"],
            conditional=True,
        )
    minimum, maximum, roots = row["levels"][level - 1]
    compiled = npc_runtime_catalog()
    semantic = classify_roots(
        roots,
        compiled.effects,
        states=compiled.source_states,
        registry=characteristic_registry().get("effects", {}),
        level=level,
    )
    # Candidate pruning uses the envelope of every conditional native table.
    # It never drops a cast solely because baseline range would exclude it.
    envelope = [(minimum, maximum)] + [
        tuple(rule["ranges"][level - 1]) for rule in row["conditional"]
    ]
    return dict(
        spellId=spell,
        level=level,
        minimum=min(lo for lo, hi in envelope),
        maximum=max(hi for lo, hi in envelope),
        conditional=bool(row["conditional"]) or semantic["conditional"],
        tags=semantic["tags"],
        unknownDependencies=semantic["unknownDependencies"],
    )


def spell_capabilities(fight, monsters):
    from .combat_npc_spell import owned_spells

    return [
        deepcopy(describe_spell(spell, level))
        for spell, level in sorted(owned_spells(fight, monsters).items())
    ]


def target_affinity(capability, actor, target):
    """Cheap candidate priority; exact effects still decide the useful target."""
    tags = set(capability.get("tags", ()))
    ally = actor.team == target.team
    offensive = bool(tags & {"damage", "control", "debuff", "displacement"})
    supportive = bool(tags & {"heal", "armor", "buff"})
    if ally and "heal" in tags and target.hp < target.max_hp:
        return 0, target.hp - target.max_hp, target.id
    if not ally and offensive:
        return 0, target.hp, target.id
    if ally and supportive:
        return 1, target.hp - target.max_hp, target.id
    # Mixed/unknown capabilities retain alternate teams rather than being
    # locked into a monster role. The preview will exclude hostile healing.
    return 2, target.hp, target.id
