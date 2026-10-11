"""Read-only native NPC previews with fenced, append-only dependency overlays."""
import argparse
import ast
from collections import Counter
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import random
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
NATIVE_SOURCE_MONSTERS = {}


CLASS_TEST_MODULES = [
    "test_combat_class_initialization",
    "test_combat_iop_cast",
    "test_combat_xelor_cast",
    "test_combat_xelor_passive",
    "test_combat_spell_transaction",
    "test_combat_damage_healing",
    "test_combat_damage_handler",
    "test_combat_damage_parameters",
    "test_combat_npc_attack",
    "test_combat_active_spell",
    "test_combat_native_owner_selection",
    "test_monster_spell_activation",
    "test_npc_casting_root_import",
    "test_monster_combat_extraction",
    "test_combat_spell_resource_costs",
    "test_combat_hupper_resource_binding",
    "test_combat_tactical_ai",
    "test_combat_feca_start",
    "test_feca_protection_pipeline",
    "test_sram_stacked_visibility_native",
    "test_sacrier_sacrifice_pipeline",
    "test_sacrier_threshold_pipeline",
    "test_sacrier_columnata_pipeline",
    "test_combat_cra_beacon_reaction",
    "test_combat_huppermage_runtime",
    "test_combat_iop_preparation_movement_runtime",
    "test_combat_iop_cast_boundary_runtime",
    "test_feca_grant_pipeline",
    "test_sram_trap_audit_config",
    "test_monster_activation_finalize",
    "test_monster_activation_staging",
    "test_monster_activation_pipeline_safety",
    "test_monster_activation_automation",
    "test_monster_spell_scenarios",
    "test_combat_npc_initialization",
    "test_native_local_boolean_operators",
    "test_monster_state_resistance_import",
    "test_monster_native_spell_levels",
    "test_combat_state_resistance_metadata",
    "test_monsters",
    "test_monster_cell_group_import",
    "test_monster_summon_dependency_export",
    "test_combat_minimum_resource_constructor",
    "test_combat_initial_state_zero_duration",
    "test_combat_instant_state_subscription",
    "test_monster_scenario_actor_turns",
    "test_monster_class_buff_scenarios",
    "test_monster_initialization_proof_regressions",
    "test_monster_scenario_player_turn_identity",
    "test_monster_empty_target_search",
    "test_monster_activation_exceptions",
    "test_combat_npc_ai_initialization",
    "test_monster_area_search_envelope",
    "test_monster_casting_contract_audit",
    "test_monster_empty_target_alignment",
    "test_native_npc_summon_delivery",
    "test_monster_encounter_buff_recipes",
    "test_monster_summon_activation_scope",
    "test_monster_native_companion_scenarios",
    "test_combat_human_enemy_range",
    "test_combat_npc_area_preflight",
    "test_monster_ignored_references",
    "test_monster_activation_scope",
    "test_monster_validation_budget",
    "test_monster_validation_missing_geometry",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_receipt_context(previous, current):
    """Reject reuse after a change in executable or native test authority."""
    for field in (
        "candidate_manifest_sha256",
        "changed_document_hashes",
        "base_revision",
        "base_document_hashes",
        "runtime_code_sha256",
        "native_monsters_sha256",
        "validator_sha256",
        "test_code_sha256",
        "test_scope",
    ):
        if field not in previous or previous[field] != current[field]:
            raise ValueError("Cannot reuse validation after changed " + field)


def initialization_proven(reference, level, raw_triples, receipt):
    """Require the exact native constructor plan, never just a status flag."""
    if not raw_triples:
        return True
    from wakfu_server.combat_summon_initial_states import initial_state_plan
    from dataclasses import asdict

    carrier_count = len(raw_triples) // 3
    if isinstance(receipt, dict) and "nonretained_state_ids" in receipt:
        expected = nonretained_initial_states(raw_triples, level)
        if receipt["nonretained_state_ids"] != expected:
            return False
        carrier_count -= len(expected)
    return (
        isinstance(receipt, dict)
        and receipt.get("initialized") is True
        and receipt.get("ref") == reference
        and receipt.get("descriptor_level") == level
        and receipt.get("raw_triples") == raw_triples
        and receipt.get("resolved_states")
        == [asdict(item) for item in initial_state_plan(raw_triples, level)]
        and receipt.get("applications")
        == [
            dict(state_id=item.state_id, level=item.level, applied=True)
            for item in initial_state_plan(raw_triples, level)
        ]
        and placement_effects_proven(receipt.get("placement_effects"), carrier_count)
    )


def nonretained_initial_states(raw_triples, level):
    """Native eZk.Ty/bbX retain neither clock when both durations are zero."""
    from wakfu_server.combat_summon_initial_states import initial_state_plan
    from wakfu_server.combat_definitions import state_profile
    from wakfu_server.combat_server_spell import states_catalog

    catalog = states_catalog()
    return [
        item.state_id
        for item in initial_state_plan(raw_triples, level)
        if (lambda p: p["duration"] == 0 and p["realtime_duration"] == 0)(
            state_profile(catalog, item.state_id, item.level)
        )
    ]


def placement_effects_proven(receipt, state_count):
    """A constructor pass also needs its complete native placement envelope."""
    if not isinstance(receipt, dict) or receipt.get("verified") is not True:
        return False
    count, carriers, size = (
        receipt.get(key) for key in ("effect_count", "state_carrier_count", "bytes")
    )
    checksum = receipt.get("sha256")
    return (
        all(type(value) is int for value in (count, carriers, size))
        and count >= carriers >= state_count >= 0
        and 2 <= size <= 50000
        and isinstance(checksum, str)
        and len(checksum) == 64
        and all(char in "0123456789abcdef" for char in checksum)
    )


def changed_hashes(before, after):
    return sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )


