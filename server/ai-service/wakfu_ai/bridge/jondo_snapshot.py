"""Compact, source-bound advisory facts for the separate Jondo selector."""
from collections import deque
from collections.abc import Mapping
from copy import copy
import ast
import random
import uuid

from ..native.native_control import effective_affiliation
from ..native.native_deadline import check, clock_now


_MECHANIC_MONSTERS = frozenset(
    (2431, 2448, 2977, 3022, 3870, 4251, 4280, 5039, 5040, 5500, 5664)
)
_MECHANIC_AREAS = frozenset((655, 1085, 1086, 1173))


def mechanic_areas(fight, actor, indices, *, hidden=()):
    """Project installed, visible mechanic areas without refreshing live rows."""
    from wakfu_server.combat_area_authority import area_guards
    from wakfu_server.combat_effect_area_geometry import (
        contains_area_actor,
        refresh_area_geometry,
    )

    result = []
    for identity, row in getattr(fight, "native_effect_areas", {}).items():
        check()
        if (
            not isinstance(row, dict)
            or row.get("reference") not in _MECHANIC_AREAS
            or row.get("uid") != identity
            or row.get("remaining_activations", -1) == 0
            or row.get("executing", False)
            or row.get("hidden", False)
            or row.get("native_hidden", False)
            or row.get("owner_id") in hidden
        ):
            continue
        try:
            if area_guards(fight, identity) != dict(baG=False, baK=False, baF=True):
                continue
            private = dict(row)
            refresh_area_geometry(fight, private)
            anchor = indices.get(tuple(private["cell"]))
            if anchor is None:
                continue
            overlap = [
                index
                for cell, index in indices.items()
                if contains_area_actor(private, cell, actor.physical_radius)
            ]
        except (ValueError, TypeError, KeyError):
            # Missing constructor/geometry authority is not a guessed area.
            continue
        result.append(
            dict(
                reference=row["reference"],
                cell=anchor,
                cells=overlap,
                ownerId=row.get("owner_id"),
            )
        )
    return result


def special_aim_cells(actor, indices, visible, spells):
    """Bound empty-cell suggestions around observed actors, never native previews."""
    from wakfu_server.combat_obstacle_condition import footprint

    if not any(
        spell.get("needsFreeCell") and spell.get("needsLineOfSight") for spell in spells
    ):
        return []
    anchors = [tuple(actor.position)]
    anchors.extend(
        tuple(candidate.position)
        for candidate in visible
        if candidate.hp > 0 and candidate.controlled
    )
    occupied = {
        point
        for candidate in visible
        if candidate.hp > 0
        for point in footprint(candidate.position, candidate.physical_radius)
    }
    candidates = set()
    for x, y, z in anchors:
        for dx, dy in (
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1),
            (2, 0),
            (-2, 0),
            (0, 2),
            (0, -2),
            (1, 1),
            (1, -1),
            (-1, 1),
            (-1, -1),
        ):
            cell = x + dx, y + dy, z
            if cell in indices and cell[:2] not in occupied:
                candidates.add(cell)
    origin = tuple(actor.position)
    distance = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    ordered = sorted(
        candidates,
        key=lambda cell: (
            min(distance(cell, anchor) for anchor in anchors),
            distance(cell, origin),
            indices[cell],
        ),
    )
    return [indices[cell] for cell in ordered[:16]]


def nox_calendar_managed(fight):
    """Read only the already frozen Nox event policy, preserving explicit absence."""
    if hasattr(fight, "native_encounter_table_listener_policy"):
        policy = fight.native_encounter_table_listener_policy
    else:
        profile = getattr(fight, "boss_score_profile", None)
        policy = (
            profile.get("table_listener_policy")
            if isinstance(profile, Mapping)
            else None
        )
    if (
        not isinstance(policy, Mapping)
        or policy.get("policy") != "wakemu-nox-owned-boundaries-v4"
        or policy.get("map_id") != 1435
        or policy.get("boss_reference") != 5664
        or not isinstance(policy.get("monster_references"), (tuple, list))
        or 5664 not in policy["monster_references"]
    ):
        return False
    callbacks = policy.get("callbacks")
    if not isinstance(callbacks, (tuple, list)):
        return False
    return all(
        any(
            isinstance(row, Mapping)
            and row.get("effect_reference") == effect
            and row.get("owner_reference") == 5664
            and row.get("owner_state") == state
            and row.get("forbidden_state") == forbidden
            and row.get("timing") == "owned_boss_post_start"
            and row.get("event_id") == 1005
            and row.get("channel") == 60
            for row in callbacks
        )
        for effect, state, forbidden in ((401544, 8978, 8979), (401749, 8979, 9031))
    )


