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
    from .combat_ai_capability_projection import advisory_effect

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
        effect = advisory_effect(
            effects,
            reference,
            pending=(
                following
                for following, parents in reversed(stack)
                if following not in visited and following not in parents
            ),
            remaining=max_nodes - len(visited),
        )
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
                from .combat_definitions import effect_profile
                from .combat_ai_capability_projection import selected_state_roots

                parameters = effect_profile(effect, level)["parameters"]
                if states is None or len(parameters) < 2:
                    raise ValueError("Missing state metadata")
                state_roots = selected_state_roots(states, parameters[0], parameters[1])
                stack.extend((root, ancestors | {reference}) for root in state_roots)
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
    from .combat_native_spell_casting import native_casting_table
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_static_catalogs import characteristic_registry

    from . import combat_native_spell_casting as casting_module
    from .combat_published_catalogs import static_catalog_descriptor

    getter = getattr(casting_module, "catalog", None)
    source = getter() if type(level) is int and level > 0 and callable(getter) else None
    descriptor = None if source is None else static_catalog_descriptor(source)
    selected = None
    if (
        descriptor is not None
        and descriptor["revision"] != "0" * 64
        and source.representation == "native_json"
    ):
        try:
            selected = casting_module.selected_casting_projection(
                spell, level, casting=source
            )
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    if selected is None:
        # Private/zero/malformed tables keep their original advisory behavior.
        try:
            options = {} if source is None else {"casting": source}
            row, index = native_casting_table(spell, level, **options)
        except ValueError:
            return dict(
                spellId=spell,
                level=level,
                minimum=0,
                maximum=0,
                tags=["unknown"],
                unknownDependencies=["missing_casting_table"],
                conditional=True,
            )
        minimum, maximum, roots = row["levels"][index]
        envelope = [(minimum, maximum)] + [
            tuple(rule["ranges"][index]) for rule in row["conditional"]
        ]
        conditional = bool(row["conditional"])
    else:
        minimum, maximum = selected.baseline[3:5]
        roots = selected.roots
        envelope = [(minimum, maximum)] + [
            tuple(rule[1][3:5]) for rule in selected.rules
        ]
        conditional = bool(selected.rules)
    compiled = npc_runtime_catalog()
    semantic = classify_roots(
        roots,
        compiled.effects,
        states=compiled.source_states,
        registry=characteristic_registry().get("effects", {}),
        level=level,
    )
    # The projection includes every conditional native range; legality stays
    # with the current native preview rather than these advisory bounds.
    return dict(
        spellId=spell,
        level=level,
        minimum=min(lo for lo, hi in envelope),
        maximum=max(hi for lo, hi in envelope),
        conditional=conditional or semantic["conditional"],
        tags=semantic["tags"],
        unknownDependencies=semantic["unknownDependencies"],
    )


def prepare_spell_capabilities(pairs):
    """Batch mandatory static books without changing any classifier traversal.

    Each spell retains its original DFS, ancestor/cycle checks and 128-node
    limit. Only verified record reception is shared between those traversals;
    ordinary describe_spell still computes every final capability result.
    """
    from . import combat_native_spell_casting as casting
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_ai_capability_projection import (
        _identity,
        advisory_effect,
        selected_state_roots,
        prefetch_effects,
        forest_prepared,
        mark_forest_prepared,
    )
    from .combat_definitions import effect_profile

    source = casting.catalog()
    casting_identity = _identity(source)
    if casting_identity is None or source.representation != "native_json":
        return False
    compiled = npc_runtime_catalog()
    identities = (
        casting_identity,
        _identity(compiled.effects),
        _identity(compiled.source_states.get("states")),
        _identity(compiled.source_states.get("effects")),
    )
    if any(identity is None for identity in identities):
        return False
    frames, prepared = [], []
    for spell, level in dict.fromkeys(pairs):
        if type(level) is not int or level <= 0:
            continue  # Private and explicit zero books retain their live path.
        key = ("forest", identities, str(spell), level)
        if forest_prepared(key):
            continue
        selected = casting.selected_casting_projection(spell, level, casting=source)
        frames.append(
            dict(
                stack=[(root, frozenset()) for root in selected.roots],
                visited=set(),
                level=level,
            )
        )
        prepared.append(key)
    while frames:
        pending, following = [], []
        for frame in frames:
            while frame["stack"] and len(frame["visited"]) < 128:
                reference, ancestors = frame["stack"].pop()
                if reference in ancestors or reference in frame["visited"]:
                    continue
                frame["visited"].add(reference)
                pending.append((frame, reference, ancestors))
                break
        if not pending:
            break
        prefetch_effects(compiled.effects, (reference for _, reference, _ in pending))
        for frame, reference, ancestors in pending:
            effect = advisory_effect(compiled.effects, reference)
            if effect is not None:
                if effect.get("effect_class") == 304:
                    try:
                        parameters = effect_profile(effect, frame["level"])[
                            "parameters"
                        ]
                        if len(parameters) < 2:
                            raise ValueError("Missing state metadata")
                        roots = selected_state_roots(
                            compiled.source_states, parameters[0], parameters[1]
                        )
                        frame["stack"].extend(
                            (root, ancestors | {reference}) for root in roots
                        )
                    except (ValueError, KeyError, TypeError):
                        pass  # The normal classifier retains its unknown label.
                frame["stack"].extend(
                    (child, ancestors | {reference})
                    for child in effect.get("children", ())
                )
            if frame["stack"] and len(frame["visited"]) < 128:
                following.append(frame)
        frames = following
    for key in prepared:
        mark_forest_prepared(key)
    return bool(prepared)


def spell_capabilities(fight, monsters):
    from .combat_npc_spell import owned_spells

    return [
        deepcopy(describe_spell(spell, level))
        for spell, level in sorted(owned_spells(fight, monsters).items())
    ]


def target_affinity(capability, actor, target, *, fight=None):
    """Cheap candidate priority; exact effects still decide the useful target."""
    tags = set(capability.get("tags", ()))
    if fight is None:
        ally = actor.team == target.team
    else:
        from .combat_effective_control import effective_affiliation

        ally = effective_affiliation(fight, actor) == effective_affiliation(
            fight, target
        )
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