def source_hashes():
    excluded = {"tests", "__pycache__", ".venv", "venv", "site-packages"}
    return {
        p.relative_to(ROOT).as_posix(): digest(p)
        for p in (ROOT / "server").rglob("*.py")
        if not excluded.intersection(p.relative_to(ROOT / "server").parts)
    }


def test_dependency_files(root, modules):
    """Discover static local test/tool imports, including transitive fixtures."""
    root = Path(root)
    search = [root / "server/tests", root / "server/tools"]
    pending = []

    def find(module):
        relative = Path(*module.split("."))
        for directory in search:
            for path in (
                directory / relative.with_suffix(".py"),
                directory / relative / "__init__.py",
            ):
                if path.is_file():
                    return path
        return None

    for name in modules:
        path = find(name)
        if path is None:
            raise ValueError("Missing selected regression module: " + name)
        pending.append(path)
    found = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                names = [prefix] + [
                    prefix + "." + alias.name if prefix else alias.name
                    for alias in node.names
                ]
                if node.level:
                    parent = path.parent
                    for _ in range(node.level - 1):
                        parent = parent.parent
                    for name in filter(None, names):
                        candidate = parent / Path(*name.split(".")).with_suffix(".py")
                        if candidate.is_file():
                            pending.append(candidate)
            for name in filter(None, names):
                dependency = find(name)
                if dependency is not None:
                    pending.append(dependency)
    return sorted(found)


def test_hashes():
    return {
        p.relative_to(ROOT).as_posix(): digest(p)
        for p in test_dependency_files(ROOT, CLASS_TEST_MODULES)
    }