def source(oracle):
    fight = oracle.runtime.fight
    actor = fight.current
    from wakfu_server import native_catalog

    return dict(
        fightInstanceId=oracle.runtime.tactical_encounter_id,
        fightId=fight.id,
        actorId=actor.id,
        turnId=fight.turn_id,
        stateRevision=fight.sequence,
        actionId=oracle.runtime.action_id,
        catalogRevision=native_catalog.release(),
        nativeIdentity=oracle.state_identity(oracle.runtime),
    )


def _position_view(fight, actor, position):
    # Native LOS/tackle readers require the actual caster to occupy the queried
    # origin. A shallow read-only view changes no live actor or QI registration.
    private = copy(fight)
    private.actors = dict(fight.actors)
    traveler = copy(actor)
    traveler.position = tuple(position)
    private.actors[actor.id] = traveler
    return private, traveler


def _reachable(fight, actor, portals=(), *, geometry=None):
    portals = tuple(portals)
    if geometry is None:
        adjacency = {}
        for start, end in fight.edges or ():
            adjacency.setdefault(tuple(start), []).append(tuple(end))
    elif not portals:
        adjacency = geometry.adjacency
    else:
        adjacency = {
            cell: list(destinations)
            for cell, destinations in geometry.adjacency.items()
        }
    for start, end in portals:
        adjacency.setdefault(tuple(start), []).append(tuple(end))
    occupied = {
        tuple(a.position)
        for a in fight.actors.values()
        if a.hp > 0 and a.id != actor.id
    }
    origin = tuple(actor.position)
    distances, pending = {origin: 0}, deque([origin])
    while pending:
        check()
        here = pending.popleft()
        if distances[here] >= actor.mp:
            continue
        for cell in adjacency.get(here, ()):
            if cell not in occupied and cell not in distances:
                distances[cell] = distances[here] + 1
                pending.append(cell)
    return distances, adjacency


def _area_harmful(fight, actor, row, definition, effects, registry):
    """Bounded semantic classification, preserving native recipient relations.

    This is advisory risk, not a second effect interpreter. Conditional damage
    remains possible risk; native preparation still decides actual execution.
    """
    from wakfu_server.combat_ai_capabilities import classify_roots
    from wakfu_server.combat_effect_targets import native_selector_policy

    owner = getattr(fight, "actors", {}).get(row.get("owner_id"))
    area_source = (
        row.get("owner_id") is None or row.get("native_area_contract") == "fbc"
    )
    caster_id = row.get("uid") if area_source else row.get("owner_id")
    team = (
        row.get("native_fight_affiliation", -1)
        if area_source or owner is None
        else effective_affiliation(fight, owner)
    )
    relation = (
        "self"
        if actor.id == caster_id
        else "ally"
        if effective_affiliation(fight, actor) == team
        else "enemy"
    )
    state_catalog = None

    def states():
        nonlocal state_catalog
        if state_catalog is None:
            from wakfu_server.combat_npc_attack import npc_runtime_catalog

            state_catalog = npc_runtime_catalog(imported=True).source_states
        return state_catalog

    class StateView(Mapping):
        def __getitem__(self, key):
            return states()[key]

        def __iter__(self):
            return iter(("states", "effects"))

        def __len__(self):
            return 2

    class RecipientEffects:
        def get(self, key, default=None):
            check()
            effect = effects.get(key)
            if effect is None and state_catalog is not None:
                effect = state_catalog.get("effects", {}).get(key)
            if effect is None:
                return default
            level = row.get("level", 0)
            if (
                not effect.get("minimum_level", -32768)
                <= level
                <= effect.get("maximum_level", 32767)
            ):
                return default
            try:
                if relation not in native_selector_policy(effect)["relations"]:
                    return default
            except (ValueError, KeyError, TypeError):
                # Unknown selectors cannot certify safety. Preserve potential
                # harm while the native engine remains execution authority.
                pass
            return effect

    semantic = classify_roots(
        definition.get("effect_ids", ()),
        RecipientEffects(),
        states=StateView(),
        registry=registry,
        level=row.get("level", 0),
        max_nodes=128,
    )
    return bool({"damage", "control", "debuff"}.intersection(semantic["tags"]))