def install_overlay(candidate, *, overlay=True):
    from wakfu_server import native_catalog

    manifest = json.loads((candidate / "manifest.json").read_text())
    raw = {}
    for name, expected in manifest["changed_documents"].items():
        data = (candidate / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Candidate checksum mismatch: " + name)
        raw[name] = data
    required = {"native-npc-spell-effect-trees.json", "native-class-casting-roots.json"}
    from export_monster_state_resistance import CATALOG_PATH, assert_preserved
    from export_monster_cell_groups import (
        CATALOG_PATH as CELL_PATH,
        assert_preserved as preserve_cells,
    )
    from export_monster_summon_dependencies import (
        CATALOG_PATHS as SUMMON_PATHS,
        assert_preserved as preserve_summons,
    )

    if not required <= set(raw) or set(raw) - required - {
        "native-spell-resource-costs.json",
        CATALOG_PATH,
        CELL_PATH,
    } - set(SUMMON_PATHS):
        raise ValueError("Unexpected candidate overlay scope")

    class NoRedis:
        def get(self, key):
            return None

        def setex(self, *args):
            return None

    native_catalog._redis = lambda: NoRedis()
    if native_catalog.release() != manifest["base_revision"]:
        raise ValueError("Active base revision changed")
    hashes = native_catalog.document_hashes()
    if any(
        hashes.get(name) != expected
        for name, expected in manifest["unchanged_documents"].items()
    ):
        raise ValueError("Shared catalog differs from candidate manifest")
    if not overlay:
        raw = {
            name: data
            for name, data in raw.items()
            if name == "native-spell-resource-costs.json"
        }
    base_hashes = {}
    audited = required | (
        set(manifest["changed_documents"])
        & ({CATALOG_PATH, CELL_PATH} | set(SUMMON_PATHS))
    )
    for name in audited:
        base_raw = native_catalog.read_bytes(native_catalog.DATA_ROOT / name)
        base_hashes[name] = hashlib.sha256(base_raw).hexdigest()
        if hashes.get(name) != base_hashes[name]:
            raise ValueError("Pinned base document checksum mismatch: " + name)
        if name == CATALOG_PATH:
            assert_preserved(
                json.loads(base_raw), json.loads((candidate / name).read_bytes())
            )
        elif name == CELL_PATH:
            preserve_cells(
                json.loads(base_raw), json.loads((candidate / name).read_bytes())
            )
        elif name in SUMMON_PATHS:
            preserve_summons(
                name, json.loads(base_raw), json.loads((candidate / name).read_bytes())
            )
    manifest = dict(manifest, audited_base_document_hashes=base_hashes)
    original_load, original_read = native_catalog.load, native_catalog.read_bytes
    decoded = {name: json.loads(data) for name, data in raw.items()}

    def read(path):
        return raw.get(native_catalog._key(path), None) or original_read(path)

    def load(path):
        key = native_catalog._key(path)
        return decoded[key] if key in decoded else original_load(path)

    native_catalog.read_bytes, native_catalog.load = read, load
    return manifest


def fixture(reference, level, enemy_cell, *, scenario=None):
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import encode_deck

    source = (-8, -7, -1)
    buff_recipe = (
        scenario
        if isinstance(scenario, dict) and scenario.get("kind") == "class_buff"
        else None
    )
    character_breed = buff_recipe["character_breed"] if buff_recipe else 15
    character_level = buff_recipe["character_level"] if buff_recipe else 1
    character = effective_character(
        dict(
            id=7,
            account_id=3,
            breed=character_breed,
            level=character_level,
            hp=maximum(character_breed, character_level),
            map_id=1134,
            instance_id=0,
            x=enemy_cell[0],
            y=enemy_cell[1],
            z=enemy_cell[2],
            sex=0,
            builds={},
            inventory_items=[],
        )
    )
    resources = combat_resources(character)
    monster = owned_instance(
        reference, level, -200, map_id=1134, x=source[0], y=source[1], z=source[2]
    )
    terrain = local_arena(
        1134,
        0,
        enemy_cell,
        source,
        relocate_monsters=False,
        compact=True,
        variation_seed=1,
        minimum_dimensions=(9, 9),
    )
    player = Actor(
        7,
        1 if scenario == "wounded_ally" else 0,
        enemy_cell,
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        character_level,
        3,
        True,
        max_hp=character["max_hp"],
    )
    npc_team = buff_recipe["caster_team"] if buff_recipe else 1
    npc = Actor(
        -200,
        npc_team,
        source,
        monster["hp"],
        monster["ap"],
        monster["mp"],
        monster["initiative"],
        level,
        max_hp=monster["max_hp"],
    )
    npc.direction = 3
    actors = [player, npc]
    monsters = {-200: monster}
    placements = {0: {enemy_cell}, 1: {source}}
    if isinstance(scenario, dict):
        if buff_recipe:
            hostile_cell = next(
                (
                    cell
                    for cell in sorted(
                        terrain["validated_cells"],
                        key=lambda cell: (
                            abs(cell[0] - source[0]) + abs(cell[1] - source[1]),
                            cell,
                        ),
                    )
                    if cell not in {source, enemy_cell}
                ),
                None,
            )
            if hostile_cell is None:
                raise ValueError("Class buff scenario lacks an opposing placement")
            hostile_source = scenario.get(
                "opponent", dict(reference=6, level=4, team=1)
            )
            if hostile_source.get("team", 1) != 1:
                raise ValueError("Class preparation requires its actual opposing actor")
            hostile = owned_instance(
                hostile_source["reference"],
                hostile_source["level"],
                -201,
                map_id=1134,
                team=1,
                x=hostile_cell[0],
                y=hostile_cell[1],
                z=hostile_cell[2],
            )
            actors.append(
                Actor(
                    -201,
                    1,
                    hostile_cell,
                    hostile["hp"],
                    hostile["ap"],
                    hostile["mp"],
                    hostile["initiative"],
                    hostile_source["level"],
                    max_hp=hostile["max_hp"],
                )
            )
            monsters[-201] = hostile
            placements = {0: {source, enemy_cell}, 1: {hostile_cell}}
        elif scenario.get("kind") == "native_opponent":
            descriptor = scenario["opponent"]
            spare = next(
                (
                    cell
                    for cell in sorted(
                        terrain["validated_cells"],
                        key=lambda cell: (
                            abs(cell[0] - source[0]) + abs(cell[1] - source[1]),
                            cell,
                        ),
                    )
                    if cell not in {source, enemy_cell}
                ),
                None,
            )
            if spare is None:
                raise ValueError(
                    "Native opponent scenario lacks a separate player cell"
                )
            dependency_team = descriptor.get("team", 0)
            if dependency_team not in (0, 1):
                raise ValueError("Invalid native encounter dependency team")
            dependency_cell = spare if dependency_team == 1 else enemy_cell
            if dependency_team == 0:
                player.position = spare
                character.update(x=spare[0], y=spare[1], z=spare[2])
            opponent = owned_instance(
                descriptor["reference"],
                descriptor["level"],
                -201,
                map_id=1134,
                team=dependency_team,
                x=dependency_cell[0],
                y=dependency_cell[1],
                z=dependency_cell[2],
            )
            actors.append(
                Actor(
                    -201,
                    dependency_team,
                    dependency_cell,
                    opponent["hp"],
                    opponent["ap"],
                    opponent["mp"],
                    opponent["initiative"],
                    descriptor["level"],
                    max_hp=opponent["max_hp"],
                )
            )
            monsters[-201] = opponent
            placements = (
                {0: {enemy_cell}, 1: {source, spare}}
                if dependency_team == 1
                else {0: {spare, enemy_cell}, 1: {source}}
            )
        elif scenario.get("kind") != "owned_spell_sequence":
            raise ValueError("Unknown native monster scenario recipe")
    elif scenario == "wounded_ally":
        attacker_cells = [
            (enemy_cell[0] + dx, enemy_cell[1] + dy, enemy_cell[2])
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        ]
        attacker_cell = next(
            (
                cell
                for cell in attacker_cells
                if cell in terrain["validated_cells"] and cell != source
            ),
            None,
        )
        if attacker_cell is None:
            raise ValueError("Scenario lacks a distinct native attacker cell")
        attacker = owned_instance(
            6,
            4,
            -201,
            map_id=1134,
            team=0,
            x=attacker_cell[0],
            y=attacker_cell[1],
            z=attacker_cell[2],
        )
        actors.append(
            Actor(
                -201,
                0,
                attacker_cell,
                attacker["hp"],
                attacker["ap"],
                attacker["mp"],
                attacker["initiative"],
                4,
                max_hp=attacker["max_hp"],
            )
        )
        monsters[-201] = attacker
        placements = {0: {attacker_cell}, 1: {source, enemy_cell}}
    elif scenario is not None:
        raise ValueError("Unknown monster validation scenario")
    fight = Fight(
        78, actors, terrain["validated_cells"], placements, terrain["valid_edges"]
    )
    fight.native_qi_snapshot = {
        name: terrain[name] for name in ("x", "y", "width", "height", "cell_masks")
    }
    fight.native_qi_surface_provenance = dict(terrain["native_qi_surface_provenance"])
    freeze_terrain(fight)
    initialize_global_pv_collections(fight, tuple(fight.actors))
    from contextlib import nullcontext
    from unittest.mock import patch
    from wakfu_server import combat_npc_initialization

    constructor_scope = nullcontext()
    if isinstance(scenario, dict) and "opponent" in scenario:
        # Encounter dependencies use their complete original cle constructor,
        # never a state setter or expanded high-level spell activation policy.
        # This fixture-only scope cannot publish a high-level NPC activation.
        original_plans = combat_npc_initialization.initial_plans

        def dependency_plans(state, descriptors):
            plans = original_plans(state, descriptors)
            descriptor = descriptors[-201]
            native = NATIVE_SOURCE_MONSTERS.get(descriptor["ref"])
            actor = state.actors[-201]
            if (
                native is None
                or not native["min_level"]
                <= actor.effective_level
                <= native["max_level"]
            ):
                raise ValueError("Missing exact native encounter dependency descriptor")
            from wakfu_server.combat_summon_initial_states import initial_state_plan

            raw = native["initial_state_triples"]
            plan = initial_state_plan(raw, actor.effective_level)
            if plan:
                plans[-201] = (descriptor["ref"], tuple(raw), plan)
            return plans

        constructor_scope = patch.object(
            combat_npc_initialization, "initial_plans", dependency_plans
        )
    with constructor_scope:
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters=monsters,
            wp_resources={
                7: (resources["wp"], resources["wp"]),
                **{
                    identity: (row["wp"], row["wp"])
                    for identity, row in monsters.items()
                },
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
        )
    if terrain.get("team_values") != []:
        raise ValueError(
            "Constructed native arena lacks explicit empty QL obstacle table"
        )
    fight.native_obstacle_cells = frozenset()
    from wakfu_server.combat_remote_effects import (
        initial_npc_actor_effects,
        decode_remote_effects,
    )

    for identity, receipt in getattr(
        fight, "native_npc_initialization_receipts", {}
    ).items():
        payload = initial_npc_actor_effects(fight, identity)
        decoded = decode_remote_effects(payload)
        carriers = sum(item.effect_class == 310 for item in decoded)
        nonretained = nonretained_initial_states(
            receipt["raw_triples"], receipt["descriptor_level"]
        )
        if nonretained:
            receipt["nonretained_state_ids"] = nonretained
        if carriers < len(receipt["resolved_states"]) - len(nonretained):
            raise ValueError("Placement delivery omitted native initial-state carriers")
        receipt["placement_effects"] = dict(
            verified=True,
            bytes=len(payload),
            effect_count=len(decoded),
            state_carrier_count=carriers,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
    fight.ready(3)
    deck = encode_deck([buff_recipe["spell_id"]]) if buff_recipe else encode_deck()
    from monster_spell_scenarios import advance_to, wound_ally

    if isinstance(scenario, dict):
        if buff_recipe:
            from monster_class_buff_scenarios import buff_ally
            from wakfu_server.combat_los import authoritative_visible
            from monster_class_buff_scenarios import CLASS_BUFF_RECIPES

            canonical_recipe = next(
                recipe
                for recipe in CLASS_BUFF_RECIPES.values()
                if all(buff_recipe.get(key) == value for key, value in recipe.items())
            )
            fight.validation_scenario_receipt = buff_ally(
                fight,
                character,
                monsters,
                deck,
                ally_id=-200,
                recipe=canonical_recipe,
                line_of_sight=authoritative_visible,
            )
            for state_id in scenario.get("required_opponent_states", ()):
                if not any(
                    entry.reference == state_id
                    for entry in fight.actors[-201].state_ledger.entries
                ):
                    raise ValueError(
                        "Prepared encounter opponent lacks its native prerequisite state"
                    )
        else:
            from monster_pending_scenarios import prepare_scenario

            fight.validation_scenario_receipt = prepare_scenario(
                fight, character, monsters, deck, recipe=scenario
            )
    elif scenario == "wounded_ally":
        fight.validation_scenario_receipt = wound_ally(
            fight,
            character,
            monsters,
            deck,
            attacker_id=-201,
            ally_id=7,
            caster_id=-200,
            spell_id=5790,
            spell_level=4,
        )
    else:
        advance_to(fight, -200)
    return fight, character, monsters, deck


def run_case(reference, level, spell, spell_level, cells, limit):
    from wakfu_server.combat_ai_capabilities import describe_spell
    from wakfu_server.combat_npc_spell import prepare_npc_spell
    from wakfu_server.combat_geometry_snapshot import source_snapshot

    result = dict(
        level=level,
        spell_id=spell,
        spell_level=spell_level,
        status="pending",
        attempts=0,
        errors={},
        successful_targets=[],
        initialization_receipts=[],
    )
    errors = Counter()
    try:
        capability = describe_spell(spell, spell_level)
        result["capability"] = capability
    except Exception as exc:
        result["errors"] = {type(exc).__name__ + ": " + str(exc): 1}
        return result
    source = (-8, -7, -1)
    destinations = sorted(
        (cell for cell in cells if cell != source),
        key=lambda c: (abs(c[0] - source[0]) + abs(c[1] - source[1]), c),
    )
    from monster_pending_scenarios import enemy_search_envelope

    try:
        enemy_maximum = enemy_search_envelope(spell, spell_level, capability["maximum"])
    except ValueError as exc:
        result["errors"] = {"scene_search: ValueError: " + str(exc): 1}
        return result
    by_distance = {}
    for cell in destinations:
        distance = abs(cell[0] - source[0]) + abs(cell[1] - source[1])
        if max(1, capability["minimum"]) <= distance <= max(1, enemy_maximum):
            by_distance.setdefault(distance, []).append(cell)
    enemies = []
    for group in by_distance.values():
        enemies.extend(group[:2])
    if not enemies:
        enemies = destinations[:1]
    from monster_pending_scenarios import scenario_recipes

    scenarios = scenario_recipes(reference, spell) + [None]
    if "heal" in capability.get("tags", []):
        scenarios.append("wounded_ally")
    from monster_class_buff_scenarios import CLASS_BUFF_RECIPES

    if reference == 2778:
        scenarios.append(dict(CLASS_BUFF_RECIPES["ap"]))
    elif (reference, spell) == (5710, 4641):
        scenarios.append(dict(CLASS_BUFF_RECIPES["mp"]))
    scenes = [(scenario, enemy) for scenario in scenarios for enemy in enemies]
    for scenario, enemy in scenes:
        scene_limit = limit * (scenarios.index(scenario) + 1)
        # Exhausted scenarios cannot attempt another cast. Keep later scenario
        # budgets available without constructing unused native fights.
        if result["attempts"] >= scene_limit:
            continue
        try:
            fight, character, monsters, deck = fixture(
                reference, level, enemy, scenario=scenario
            )
        except Exception as exc:
            errors["initialization: " + type(exc).__name__ + ": " + str(exc)] += 1
            continue
        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(-200)
        if receipt is not None and receipt not in result["initialization_receipts"]:
            result["initialization_receipts"].append(receipt)
        target_id = (
            -201
            if isinstance(scenario, dict)
            and scenario.get("kind") == "native_opponent"
            and scenario["opponent"].get("team", 0) == 0
            else 7
        )
        targets = [(enemy, target_id), (source, -200)]
        if isinstance(scenario, dict) and scenario.get("kind") == "class_buff":
            hostile = fight.actors[-201]
            targets.insert(0, (hostile.position, -201))
        from monster_pending_scenarios import bounded_empty_targets
        from wakfu_server.combat_native_spell_casting import catalog as casting_catalog

        casting = casting_catalog().get(str(spell), {})
        if casting.get("free_cell") is True:
            empty = bounded_empty_targets(
                fight,
                source,
                capability["minimum"],
                capability["maximum"],
                limit=12,
                prefer_linear=casting.get("linear") is True,
                prefer_diagonal=casting.get("diagonal") is True,
            )
            empty_targets = [(cell, None) for cell in empty]
            targets = empty_targets + targets
        else:
            # Retain the certified ordinary-spell search order. Proximity
            # ordering is useful for free-cell AoE, but can discard the aligned
            # displacement target before the finite preview budget is spent.
            occupied = {tuple(actor.position) for actor in fight.actors.values()}
            ordinary_empty = [
                cell
                for cell in destinations
                if cell in fight.walkable
                and cell not in occupied
                and capability["minimum"]
                <= abs(cell[0] - source[0]) + abs(cell[1] - source[1])
                <= capability["maximum"]
            ]
            targets.extend((cell, None) for cell in ordinary_empty[:2])
        for target, identity in targets:
            if result["attempts"] >= scene_limit:
                break
            result["attempts"] += 1
            before = source_snapshot(fight)
            try:
                transaction = prepare_npc_spell(
                    fight,
                    dict(
                        type="cast",
                        spellId=spell,
                        level=spell_level,
                        target=list(target),
                        targetId=identity,
                    ),
                    character,
                    monsters,
                    deck,
                    action_id=1,
                    rng=random.Random(0),
                )
                effectful = any(
                    bool(getattr(outcome, "applied", outcome))
                    for outcome in transaction.outcomes
                )
                result["successful_targets"].append(
                    dict(
                        target=list(target),
                        target_id=identity,
                        enemy_cell=list(enemy),
                        effectful=effectful,
                        scenario=scenario,
                        scenario_receipt=getattr(
                            fight, "validation_scenario_receipt", None
                        ),
                        native_initialization=getattr(
                            fight, "native_npc_initialization_receipts", {}
                        ).get(-200),
                        outcomes=[repr(o)[:500] for o in transaction.outcomes],
                        event_kinds=[e["kind"] for e in transaction.events],
                        packets=len(transaction.packets),
                    )
                )
                if effectful:
                    result["status"] = "validated"
            except Exception as exc:
                errors[type(exc).__name__ + ": " + str(exc)] += 1
            if source_snapshot(fight) != before:
                raise RuntimeError("Native preview mutated original fight")
            if result["status"] == "validated":
                break
        if result["status"] == "validated":
            break
    result["errors"] = dict(errors)
    return result


def commit_smoke(monster):
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_geometry_snapshot import source_snapshot
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats

    case = next(c for c in monster["cases"] if c["status"] == "validated")
    success = next(t for t in case["successful_targets"] if t["effectful"])
    target = tuple(success["target"])
    # The recorded enemy location is exact for enemy casts; self/empty casts
    # retain the same native adjacent enemy creation context.
    enemy = (
        tuple(success["enemy_cell"])
        if "enemy_cell" in success
        else (target if success["target_id"] == 7 else (-7, -7, -1))
    )
    result = dict(status="pending", spell_id=case["spell_id"], level=case["level"])
    try:
        fight, character, monsters, deck = fixture(
            monster["ref"], case["level"], enemy, scenario=success.get("scenario")
        )
        provider = NativeProvider(character, monsters, deck)
        action = dict(
            type="cast",
            spellId=case["spell_id"],
            level=case["spell_level"],
            target=list(target),
            targetId=success["target_id"],
        )
        before = source_snapshot(fight)
        preview = provider.preview(fight, action, 1, forecast=True)
        if source_snapshot(fight) != before:
            raise RuntimeError("AI forecast mutated source")
        runtime = RuntimeMessages(fight)
        checkpoint = snapshot(fight, runtime=runtime)

        def broken_serializer(actor, state):
            raise ValueError("activation validator injected serialization failure")

        try:
            provider.commit(runtime, action, broken_serializer)
        except ValueError as exc:
            if str(exc) != "activation validator injected serialization failure":
                raise
        else:
            raise RuntimeError("Serializer failure failed to reject")
        if snapshot(runtime.fight, runtime=runtime) != checkpoint:
            raise RuntimeError("Failed AI delivery mutated runtime")

        def serialize(actor, state):
            keywords = dict(
                wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
            )
            if actor.id in getattr(state, "native_summon_registrations", {}):
                from wakfu_server.combat_summon_stats import registered_summon_stats

                return registered_summon_stats(actor, state, character["map_id"])
            if actor.controlled:
                return actual_actor_stats(character, actor, state.id, **keywords)
            return actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, **keywords
            )

        event_start = len(fight.events)
        observed_before = {
            str(a.id): dict(
                hp=a.hp,
                ap=a.ap,
                mp=a.mp,
                wp=a.effect_stats[4],
                states=len(a.state_ledger.entries),
                position=list(a.position),
                stats=dict(a.effect_stats),
            )
            for a in fight.actors.values()
        }
        actor_identities = {identity: actor for identity, actor in fight.actors.items()}
        packets = provider.commit(runtime, action, serialize)
        if (
            not packets
            or runtime.action_id != 1
            or runtime.fight is not fight
            or any(
                runtime.fight.actors[identity] is not actor
                for identity, actor in actor_identities.items()
            )
            or source_snapshot(runtime.fight) == before
        ):
            raise RuntimeError("AI delivery did not commit atomically")
        observed_after = {
            str(a.id): dict(
                hp=a.hp,
                ap=a.ap,
                mp=a.mp,
                wp=a.effect_stats[4],
                states=len(a.state_ledger.entries),
                position=list(a.position),
                stats=dict(a.effect_stats),
            )
            for a in runtime.fight.actors.values()
        }
        if observed_after == observed_before:
            raise RuntimeError(
                "AI commit changed no observable actor resources, states or positions"
            )
        deltas = {
            identity: dict(
                hp=after["hp"] - observed_before[identity]["hp"],
                ap=after["ap"] - observed_before[identity]["ap"],
                mp=after["mp"] - observed_before[identity]["mp"],
                wp=after["wp"] - observed_before[identity]["wp"],
                states=after["states"] - observed_before[identity]["states"],
                position_before=observed_before[identity]["position"],
                position_after=after["position"],
                changed_statistics=[
                    stat
                    for stat, value in after["stats"].items()
                    if observed_before[identity]["stats"].get(stat) != value
                ],
            )
            for identity, after in observed_after.items()
            if identity in observed_before
        }
        added_actors = sorted(set(observed_after) - set(observed_before))
        result.update(
            status="validated",
            packets=len(packets),
            actor_deltas=deltas,
            added_actor_ids=added_actors,
            scenario=success.get("scenario"),
            scenario_receipt=getattr(fight, "validation_scenario_receipt", None),
            native_initialization=getattr(
                fight, "native_npc_initialization_receipts", {}
            ).get(-200),
            forecast_source_unchanged=True,
            serializer_failure_rolled_back=True,
            committed_state_changed=True,
            owned_object_identities_preserved=True,
            event_kinds=[e["kind"] for e in runtime.fight.events[event_start:]],
        )
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    print(json.dumps(dict(ai_commit_ref=monster["ref"], **result)), flush=True)
    return result


def class_regressions():
    os.environ["WAKFU_TEST_GRANTEDCAST"] = "1"
    from wakfu_server import native_catalog

    expected_cost_sha = hashlib.sha256(
        native_catalog.read_bytes(
            native_catalog.DATA_ROOT / "native-spell-resource-costs.json"
        )
    ).hexdigest()
    with native_catalog._database().connection() as connection:
        latest_cost = connection.execute(
            "SELECT d.sha256 FROM native_catalog_documents d JOIN native_catalog_releases r USING(revision) "
            "WHERE d.path='native-spell-resource-costs.json' AND r.complete ORDER BY r.completed_at DESC LIMIT 1"
        ).fetchone()
    latest_cost_sha = latest_cost["sha256"] if latest_cost is not None else None
    if latest_cost_sha != expected_cost_sha:
        raise ValueError(
            "Huppermage test staged resource-cost authority differs from candidate dependency"
        )
    sys.path.insert(0, str(ROOT / "server/tests"))
    names = CLASS_TEST_MODULES
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    stream = io.StringIO()
    outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return dict(
        run=outcome.testsRun,
        failures=[dict(test=str(t), traceback=trace) for t, trace in outcome.failures],
        errors=[dict(test=str(t), traceback=trace) for t, trace in outcome.errors],
        skipped=[dict(test=str(t), reason=reason) for t, reason in outcome.skipped],
        successful=outcome.wasSuccessful(),
        log=stream.getvalue(),
        resource_cost_sha256=expected_cost_sha,
        hupper_latest_staged_cost_sha256=latest_cost_sha,
        native_opt_in=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--only-ref", type=int, action="append")
    parser.add_argument("--skip-class-tests", action="store_true")
    parser.add_argument("--class-tests-only", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--extend-results", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--reuse-commit-checks", action="store_true")
    parser.add_argument("--baseline-report", type=Path)
    parser.add_argument(
        "--native-monsters",
        type=Path,
        default=ROOT / ".runtime/monster-combat-extraction-20261010/monsters.json.gz",
    )
    args = parser.parse_args()
    if (ROOT / ".runtime").resolve() not in args.output.resolve().parents:
        parser.error("Validation artifacts must stay beneath .runtime")
    os.environ.setdefault("PGOPTIONS", "-c default_transaction_read_only=on")
    gc.disable()
    started = time.monotonic()
    initial_sources = source_hashes()
    initial_tests = test_hashes()
    initial_validator = digest(Path(__file__))
    manifest = install_overlay(args.candidate, overlay=not args.baseline)
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.monsters import native_abilities, reference

    rows = json.loads((args.candidate / "monster-status.json").read_text())["monsters"]
    selected = set(manifest["selected_references"])
    if args.only_ref:
        selected &= set(args.only_ref)
    result = dict(
        schema="native-npc-activation-validation-v1",
        activated=False,
        candidate_manifest_sha256=digest(args.candidate / "manifest.json"),
        changed_document_hashes=manifest["changed_documents"],
        base_revision=manifest["base_revision"],
        base_document_hashes=manifest["audited_base_document_hashes"],
        runtime_code_sha256=initial_sources,
        test_code_sha256=initial_tests,
        test_scope=CLASS_TEST_MODULES,
        validator_sha256=initial_validator,
        native_monsters_sha256=digest(args.native_monsters),
        overlay_applied="resource_cost_dependency_only"
        if args.baseline
        else "npc_candidate",
        validation_scope="Fresh owned map1134 fights, native QI terrain and explicitly empty serialized QL obstacles; finite self/enemy/empty and legally wounded ally target search; exact native constructor receipts required",
        monsters=[],
        class_tests=None,
    )
    if args.resume:
        previous = json.loads(args.resume.read_text())
        validate_receipt_context(previous, result)
        result["resumed_receipt_sha256"] = digest(args.resume)
        result["monsters"] = previous["monsters"]
        selected -= {row["ref"] for row in previous["monsters"]}
    native_monsters = {
        row["ref"]: row
        for row in json.load(gzip.open(args.native_monsters, "rt"))["monsters"]
    }
    global NATIVE_SOURCE_MONSTERS
    NATIVE_SOURCE_MONSTERS = native_monsters
    result["native_monsters_sha256"] = digest(args.native_monsters)
    if args.class_tests_only:
        selected = set()
    cells = published_geometry(1134).cells
    # Native catalogs remain live for this entire validation process. Avoid
    # traversing their large immutable graphs after every simulated encounter.
    gc.freeze()
    for row in rows:
        if row["ref"] not in selected:
            continue
        source = native_monsters[row["ref"]]
        cases = [
            run_case(
                row["ref"],
                level,
                a["spell_id"],
                a["spell_level"],
                cells,
                args.max_attempts,
            )
            for level in range(row["min_level"], row["max_level"] + 1)
            for a in native_abilities(row["ref"], level)
        ]
        pending_initialization = bool(source["initial_state_triples"]) and not all(
            any(
                initialization_proven(
                    row["ref"], level, source["initial_state_triples"], receipt
                )
                for case in cases
                if case["level"] == level
                for receipt in case.get("initialization_receipts", [])
            )
            for level in range(row["min_level"], row["max_level"] + 1)
        )
        status = (
            "validated"
            if cases
            and all(c["status"] == "validated" for c in cases)
            and not pending_initialization
            else "pending"
        )
        result["monsters"].append(
            dict(
                ref=row["ref"],
                name=row.get("name"),
                status=status,
                pending_initialization=pending_initialization,
                cases=cases,
            )
        )
        result["summary"] = dict(Counter(m["status"] for m in result["monsters"]))
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                dict(
                    ref=row["ref"],
                    status=status,
                    cases=len(cases),
                    validated=sum(c["status"] == "validated" for c in cases),
                )
            ),
            flush=True,
        )
        gc.collect()
        gc.freeze()
    if args.extend_results:
        previous = json.loads(args.extend_results.read_text())
        validate_receipt_context(previous, result)
        if (
            not previous.get("sources_stable")
            or not previous.get("tests_stable")
            or not previous.get("validator_stable")
        ):
            raise ValueError("Cannot extend unstable validation receipts")
        result["monsters"] = previous["monsters"]
        result["preview_runtime_code_sha256"] = previous["runtime_code_sha256"]
        result["preview_changed_runtime_sources"] = sorted(
            k
            for k, v in previous["runtime_code_sha256"].items()
            if result["runtime_code_sha256"].get(k) != v
        )
        result["preview_sources_match_current"] = not result[
            "preview_changed_runtime_sources"
        ]
        for monster in result["monsters"]:
            if monster["status"] == "validated":
                if args.reuse_commit_checks:
                    if (
                        not result["preview_sources_match_current"]
                        or "ai_commit" not in monster
                    ):
                        raise ValueError(
                            "Cannot reuse AI checks after runtime changes or without proof"
                        )
                else:
                    monster["ai_commit"] = commit_smoke(monster)
                if monster["ai_commit"]["status"] != "validated":
                    monster["status"] = "pending"
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
            gc.collect()
            gc.freeze()
        result["summary"] = dict(Counter(m["status"] for m in result["monsters"]))
    if not args.skip_class_tests:
        result["class_tests"] = class_regressions()
        if args.baseline_report:
            baseline = json.loads(args.baseline_report.read_text())
            validate_receipt_context(baseline, result)
            if not baseline.get("sources_stable"):
                raise ValueError("Cannot compare classes against unstable baseline")

            def failures(report):
                return {
                    (kind, row["test"], row["traceback"].strip().splitlines()[-1])
                    for kind in ("failures", "errors")
                    for row in report["class_tests"][kind]
                }

            old, new = failures(baseline), failures(result)
            result["class_tests"]["baseline_comparison"] = dict(
                baseline_report_sha256=digest(args.baseline_report),
                baseline_run=baseline["class_tests"]["run"],
                candidate_run=result["class_tests"]["run"],
                added_failures=sorted(new - old),
                removed_failures=sorted(old - new),
                unchanged_failures=sorted(new & old),
                baseline_successful=baseline["class_tests"]["successful"],
            )
    result["runtime_code_sha256_after"] = source_hashes()
    result["test_code_sha256_after"] = test_hashes()
    result["tests_stable"] = (
        result["test_code_sha256"] == result["test_code_sha256_after"]
    )
    result["validator_stable"] = initial_validator == digest(Path(__file__))
    result["changed_runtime_sources"] = changed_hashes(
        result["runtime_code_sha256"], result["runtime_code_sha256_after"]
    )
    result["native_monsters_stable"] = result["native_monsters_sha256"] == digest(
        args.native_monsters
    )
    result["sources_stable"] = (
        not result["changed_runtime_sources"]
        and result["validator_stable"]
        and result["tests_stable"]
        and result["native_monsters_stable"]
    )
    for monster in result["monsters"]:
        reasons = []
        if monster["pending_initialization"]:
            reasons.append("native_initial_states_not_initialized")
        if any(c["status"] != "validated" for c in monster["cases"]):
            reasons.append("no_effectful_native_execution_in_finite_target_search")
        if monster.get("ai_commit", {}).get("status", "validated") != "validated":
            reasons.append("ai_delivery_validation_pending")
        monster["pending_reasons"] = reasons
    result["validator_sha256_after"] = digest(Path(__file__))
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                summary=result.get("summary"),
                elapsed=result["elapsed_seconds"],
                class_tests=None
                if result["class_tests"] is None
                else {k: result["class_tests"][k] for k in ("run", "successful")},
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