def movement_danger(fight, actor, indices):
    """Soft costs for active harmful areas; costs never consume real MP.

    Inspect only installed prototypes and their bounded effect closures. Native
    XY/radius geometry and recipient relations are retained. Pure buffs, heals,
    portals and mechanically inert areas do not become hazards merely by type.
    """
    from wakfu_server.combat_battleground_border import verify_battleground_border
    from wakfu_server.combat_effect_area_geometry import (
        contains_area_actor,
        refresh_area_geometry,
    )

    raw = [
        row
        for row in getattr(fight, "native_effect_areas", {}).values()
        if isinstance(row, dict)
        and row.get("remaining_activations", -1) != 0
        and not row.get("executing", False)
    ]
    hazards, definitions, effects, registry = [], None, None, None
    for row in raw:
        check()
        if row.get("native_area_contract") == "faP":
            verify_battleground_border(fight, row)
            hazards.append(row)
            continue
        if "reference" not in row:
            continue
        if definitions is None:
            from wakfu_server.combat_effect_area import native_effect_areas

            definitions = native_effect_areas()
        definition = definitions.get(str(row["reference"]))
        if not isinstance(definition, Mapping):
            continue
        kind = definition.get("type")
        if (
            kind in ("SIMPLE", "WALL", "FAKE_FIGHTER", "PORTAL")
            or row.get("native_type_id") == 19
        ):
            continue
        masks = set(definition.get("entry_masks", ()))
        if not masks.intersection((10001, 10008, 10000, 2243)):
            continue
        if kind == "HOUR" and actor.id != row.get("owner_id"):
            continue
        if row.get("native_area_contract") == "faN" and actor.id == row.get("owner_id"):
            continue
        if row.get("native_area_contract") == "fbc":
            from wakfu_server.combat_trap_area import trap_owner_movement_allowed

            if not trap_owner_movement_allowed(
                row,
                definition,
                target_id=actor.id,
                current_id=actor.id,
                event_ids=(10001, 10008),
            ):
                continue
        if effects is None:
            from wakfu_server.combat_effect_area_catalog import area_effect_catalog
            from wakfu_server.combat_static_catalogs import characteristic_registry

            effects = area_effect_catalog()["effects"]
            registry = characteristic_registry().get("effects", {})
        from wakfu_server.combat_area_property import area_properties

        if 1 in area_properties(row, definition):
            if row.get("native_fight_affiliation") == effective_affiliation(
                fight, actor
            ):
                from wakfu_server.combat_area_contact_policy import (
                    permits_ally_contact_consumption,
                )

                if not permits_ally_contact_consumption(row, definition, effects):
                    continue
        if _area_harmful(fight, actor, row, definition, effects, registry):
            private = dict(row)
            refresh_area_geometry(fight, private)
            hazards.append(private)
    result = []
    for cell, index in indices.items() if hazards else ():
        check()
        cost = 3 * sum(
            contains_area_actor(row, cell, actor.physical_radius) for row in hazards
        )
        if cost:
            result.append(dict(cell=index, cost=cost))
    return result


def portal_edges(oracle, indices, properties):
    """Observed native gate pairs, explicitly labelled as one-MP travel.

    Walking onto an entry does not teleport. These labels must be translated
    into portal_travel actions, never ordinary nonadjacent movement packets.
    """
    fight, actor = oracle.runtime.fight, oracle.runtime.fight.current
    raw = getattr(fight, "native_effect_areas", {})
    if (
        actor.mp < 1
        or properties.intersection({3, 88, 105})
        or not any(
            isinstance(row, dict) and row.get("native_type_id") == 19
            for row in raw.values()
        )
    ):
        return []
    from wakfu_server.combat_carrying import carrying_relations
    from wakfu_server.combat_effect_area_geometry import contains_area_cell
    from wakfu_server.combat_portal_travel import portal_network_pair
    from ..native.native_portal_travel import _visible_gates

    if carrying_relations(fight, actor)["is_carried"]:
        return []
    # The native area reader may refresh geometry. Keep it private exactly as
    # the existing native gate certification does, preserving the live source.
    private = oracle.fork(runtime=oracle.runtime)
    gates = _visible_gates(oracle, private)
    cells = {
        cell: tuple(row for row in gates if contains_area_cell(row, cell))
        for cell in indices
    }
    endpoints = {cell: rows for cell, rows in cells.items() if rows}
    result = []
    for origin, entries in endpoints.items():
        check()
        for destination, exits in endpoints.items():
            if origin == destination:
                continue
            pair = portal_network_pair(entries, exits)
            if pair is not None:
                result.append(
                    dict(
                        fromCell=indices[origin],
                        toCell=indices[destination],
                        entryUid=pair[0],
                        exitUid=pair[1],
                    )
                )
    return result


def semantic_rows(compiled, roots, level):
    """Project named semantics only; native effect IDs never become Dofus IDs.

    These are advisory summaries, not an alternate interpreter. Missing or
    conditional semantics remain explicit and do not remove the owned spell.
    """
    from wakfu_server.combat_definitions import effect_profile
    from .jondo_native_amount import (
        project_native_amount,
        protect_health_geometry,
        source_binding_proof,
        health_eligibility_proof,
        legacy_heal_fallback,
    )
    from wakfu_server.combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS
    from wakfu_server.combat_effect_targets import native_selector_policy
    from .jondo_area import area_projection
    from wakfu_server.combat_static_catalogs import characteristic_registry
    from wakfu_server.combat_current_stat_parameters import stat_parameters
    from wakfu_server.combat_effect_resolver import variant_accepts

    registry = characteristic_registry().get("effects", {})
    rows, unknown, seen = [], [], set()
    source_bindings = source_binding_proof(compiled.effects, roots, level)
    eligibility = health_eligibility_proof(
        compiled.effects, roots, level, source_bindings
    )
    pending = [(reference, False) for reference in roots]
    while pending and len(seen) < 128:
        check()
        reference, inherited_condition = pending.pop()
        if reference in seen:
            continue
        seen.add(reference)
        effect = compiled.effects.get(str(reference))
        if not isinstance(effect, Mapping):
            unknown.append("missing_effect:" + str(reference))
            continue
        try:
            if (
                not effect.get("minimum_level", -32768)
                <= level
                <= effect.get("maximum_level", 32767)
            ):
                continue
            # The native AI cast entry explicitly uses critical=False. Both
            # normal and critical roots exist in the native casting table;
            # select through the same resolver before following child roots.
            if not variant_accepts(effect, "EFFECTS_ONLY"):
                continue
            conditional = (
                inherited_condition
                or bool(effect.get("criteria"))
                or effect["effect_class"] == 349
            )
            pending.extend((child, conditional) for child in effect.get("children", ()))
            family = effect["effect_class"]
            profile = effect_profile(effect, level)
            policy = native_selector_policy(effect)
            relations = sorted(policy["relations"])
            # Preserve exact native XY footprints rather than rounding cones,
            # rings and crosses into a guessed circular Jondo zone.
            area = area_projection(effect)
            kind, amount, element = None, None, "physical"
            native_amount = {}
            row_in_area = policy["in_area"]
            if family in DAMAGE_FAMILIES or family in HEAL_ELEMENTS:
                kind = "damage" if family in DAMAGE_FAMILIES else "heal"
                binding = source_bindings.get(reference, False)
                native_amount = project_native_amount(
                    effect, level, source_binding_known=binding
                )
                legacy_heal = legacy_heal_fallback(
                    effect,
                    native_amount,
                    source_known=binding,
                    conditional=conditional,
                    eligibility=eligibility.get(reference, False),
                )
                if eligibility.get(reference):
                    native_amount["nativeHealthEligibility"] = dict(
                        version=1, targetNotCarried=True
                    )
                if not binding and not legacy_heal:
                    conditional = True
                    unknown.append("native_source_binding_unproven:" + str(reference))
                amount = native_amount.pop("amount")
                if legacy_heal:
                    amount = native_amount["nativeBase"]["value"]
                    native_amount = {}
                if not legacy_heal and (
                    "nativeHealing" in native_amount
                    or native_amount["nativeBase"]["kind"]
                ):
                    area = protect_health_geometry(area, row_in_area)
                    row_in_area = True
                element = (
                    {
                        1: "physical",
                        2: "fire",
                        3: "earth",
                        4: "water",
                        5: "air",
                        6: "light",
                    }.get(HEAL_ELEMENTS[family], "physical")
                    if kind == "heal" and not legacy_heal
                    else {
                        2: "fire",
                        3: "earth",
                        4: "water",
                        5: "air",
                        917: "stasis",
                        1083: "light",
                    }.get(family, "physical")
                )
            else:
                metadata = registry.get(str(family), {})
                statistic, operation = metadata.get("fixed_stat_id"), metadata.get(
                    "operation"
                )
                kind = {
                    (2, "gain_current"): "gain_ap",
                    (3, "gain_current"): "gain_mp",
                    (2, "lose_current"): "remove_ap",
                    (3, "lose_current"): "remove_mp",
                }.get((statistic, operation))
                if kind is not None and profile["parameters"]:
                    values = stat_parameters(
                        effect["parameters"],
                        level,
                        registered_stat_id=statistic,
                        percent_default=bool(metadata.get("percent_default", False)),
                        trigger_value=None,
                    )
                    if values["percent"]:
                        raise ValueError("percent_stat_requires_native_target_context")
                    amount = values["requested"]
            if kind is None or type(amount) is not int:
                raise ValueError("unsupported_semantic_family:" + str(family))
            if conditional:
                unknown.append("conditional_effect:" + str(reference))
            for relation in relations:
                rows.append(
                    dict(
                        kind=kind,
                        amount=amount,
                        target=relation,
                        element=element,
                        zoneRadius=0,
                        **area,
                        probability=profile["probability"],
                        conditional=conditional,
                        nativeInArea=row_in_area,
                        confidence="conditional"
                        if conditional or profile["probability"] < 100
                        else "known",
                        nativeReference=reference,
                        **native_amount
                    )
                )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            unknown.append(str(error))
    if pending:
        unknown.append("semantic_projection_node_limit")
    return rows, sorted(set(unknown))


def summarize(rows, unknown):
    values = dict(
        damage=0,
        heal=0,
        removal=0,
        buff=0,
        utility=0,
        summons=False,
        element="physical",
        hurtsAllies=False,
    )
    seen = set()
    for row in rows:
        values["hurtsAllies"] |= row["kind"] == "damage" and row["target"] in (
            "self",
            "ally",
        )
        identity = row["nativeReference"], row["kind"]
        if identity in seen:
            continue
        seen.add(identity)
        field = {
            "damage": "damage",
            "heal": "heal",
            "gain_ap": "buff",
            "gain_mp": "buff",
            "remove_ap": "removal",
            "remove_mp": "removal",
        }.get(row["kind"])
        if field is not None:
            values[field] += max(0, row["amount"])
        if row["kind"] == "damage":
            values["element"] = row["element"]
    if unknown and not any(
        values[name] for name in ("damage", "heal", "removal", "buff")
    ):
        # Match Jondo's pure-mechanics exploration category without pretending
        # this is native damage or a qualified effect forecast.
        values["utility"] = 1
    return values


def utility_targets(compiled, roots, level, *, rule=None):
    """Describe actual native recipient relations without inventing a benefit.

    Cast aim and effect recipient are distinct: a zero-range hostile aura is
    aimed at self even though its native selector affects enemies only.
    """
    from wakfu_server.combat_effect_resolver import variant_accepts
    from wakfu_server.combat_effect_targets import native_selector_policy

    relations, seen, pending, unknown = set(), set(), list(roots), False
    while pending and len(seen) < 128:
        check()
        reference = pending.pop()
        if reference in seen:
            continue
        seen.add(reference)
        effect = compiled.effects.get(str(reference))
        if not isinstance(effect, Mapping):
            unknown = True
            continue
        try:
            if (
                not effect.get("minimum_level", -32768)
                <= level
                <= effect.get("maximum_level", 32767)
            ):
                continue
            if not variant_accepts(effect, "EFFECTS_ONLY"):
                continue
            relations.update(native_selector_policy(effect)["relations"])
            pending.extend(effect.get("children", ()))
        except (ValueError, TypeError, KeyError):
            unknown = True
    unknown = unknown or bool(pending)
    aims = set(relations)
    basis = "mixed_or_unknown"
    if rule is not None and rule["maximum"] <= 0:
        aims, basis = {"self"}, "self_aim_zero_range"
    elif rule is not None and rule.get("allow_self") is False:
        aims.discard("self")
    enemy_only = aims == {"enemy"} and not unknown
    if enemy_only:
        basis = "exclusive_enemy"
    elif aims == {"self"} and not unknown and basis != "self_aim_zero_range":
        basis = "exclusive_self"
    elif aims == {"ally"} and not unknown:
        basis = "exclusive_ally"
    return dict(
        utilityOnEnemies=enemy_only,
        utilityTargets=sorted(aims),
        utilityEffectRelations=sorted(relations),
        utilityTargetBasis=basis,
        utilityTargetUnknown=unknown,
    )


def usage_rows(fight, actor, spells):
    state = getattr(fight, "native_spell_usage", {}).get(str(actor.id), {})
    current = state.get("turn") == actor.turn_count
    result = []
    # Native counters intentionally omit spells without enabled per-turn
    # limits. Successful NPC events provide the complete observed turn count
    # needed by Jondo's once-per-turn support policy without changing limits.
    observed = {}
    for event in getattr(fight, "events", ()):
        if (
            event.get("kind") == "npc_cast"
            and event.get("actor_id") == actor.id
            and event.get("turn_id") == fight.turn_id
        ):
            key = str(event["spell_id"])
            observed[key] = observed.get(key, 0) + 1
    for spell in spells:
        reference = str(spell["id"])
        last = state.get("last", {}).get(reference)
        interval = spell.get("interval", 0)
        cooldown = (
            0
            if last is None or interval == 0
            else (
                2**30
                if interval < 0
                else max(0, interval - (fight.native_table_turn - last))
            )
        )
        record = dict(
            spellId=spell["id"],
            count=max(
                observed.get(reference, 0),
                state.get("casts", {}).get(reference, 0) if current else 0,
            ),
            remainingCooldown=cooldown,
        )
        result.append(record)
        if not current:
            continue
        for target, count in state.get("targets", {}).get(reference, {}).items():
            try:
                identity = ast.literal_eval(target)
            except (ValueError, SyntaxError, TypeError):
                continue
            if type(identity) is int:
                target_id = identity
            elif (
                isinstance(identity, tuple)
                and len(identity) == 2
                and identity[0] == "actor"
                and type(identity[1]) is int
            ):
                target_id = identity[1]
            else:
                continue
            result.append(dict(record, targetId=target_id, targetCount=count))
    return result


def build_snapshot(oracle, *, excluded_actions=(), budget_ms=500):
    from .jondo_native_hp import readonly_hp_projection, readonly_healing_projection
    from wakfu_server.combat_spell_usage import limits
    from wakfu_server.combat_native_spell_casting import (
        definition,
        native_casting_table,
    )
    from wakfu_server.combat_casting_range import resolve_range
    from wakfu_server.combat_tackle_movement import movement_tackle_cost
    from .jondo_los import casting_visible
    from wakfu_server.combat_los_geometry import prepare_los_geometry
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_carrying import carrying_relations

    runtime, fight = oracle.runtime, oracle.runtime.fight
    actor = fight.current
    baseline = source(oracle)
    from .jondo_los_cache import cache_for_oracle

    advisory_cache = cache_for_oracle(oracle, baseline)
    if advisory_cache is not None:
        advisory_cache = advisory_cache.snapshot_session()
    cache_kwargs = (
        dict(advisory_cache=advisory_cache) if advisory_cache is not None else {}
    )
    from .jondo_geometry import geometry_projection, body_extra_cells

    geometry = geometry_projection(fight, catalog_revision=baseline["catalogRevision"])
    cells, indices = geometry.cells, geometry.indices
    factory, adapter = oracle.factory(fight, runtime.action_id + 1, random.Random(0))
    properties, actor_contexts = {}, {}
    project_condition = getattr(adapter.actor_authority, "condition_projection", None)
    for candidate in fight.actors.values():
        if candidate.hp <= 0:
            continue
        if callable(project_condition):
            try:
                metadata, world, fight_properties = project_condition(fight, candidate)
                if isinstance(fight_properties, (set, frozenset)):
                    properties[candidate.id] = fight_properties
                    actor_contexts[candidate.id] = metadata, world
                    continue
            except (ValueError, TypeError, KeyError, AttributeError):
                # Optional world-property evidence must not block an actor
                # whose existing ordinary fight-property reader still works.
                pass
        properties[candidate.id] = adapter.actor_authority.properties(fight, candidate)
    hidden = {
        a.id
        for a in fight.actors.values()
        if a.hp > 0
        and effective_affiliation(fight, a) != effective_affiliation(fight, actor)
        and {5, 18}.intersection(properties.get(a.id) or ())
    }
    visible = [a for a in fight.actors.values() if a.id not in hidden]
    hp_definition = None
    if any(
        isinstance(getattr(a, "effect_minima", None), dict) and 1 in a.effect_minima
        for a in visible
    ):
        from wakfu_server.combat_character_copy_metadata import (
            native_copy_characteristics,
        )

        try:
            hp_definition = native_copy_characteristics()["fresh_characteristics"]["1"]
        except (ValueError, KeyError, TypeError):
            # Missing optional bounds never become a guessed floor or raw HP.
            pass
    prisoner_mechanic = oracle.descriptor(fight, actor).get("ref", 0) in (4251, 4280)
    actors = []
    for candidate in visible:
        if tuple(candidate.position) not in indices:
            if candidate.hp <= 0:
                continue
            raise ValueError("Jondo actor lies outside authoritative XYZ geometry")
        registration = getattr(fight, "native_summon_registrations", {}).get(
            candidate.id, {}
        )
        companion = getattr(fight, "native_companion_sources", {}).get(
            str(candidate.id), {}
        )
        descriptor = oracle.descriptor(fight, candidate)
        native_hp = readonly_hp_projection(candidate, hp_definition=hp_definition)
        native_footprint = frozenset(
            footprint(candidate.position, candidate.physical_radius)
        )
        extra_cells = body_extra_cells(geometry, candidate.position, native_footprint)
        actors.append(
            dict(
                id=candidate.id,
                team=effective_affiliation(fight, candidate),
                cell=indices[tuple(candidate.position)],
                hp=candidate.hp,
                maxHp=candidate.max_hp,
                ap=candidate.ap,
                mp=candidate.mp,
                maxAp=candidate.max_ap,
                maxMp=candidate.max_mp,
                wp=candidate.effect_stats[4],
                maxWp=candidate.effect_maxima[4],
                virtualHpMax=candidate.effect_maxima[92],
                armor=candidate.effect_stats[97],
                extraCells=extra_cells,
                physicalRadius=candidate.physical_radius,
                level=candidate.effective_level,
                direction=candidate.direction,
                registeredSummon=candidate.id
                in getattr(fight, "native_summon_registrations", {}),
                isPlayer=candidate.controlled,
                monsterRef=descriptor.get("ref", 0),
                breed=descriptor.get("breed", 0) if candidate.controlled else 0,
                summonerId=registration.get(
                    "caster_id", companion.get("owner_character_id")
                ),
                isCompanion=bool(companion),
                **(
                    dict(isCarrying=carrying_relations(fight, candidate)["is_carrying"])
                    if prisoner_mechanic
                    else {}
                ),
                states=[
                    dict(
                        reference=entry.reference,
                        level=entry.level,
                        duration=entry.duration,
                        casterId=entry.caster_id,
                    )
                    for entry in candidate.state_ledger.entries
                ],
                hidden=False,
                stats={str(key): value for key, value in candidate.effect_stats.items()}
            )
        )
        if native_hp is not None:
            actors[-1]["nativeHp"] = native_hp
        if isinstance(properties.get(candidate.id), (set, frozenset)):
            actors[-1]["nativeUndead"] = 20 in properties[candidate.id]
        metadata, world = actor_contexts.get(candidate.id, (None, None))
        actors[-1].update(
            readonly_healing_projection(
                candidate, metadata=metadata, world_properties=world
            )
        )
    owned = oracle.owned_spells(fight)
    spells, errors = [], []
    # Dynamic support work is shared only inside this guarded snapshot.
    support_request_cache = {}
    # Resolve only the current actor's owned book. No opponent book export,
    # all-catalog publication, runtime graph or remote native query session.
    for spell, level in sorted(owned.items()):
        check()
        compiled, support_roots, support_rule, context = None, (), None, None
        entry = dict(
            id=spell,
            grade=level,
            rows=[],
            unknownProjection=[],
            utilityOnEnemies=False,
            utilityTargets=[],
            utilityEffectRelations=[],
            utilityTargetBasis="mixed_or_unknown",
            utilityTargetUnknown=True,
        )
        try:
            table, index = native_casting_table(spell, level)
            from wakfu_server.combat_npc_attack import npc_runtime_catalog

            compiled = npc_runtime_catalog(imported=True)
            support_roots = table["levels"][index][2]
            entry.update(utility_targets(compiled, support_roots, level))
            costs, ranges = table["costs"][index], table["levels"][index][:2]
            adjustment = sum(
                actor.spell_ap_cost_modifiers.get(category, 0)
                for category in table["categories"]
            )
            entry.update(
                cost=max(0, costs[0] + adjustment),
                nativeCosts=dict(
                    ap=max(0, costs[0] + adjustment),
                    mp=max(0, costs[1]),
                    wp=max(0, costs[2]),
                ),
                minRange=ranges[0],
                maxRange=ranges[1],
                needsLineOfSight=table["line_of_sight"],
                inLine=table["linear"],
                needsFreeCell=table["free_cell"],
                rangeBoostable=table["range_modifiable"],
                perTurn=0,
                perTarget=0,
                interval=0,
            )
            context = adapter.cast_condition(
                fight,
                dict(actor_id=actor.id, spell_uid=spell, target=tuple(actor.position)),
            )
            rule = definition(spell, level, context, actor.spell_ap_cost_modifiers)
            rule = resolve_range(rule, actor, context)
            support_roots, support_rule = rule["roots"], rule
            usage = limits(spell, level, context)
            rows, unknown = semantic_rows(compiled, rule["roots"], level)
            entry.update(utility_targets(compiled, rule["roots"], level, rule=rule))
            entry.update(
                cost=rule["costs"]["ap"],
                nativeCosts=rule["costs"],
                minRange=rule["minimum"],
                maxRange=rule["maximum"],
                needsLineOfSight=rule["line_of_sight"],
                inLine=rule["linear"],
                needsFreeCell=rule["free_cell"],
                rangeBoostable=False,
                perTurn=usage["per_turn"],
                perTarget=usage["per_target"],
                interval=usage["interval"],
                rows=rows,
                unknownProjection=unknown,
                selectedAt="current_caster_self_target",
                **summarize(rows, unknown)
            )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            # Keep ownership explicit when advisory conditional evaluation is
            # unavailable; native chosen-action preparation remains decisive.
            entry.setdefault("cost", 0)
            entry.setdefault("minRange", 0)
            entry.setdefault("maxRange", 0)
            entry.update(unknownProjection=[str(error)], **summarize([], [str(error)]))
            errors.append(dict(spellId=spell, detail=str(error)))
        if compiled is not None and support_roots:
            from .jondo_capabilities import project_support

            entry["nativeSupport"] = project_support(
                compiled,
                support_roots,
                level,
                fight=fight,
                actor=actor,
                rule=support_rule
                or dict(
                    maximum=entry["maxRange"],
                    minimum=entry["minRange"],
                    free_cell=entry.get("needsFreeCell", False),
                ),
                context=context,
                indices=indices,
                actors=actors,
                request_cache=support_request_cache,
            )
        spells.append(entry)
    portals = portal_edges(oracle, indices, properties[actor.id])
    reachable, adjacency = _reachable(
        fight,
        actor,
        ((cells[row["fromCell"]], cells[row["toCell"]]) for row in portals),
        geometry=geometry,
    )
    descriptor = oracle.descriptor(fight, actor)
    prepared_visibility = prepare_los_geometry(descriptor["map_id"], fight.walkable)
    actor_reference = descriptor.get("ref", 0)
    special = actor_reference in _MECHANIC_MONSTERS
    aim_cells = special_aim_cells(actor, indices, visible, spells) if special else []
    areas = mechanic_areas(fight, actor, indices, hidden=hidden) if special else []
    los, tackle = [], []
    targets = {tuple(a.position) for a in visible if a.hp > 0}
    # Reuse the observed body cells already projected above. These are bounded
    # actor aims, not all board cells; own side cells are not cast origins.
    for candidate in actors:
        if candidate["hp"] > 0 and candidate["id"] != actor.id:
            targets.update(cells[index] for index in candidate["extraCells"])
    targets.update(cells[index] for index in aim_cells)
    targets.update(
        cells[index]
        for spell in spells
        for index in spell.get("nativeSupport", {}).get("candidateCells", ())
    )
    threats = {
        tuple(a.position)
        for a in visible
        if a.hp > 0
        and effective_affiliation(fight, a) != effective_affiliation(fight, actor)
    }
    for origin in reachable:
        check()
        private, traveler = _position_view(fight, actor, origin)
        private.native_rail_movement_authority = factory.native_rail_movement_authority
        footprints = {
            a.id: footprint(a.position, a.physical_radius)
            for a in private.actors.values()
            if a.hp > 0
        }
        # Cast selection asks candidate->occupied rays; repositioning also
        # asks enemy->candidate. Native heights and endpoint probes can differ
        # by direction, so measure both against this same relocated actor view.
        rays = [(origin, target) for target in targets]
        rays.extend((enemy, origin) for enemy in threats)
        measured = set()
        for ray_origin, ray_target in rays:
            check()
            pair = ray_origin, ray_target
            if pair in measured:
                continue
            try:
                value = casting_visible(
                    descriptor["map_id"],
                    ray_origin,
                    ray_target,
                    private,
                    blocking_footprints=footprints,
                    prepared_geometry=prepared_visibility,
                    **cache_kwargs
                )
                los.append([indices[ray_origin], indices[ray_target], value])
                measured.add(pair)
            except (ValueError, TypeError, KeyError):
                # An unmeasured ray is never represented as a measured false.
                continue
        neighbors = adjacency.get(origin, ())
        if neighbors:
            ap, mp = movement_tackle_cost(private, traveler, [neighbors[0]])
            tackle.append(dict(cell=indices[origin], ap=ap, mp=mp))
    # Preserve all established rays/tackle observations before optional empty
    # AoE centers. Missing or expired supplemental evidence remains unknown.
    from .jondo_aoe_los import inverse_aoe_pairs

    supplemental_deadline = clock_now() + min(50, max(0, budget_ms) / 10) / 1000
    supplemental = inverse_aoe_pairs(
        spells,
        actors,
        cells,
        indices,
        reachable,
        targets,
        actor_id=actor.id,
        deadline=supplemental_deadline,
    )
    last_origin = None
    for origin, target in supplemental:
        check()
        if clock_now() >= supplemental_deadline:
            break
        if origin != last_origin:
            private, traveler = _position_view(fight, actor, origin)
            private.native_rail_movement_authority = (
                factory.native_rail_movement_authority
            )
            footprints = {
                a.id: footprint(a.position, a.physical_radius)
                for a in private.actors.values()
                if a.hp > 0
            }
            last_origin = origin
        try:
            value = casting_visible(
                descriptor["map_id"],
                origin,
                target,
                private,
                blocking_footprints=footprints,
                prepared_geometry=prepared_visibility,
                **cache_kwargs
            )
            los.append([indices[origin], indices[target], value])
        except (ValueError, TypeError, KeyError):
            continue
    danger = movement_danger(fight, actor, indices)
    if oracle.state_identity(runtime) != baseline["nativeIdentity"]:
        raise ValueError("Native source changed while preparing Jondo snapshot")
    if advisory_cache is not None:
        advisory_cache.publish()
    return dict(
        protocol=1,
        requestId=uuid.uuid4().hex,
        source=baseline,
        board=dict(
            cells=[dict(id=index, xyz=list(cell)) for index, cell in enumerate(cells)],
            edges=[list(edge) for edge in geometry.encoded_edges],
            actors=actors,
            round=getattr(fight, "native_table_turn", 0),
            lineOfSight=los,
            tackle=tackle,
            portalEdges=portals,
            movementDanger=danger,
            mechanicAreas=areas,
        ),
        spells=spells,
        native=dict(
            usage=usage_rows(fight, actor, spells),
            unknownProjection=errors,
            specialAimCells=aim_cells,
            turnActions=[],
            noxCalendarManaged=(
                actor_reference == 5664 and nox_calendar_managed(fight)
            ),
        ),
        excludedActions=list(excluded_actions),
        limits=dict(budgetMs=budget_ms, maxActions=1),
    )
