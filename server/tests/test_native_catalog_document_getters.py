"""Sparse original records exercise real getters; publication transport is bounded.

This does not qualify full publication completeness or Ready. Unprovided rows
and whole enumerations fail rather than fabricating source definitions.
"""
from collections import OrderedDict
from contextlib import ExitStack
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class NativeCatalogDocumentGetterTests(unittest.TestCase):
    def test_targeted_copied_qualifier_and_idle_chunks_never_scan_published_populations(
        self,
    ):
        self._targeted_access_only = True
        self.test_original_json_getters_parent_guards_and_bounded_ordered_headers()

    def _exercise_targeted_qualifiers_and_idle(
        self, requests, publication, publication_rows
    ):
        from unittest.mock import MagicMock
        from wakfu_server import native_compiled_catalog as transport
        from wakfu_server.combat_published_catalogs import (
            resolve_static_catalog_descriptor,
            POLICY,
        )
        from wakfu_server.combat_static_catalogs import DefinitionOverlay
        from wakfu_server.combat_copied_equipment_plan import (
            copied_equipment_plan,
            SOURCE,
        )
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server import (
            combat_server_spell,
            combat_static_catalogs,
            combat_actor_snapshot,
        )
        from wakfu_server.combat_equipment_opposed_damage_contract import (
            copied_opposed_damage_root,
        )
        from wakfu_server.equipment_level_groups import qualify_plan
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server import monster_idle_distribution_store as idle, combat_terrain

        path = Path(
            ".runtime/world-external-catalogs-20261024/copied-opposed-original.json"
        )
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "5bce73caaa2f35caa8b536b6509eb82f3a17f1e0c6d8d416049fd2481cfa637f",
        )
        fixture = json.loads(raw)
        records = {
            (r["path"], r["collection"], r["key"]): r["payload"]
            for r in fixture["records"]
        }
        rows = {}
        descriptors = {}
        reads = []
        locked = {"value": False}
        generation = "c" * 64

        def add(name, values, count, representation="native_json"):
            rows[name] = values
            descriptor = dict(
                policy=POLICY,
                revision=generation,
                manifest_sha256=generation,
                collection=name,
                count=count,
                ordered_keys_sha256=hashlib.sha256(
                    json.dumps(list(values)).encode()
                ).hexdigest(),
            )
            descriptors[name] = descriptor
            return resolve_static_catalog_descriptor(descriptor)

        class Reader:
            def __init__(self, descriptor):
                self.descriptor = descriptor
                self.representation = (
                    "frozen_effect"
                    if descriptor["collection"] == "targeted/effects"
                    else "native_json"
                )

            def __iter__(self):
                raise AssertionError(
                    "Global published population traversal is forbidden"
                )

            def __contains__(self, key):
                return key in rows[self.descriptor["collection"]]

            def record_bytes(self, key):
                if locked["value"]:
                    raise AssertionError("Catalog read under idle commit write lock")
                name = self.descriptor["collection"]
                reads.append((name, key))
                return json.dumps(rows[name][key], separators=(",", ":")).encode()

        ordinary_reader = transport.published_collection

        def targeted_reader(descriptor):
            if descriptor["collection"] not in rows:
                return ordinary_reader(descriptor)
            return Reader(descriptor)

        with patch.object(
            transport, "published_collection", side_effect=targeted_reader
        ):
            definition = records[
                ("native-copied-equipment-definitions.json", "definitions", "33395")
            ]
            definitions = add(
                "targeted/copied",
                {"33395": definition},
                fixture["source_counts"]["native-copied-equipment-definitions.json"],
            )
            catalog = dict(
                producer=SOURCE,
                complete=True,
                definition_count=len(definitions),
                definitions=definitions,
            )
            plan = copied_equipment_plan(33395, catalog)
            expected_root_order = [
                r["reference"] for r in definition["ordered_effects"]
            ]
            self.assertEqual(
                [r["reference"] for r in plan["roots"]], expected_root_order
            )
            effects = {
                key: value
                for (doc, collection, key), value in records.items()
                if doc == "combat-state-definitions.json" and collection == "effects"
            }
            states = {
                key: value
                for (doc, collection, key), value in records.items()
                if doc == "combat-state-definitions.json" and collection == "states"
            }
            reactive_root = next(
                root for root in plan["roots"] if root["effect_class"] == 304
            )
            local = equipment_effect_definitions({"roots": [reactive_root]})
            root_key = str(reactive_root["reference"])
            # The original expression allowed local roots to override a base key.
            effects[root_key] = dict(local[root_key], criteria="False")
            base = add("targeted/effects", effects, 63120, "frozen_effect")
            state_map = add("targeted/states", states, 289)
            source_effects = add(
                "targeted/state_effects",
                {key: value for key, value in effects.items() if key != root_key},
                63120,
            )
            compiled = SimpleNamespace(
                effects=base,
                source_states={"states": state_map, "effects": source_effects},
            )
            summaries = records[("item-equipment-effects.json", "items", "33395")][
                "effects"
            ]
            with patch.object(
                combat_server_spell, "compiled_runtime_catalog", return_value=compiled
            ), patch.object(
                combat_static_catalogs,
                "characteristic_registry",
                return_value=fixture["registry"],
            ):
                self.assertTrue(
                    copied_opposed_damage_root(
                        reactive_root, plan["native_retained_container"]
                    )
                )
                self.assertIsNone(qualify_plan(plan, summaries, fixture["registry"]))
                self.assertEqual(base[root_key]["criteria"], "False")
                overlay = DefinitionOverlay(base, local)
                self.assertEqual(overlay[root_key], local[root_key])
                self.assertEqual(
                    effect_profile(
                        overlay[root_key], plan["native_retained_container"]["level"]
                    )["parameters"],
                    [9364, 1, -1],
                )
                self.assertEqual(list(overlay._overrides), list(local))
                bad = copy.deepcopy(reactive_root)
                bad["parameters"][0] = 9365
                self.assertFalse(
                    copied_opposed_damage_root(bad, plan["native_retained_container"])
                )
                malformed = copy.deepcopy(reactive_root)
                malformed["children"] = [123]
                with self.assertRaisesRegex(ValueError, "child order"):
                    copied_opposed_damage_root(
                        malformed, plan["native_retained_container"]
                    )
                # Duplicate conflicting local definitions keep their original guard.
                conflict = copy.deepcopy(reactive_root)
                conflict["parameters"][0] += 1
                with self.assertRaisesRegex(ValueError, "Conflicting native copied"):
                    equipment_effect_definitions({"roots": [reactive_root, conflict]})
            self.assertLess(len(reads), 100)

            profiles = {
                key: value
                for (doc, collection, key), value in records.items()
                if doc == "native-actor-characteristics.json"
                and collection == "npc_profiles"
            }
            profile_map = add("targeted/profiles", profiles, 2874)
            proposal = dict(
                world_epoch="bounded",
                scope=[999999, 0],
                empty_generation=1,
                run_id=1,
                chunk_index=0,
            )
            original = dict(
                id=-10,
                ref=4,
                level=1,
                hp=7,
                max_hp=10,
                map_id=999999,
                instance_id=0,
                team=1,
                x=0,
                y=0,
                z=0,
            )
            moved = dict(original, x=3, y=3)
            move = dict(group_id=1, expected_members=[original], moved_members=[moved])
            geometry = {"cells": [(x, y, 0) for x in range(10) for y in range(10)]}

            def scenario(blocker="none", race=False):
                writes = []
                state = dict(
                    status="pending",
                    living=[
                        dict(group_id=1, members=[copy.deepcopy(original)]),
                        dict(
                            group_id=2,
                            members=[dict(original, id=-20, ref=5, x=5, y=5)],
                        ),
                    ],
                    reservation=dict(
                        key=[999999, 0, 3],
                        members=[dict(original, id=-30, ref=6, x=8, y=8)],
                    ),
                )
                if blocker == "living":
                    state["living"][1]["members"][0].update(x=3, y=3)
                elif blocker == "reservation":
                    state["reservation"]["members"][0].update(x=3, y=3)
                db = MagicMock()

                def query(sql, parameters=()):
                    cursor = MagicMock()
                    row = None
                    values = []
                    if sql.startswith("SELECT pg_advisory"):
                        locked["value"] = True
                    elif "SELECT m.group_id,m.expected_members" in sql:
                        values = [copy.deepcopy(move)]
                    elif "SELECT group_payload FROM planting_growth_outbox" in sql:
                        values = [
                            dict(group_payload=copy.deepcopy(state["reservation"]))
                        ]
                    elif sql.startswith("SELECT group_id,members FROM combat_groups"):
                        values = copy.deepcopy(state["living"])
                    elif sql.startswith("SELECT * FROM monster_idle_distribution_runs"):
                        row = dict(id=1, status=state["status"])
                    elif sql.startswith(
                        "SELECT * FROM monster_idle_distribution_moves"
                    ):
                        values = [dict(move, ordinal=0)]
                    elif sql.startswith("SELECT members,instance_id"):
                        row = dict(members=state["living"][0]["members"], instance_id=0)
                    elif sql.startswith("UPDATE combat_groups"):
                        writes.append(sql)
                        state["living"][0]["members"] = copy.deepcopy(parameters[0].obj)
                    elif sql.startswith("UPDATE monster_idle_distribution_moves"):
                        writes.append(sql)
                    elif sql.startswith("UPDATE monster_idle_distribution_runs"):
                        writes.append(sql)
                        state["status"] = "completed"
                    else:
                        raise AssertionError(sql)
                    cursor.fetchone.return_value = row
                    cursor.fetchall.return_value = values
                    cursor.__iter__.return_value = iter(values)
                    return cursor

                db.execute.side_effect = query
                store = MagicMock()
                store.connection.return_value.__enter__.return_value = db
                locked["value"] = False
                start = len(reads)
                prepared = idle.validate_chunk(store, proposal)
                profile_reads = [
                    (name, key)
                    for name, key in reads[start:]
                    if name == "targeted/profiles"
                ]
                self.assertEqual(
                    profile_reads,
                    [("targeted/profiles", key) for key in ("4", "5", "6")],
                )
                self.assertEqual(
                    prepared["radii"],
                    {key: profiles[key]["physical_radius"] for key in ("4", "5", "6")},
                )
                if race:
                    state["living"].append(
                        dict(
                            group_id=4,
                            members=[dict(original, ref=999, id=-40, x=7, y=7)],
                        )
                    )
                count = len(reads)
                outcome = idle.commit(
                    store, None, proposal, episode_current=True, prepared=prepared
                )
                self.assertEqual(len(reads), count)
                if race:
                    self.assertEqual(outcome, [])
                    self.assertEqual(writes, [])
                    self.assertEqual(state["status"], "pending")
                else:
                    self.assertEqual(
                        outcome,
                        [
                            dict(
                                group_id=1,
                                status="applied" if blocker == "none" else "skipped",
                            )
                        ],
                    )
                    self.assertEqual(
                        state["living"][0]["members"],
                        [moved] if blocker == "none" else [original],
                    )
                    self.assertEqual(
                        idle.commit(
                            store,
                            None,
                            proposal,
                            episode_current=True,
                            prepared=prepared,
                        ),
                        [],
                    )
                locked["value"] = False
                return store

            with patch.object(
                combat_actor_snapshot,
                "native_actor_catalog",
                return_value={"npc_profiles": profile_map},
            ), patch.object(combat_terrain, "map_geometry", return_value=geometry):
                scenario()
                scenario("living")
                scenario("reservation")
                scenario(race=True)
                for reference in ("4", "5", "6"):
                    saved = rows["targeted/profiles"].pop(reference)
                    with self.assertRaises(KeyError):
                        scenario()
                    rows["targeted/profiles"][reference] = saved
                for invalid in (True, 128):
                    saved = rows["targeted/profiles"]["4"]["physical_radius"]
                    rows["targeted/profiles"]["4"]["physical_radius"] = invalid
                    with self.assertRaisesRegex(ValueError, "signed-byte"):
                        scenario()
                    rows["targeted/profiles"]["4"]["physical_radius"] = saved

        # Common spell ownership and original costs must not trigger a full merge.
        from wakfu_server import combat_spells, combat_common_spell_catalog

        casting = records[("native-spell-casting.json", "spells", "5623")]
        with patch.object(
            combat_common_spell_catalog, "native_rows", return_value={"5623": casting}
        ):
            reference_costs = combat_common_spell_catalog.merge_cost_records({})["5623"]
        publication_rows["logical/costs"]["5623"] = reference_costs
        collection = publication["collections"]["logical/costs"]
        collection["count"] = len(publication_rows["logical/costs"])
        collection["ordered_keys_sha256"] = hashlib.sha256(
            json.dumps(list(publication_rows["logical/costs"])).encode()
        ).hexdigest()
        with patch.object(
            combat_spells, "_COSTS", combat_spells._cost_records()
        ), patch.object(
            combat_common_spell_catalog,
            "merge_cost_records",
            side_effect=AssertionError("Runtime whole-cost merge forbidden"),
        ):
            character = dict(
                id=501,
                account_id=41,
                breed=8,
                level=130,
                account_quest_items=[dict(account_id=41, reference=26347, quantity=1)],
            )
            actual = combat_spells.base_costs(character, 5623)
            ap, mp, wp = reference_costs["levels"][129]
            self.assertEqual(
                actual,
                dict(
                    ap=ap,
                    mp=mp,
                    wp=wp,
                    conditional_rules=reference_costs["conditional"],
                ),
            )
            with self.assertRaisesRegex(ValueError, "owned/unlocked"):
                combat_spells.base_costs(dict(character, account_quest_items=[]), 5623)
            saved = publication_rows["logical/costs"].pop("5623")
            with self.assertRaisesRegex(ValueError, "Missing native owned spell costs"):
                combat_spells.base_costs(character, 5623)
            publication_rows["logical/costs"]["5623"] = saved

        # The native PC wire must share the combat index, preserving exact bytes.
        import struct
        import sys
        from wakfu_server import wire

        actor_catalog = combat_actor_snapshot.native_actor_catalog()
        legacy_characteristics = {
            str(key): dict(row) for key, row in actor_catalog["characteristics"].items()
        }

        def payload(values):
            return struct.pack(">H", len(values)) + b"".join(
                struct.pack(">Biiii", *row) for row in values
            )

        sparse = payload(
            [
                (1, 50, 0, 100, 0),
                (2, 6, 0, 6, 0),
                (3, 3, 0, 3, 0),
                (33, -10, 0, 0, 0),
                (36, 28, 0, 0, 0),
            ]
        )
        with patch.object(
            combat_actor_snapshot,
            "native_actor_catalog",
            return_value={"characteristics": legacy_characteristics},
        ):
            expected_wire = wire.complete_public_characteristics(sparse)
            expected_zero = wire.complete_public_characteristics(payload([]))
        with combat_actor_snapshot._CHARACTERISTIC_INDEX_LOCK:
            combat_actor_snapshot._CHARACTERISTIC_INDEX.clear()
            combat_actor_snapshot._CHARACTERISTIC_INDEX_BYTES = 0
        before = len(requests)
        self.assertEqual(wire.complete_public_characteristics(sparse), expected_wire)
        self.assertEqual(
            sum(
                name == "native-actor-characteristics.json/characteristics"
                for name, key in requests[before:]
            ),
            92,
        )
        before = len(requests)
        for _ in range(6):
            self.assertEqual(
                wire.complete_public_characteristics(sparse), expected_wire
            )
            self.assertEqual(
                wire.complete_public_characteristics(payload([])), expected_zero
            )
        self.assertEqual(
            sum(
                name == "native-actor-characteristics.json/characteristics"
                for name, key in requests[before:]
            ),
            0,
        )
        for invalid in (
            payload([(1, 1, 0, 1, 0), (1, 2, 0, 2, 0)]),
            payload([(255, 1, 0, 1, 0)]),
        ):
            with self.assertRaisesRegex(ValueError, "Unknown or duplicate"):
                wire.complete_public_characteristics(invalid)
        from wakfu_server import monsters, equipment_hp_lifecycle

        self.assertIs(
            equipment_hp_lifecycle._native_catalog(),
            combat_actor_snapshot.native_actor_catalog(),
        )
        expected_resources = combat_actor_snapshot.native_npc_creation_values(5525, 1)
        before = len(requests)
        with patch.object(
            combat_actor_snapshot,
            "native_npc_creation_values",
            wraps=combat_actor_snapshot.native_npc_creation_values,
        ) as public_values:
            spawned = [
                monsters.owned_instance(
                    5525, 1, -1000 - index, map_id=1134, x=index, y=0, z=0
                )
                for index in range(6)
            ]
            self.assertEqual(public_values.call_count, 6)
            self.assertEqual(
                [call.args for call in public_values.call_args_list], [(5525, 1)] * 6
            )
        for member in spawned:
            self.assertEqual(member["hp"], expected_resources[1]["current"])
            self.assertEqual(member["max_hp"], expected_resources[1]["maximum"])
            self.assertEqual(member["ap"], expected_resources[2]["current"])
            self.assertEqual(member["mp"], expected_resources[3]["current"])
            self.assertEqual(member["wp"], expected_resources[4]["current"])
        self.assertEqual(len({id(member) for member in spawned}), 6)
        self.assertEqual(
            sum(
                name == "native-actor-characteristics.json/characteristics"
                for name, key in requests[before:]
            ),
            0,
        )
        self.assertNotIn("wakfu_server.combat.combat_actor_snapshot", sys.modules)
        output = os.environ.get("WAKFU_TARGETED_CATALOG_RECEIPT")
        if output:
            Path(output).write_text(
                json.dumps(
                    dict(
                        status="PASS",
                        fixture_sha256=hashlib.sha256(raw).hexdigest(),
                        opposed_root=reactive_root["reference"],
                        source_root_order=expected_root_order,
                        copied_qualify_plan=True,
                        global_iteration_forbidden=True,
                        idle_scenarios=[
                            "applied",
                            "living_blocker",
                            "reservation_blocker",
                            "new_species_deferred_no_writes",
                        ],
                        common_spell=5623,
                        common_costs=actual,
                        public_wire_cold_decodes=92,
                        public_wire_warm_decodes=0,
                        wire_legacy_published_identical=True,
                        public_owned_instance_spawn_calls=6,
                        public_spawn_warm_characteristic_decodes=0,
                        hp_lifecycle_public_catalog_identity=True,
                    ),
                    indent=2,
                )
                + "\n"
            )

    def test_published_reward_finish_and_scalar_projection_decode_bounds(self):
        self._reward_finish_only = True
        self.test_original_json_getters_parent_guards_and_bounded_ordered_headers()

    def _exercise_published_reward_finish(self, requests, publication):
        import ast
        import time
        from datetime import datetime, timezone
        from unittest.mock import MagicMock
        from psycopg.pq import TransactionStatus
        from wakfu_server.combat_state import Actor
        from wakfu_server import (
            monsters,
            combat_reward_context,
            combat_drops,
            reward_policy,
        )
        from wakfu_server.combat_spell_level import (
            decoded_spell_levels,
            NativeSpellBook,
        )
        from wakfu_server.combat_native_spell_casting import catalog as casting_catalog
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_published_catalogs import (
            static_row_scalar,
            static_catalog_descriptor,
        )
        from wakfu_server.wakfu_xp import monster_base_xp

        player = Actor(501, 0, (0, 0, 0), 80, 6, 3, 10, 1, owner_id=41, controlled=True)
        # A terminal native actor's authoritative mutable PA, not catalog rows.
        player.effect_stats = {36: 28, 33: 17}
        spawned = monsters.owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
        npc = Actor(
            -200,
            1,
            (1, 0, 0),
            spawned["hp"],
            spawned["ap"],
            spawned["mp"],
            spawned["initiative"],
            1,
        )
        fight = SimpleNamespace(
            id=99, phase="finished", winner=0, actors={501: player, -200: npc}
        )
        character = dict(id=501, account_id=41, level=1)
        context = combat_reward_context.build_context(fight, character, [spawned])
        self.assertEqual(context["winners"][0]["wisdom"], 28)
        self.assertEqual(combat_drops.native_prospection_bonus(player), 17)
        expected_xp = reward_policy.xp_amount(
            character_id=501,
            context=context,
            group_xp=monster_base_xp(1),
            xp_rate_bp=10000,
            conquest_rate_bp=10000,
        )
        self.assertGreater(expected_xp, 0)
        self.assertIsNotNone(
            static_catalog_descriptor(native_actor_catalog()["characteristics"])
        )

        store = MagicMock()
        store.now.return_value = datetime.now(timezone.utc)
        db = MagicMock()
        db.info.transaction_status = TransactionStatus.INTRANS
        receipts = []

        def query(sql, parameters=()):
            cursor = MagicMock()
            cursor.rowcount = 1
            if "FROM sessions WHERE" in sql:
                row = dict(character_id=501)
            elif "SELECT p.team,f.status" in sql:
                row = dict(team=0, status="finished")
            elif "FROM fight_reward_policy_receipts" in sql:
                row = receipts[0] if receipts else None
            elif "FROM fight_rewards" in sql:
                row = None
            elif "FROM combat_reward_policy_active" in sql:
                row = dict(
                    version=1,
                    xp_rate_bp=10000,
                    kamas_rate_bp=10000,
                    conquest_rate_bp=10000,
                )
            elif "FROM combat_reward_monster_levels" in sql:
                row = dict(
                    base_xp=0,
                    min_kamas=0,
                    max_kamas=0,
                    source="declared reward DB transport",
                )
            elif "FROM character_progression" in sql:
                row = dict(xp=0, kamas=0)
            elif sql.startswith("INSERT INTO fight_reward_policy_receipts"):
                receipts.append(
                    dict(
                        account_id=parameters[2],
                        policy_version=parameters[4],
                        snapshot=parameters[5].obj,
                        snapshot_sha256=parameters[6],
                        xp=parameters[7],
                        kamas=parameters[8],
                    )
                )
                row = None
            else:
                raise AssertionError(sql)
            cursor.fetchone.return_value = row
            return cursor

        db.execute.side_effect = query
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "resolve_fight_reward"
        )
        namespace = dict(
            fight=fight,
            character=character,
            TEST_MONSTERS=[spawned],
            combat_reward_context=combat_reward_context,
            reward_policy=reward_policy,
            STORE=store,
            account_id=41,
            generation="owned-generation",
            is_developer_test_fight=lambda db, fight_id: False,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        result = namespace["resolve_fight_reward"](db)
        self.assertEqual(result.xp, expected_xp)
        self.assertEqual(namespace["resolve_fight_reward"](db), result)
        self.assertEqual(len(receipts), 1)
        store.lock_character.assert_called()
        self.assertEqual(receipts[0]["snapshot"]["context"], context)

        before = len(requests)
        for value in (True, 2147483648):
            player.effect_stats[36] = value
            with self.assertRaisesRegex(ValueError, "Wisdom"):
                namespace["resolve_fight_reward"](db)
        del player.effect_stats[36]
        with self.assertRaisesRegex(ValueError, "Wisdom"):
            namespace["resolve_fight_reward"](db)
        player.effect_stats[36] = 28
        del player.effect_stats[33]
        with self.assertRaises(ValueError):
            combat_drops.native_prospection_bonus(player)
        player.effect_stats[33] = 17
        with self.assertRaisesRegex(ValueError, "owned winning"):
            combat_reward_context.build_context(
                fight, dict(character, account_id=42), [spawned]
            )

        definitions = casting_catalog()
        raw_maximum = definitions["7962"]["maximum_level"]
        records = [(100, 7962, 300)]
        expected_levels = {7962: min(300, raw_maximum)}
        samples = []
        for authority in ("decoded_owned", "native_npc"):
            static_row_scalar.cache_clear()
            for mode in ("cold", "warm"):
                count_before = len(requests)
                started = time.perf_counter_ns()
                results = [
                    decoded_spell_levels(records, definitions)
                    if authority == "decoded_owned"
                    else monsters.native_abilities(5525, 1)
                    for _ in range(6)
                ]
                elapsed_ns = time.perf_counter_ns() - started
                reads = [
                    row
                    for row in requests[count_before:]
                    if row[0] == "native-spell-casting.json/spells"
                ]
                self.assertEqual(len(reads), 1 if mode == "cold" else 0)
                if authority == "decoded_owned":
                    books = [NativeSpellBook(levels, False) for levels in results]
                    self.assertTrue(
                        all(book.level(7962) == expected_levels[7962] for book in books)
                    )
                else:
                    self.assertTrue(
                        all(
                            rows
                            == [
                                {
                                    "spell_id": 7962,
                                    "level_parameter": -1,
                                    "spell_level": 1,
                                }
                            ]
                            for rows in results
                        )
                    )
                samples.append(
                    dict(
                        authority=authority,
                        mode=mode,
                        actor_calls=6,
                        casting_record_decodes=len(reads),
                        elapsed_ns=elapsed_ns,
                    )
                )
        from wakfu_server import combat_actor_snapshot as actor_snapshots

        catalog = native_actor_catalog()
        with actor_snapshots._CHARACTERISTIC_INDEX_LOCK:
            actor_snapshots._CHARACTERISTIC_INDEX.clear()
            actor_snapshots._CHARACTERISTIC_INDEX_BYTES = 0
        prior_values = None
        for mode in ("cold", "warm"):
            count_before = len(requests)
            started = time.perf_counter_ns()
            values = [
                actor_snapshots.native_npc_creation_values(5525, 1) for _ in range(6)
            ]
            elapsed_ns = time.perf_counter_ns() - started
            decodes = sum(
                name == "native-actor-characteristics.json/characteristics"
                for name, key in requests[count_before:]
            )
            self.assertEqual(decodes, 92 if mode == "cold" else 0)
            self.assertTrue(all(value == values[0] for value in values))
            if prior_values is not None:
                self.assertEqual(values, prior_values)
            prior_values = values
            samples.append(
                dict(
                    authority="native_characteristic_projection",
                    mode=mode,
                    actor_calls=6,
                    characteristic_record_decodes=decodes,
                    elapsed_ns=elapsed_ns,
                )
            )
        frozen_rows = actor_snapshots._rows(catalog)
        self.assertEqual(dict(frozen_rows[36]), catalog["characteristics"]["36"])
        with self.assertRaises(TypeError):
            frozen_rows[36]["name"] = "forged"
        old_generation = publication["generation"]
        publication.update(generation="b" * 64, manifest_sha256="b" * 64)
        native_actor_catalog.cache_clear()
        count_before = len(requests)
        changed_rows = actor_snapshots._rows(native_actor_catalog())
        self.assertEqual(
            sum(
                name == "native-actor-characteristics.json/characteristics"
                for name, key in requests[count_before:]
            ),
            92,
        )
        self.assertEqual(dict(changed_rows[36]), dict(frozen_rows[36]))
        publication.update(generation=old_generation, manifest_sha256=old_generation)
        native_actor_catalog.cache_clear()
        legacy_rows = {str(key): dict(value) for key, value in frozen_rows.items()}
        legacy = {"characteristics": legacy_rows}
        legacy_rows["36"]["hard_maximum"] -= 1
        self.assertEqual(
            actor_snapshots._rows(legacy)[36]["hard_maximum"],
            legacy_rows["36"]["hard_maximum"],
        )
        legacy_rows["01"] = dict(legacy_rows["1"])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            actor_snapshots._rows(legacy)
        del legacy_rows["01"]
        del legacy_rows["1"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            actor_snapshots._rows(legacy)
        # Legacy mutable input never inherits cached metadata from a publication.
        private = {"7962": {"maximum_level": 5}}
        self.assertEqual(decoded_spell_levels(records, private), {7962: 5})
        private["7962"]["maximum_level"] = 7
        self.assertEqual(decoded_spell_levels(records, private), {7962: 7})
        static_row_scalar.cache_clear()
        output = os.environ.get("WAKFU_REWARD_PROJECTION_RECEIPT")
        if output:
            Path(output).write_text(
                json.dumps(
                    dict(
                        status="PASS",
                        xp=expected_xp,
                        wisdom=28,
                        prospection=17,
                        actual_world_reward_callback=True,
                        real_database=False,
                        benchmark_scope="Six calls per mode on one original spell row, not World latency",
                        samples=samples,
                    ),
                    indent=2,
                )
                + "\n"
            )

    def test_original_json_getters_parent_guards_and_bounded_ordered_headers(self):
        from wakfu_server import native_catalog
        from wakfu_server import native_compiled_catalog as transport
        from wakfu_server import native_catalog_document as documents
        from wakfu_server.combat_published_catalogs import (
            POLICY,
            static_catalog_descriptor,
        )
        from tools.sublimation_published_metadata import PublishedMetadataPack

        path = Path(".runtime/catalog-document-getter-qa/original-records.json")
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "80c4b5b0108105541491b117af7f07febbd6bdf8dce3cef3693ca33ee6e19a91",
        )
        original = json.loads(raw)
        by_source = {}
        for row in original["records"]:
            by_source.setdefault((row["path"], row["collection"]), OrderedDict())[
                row["key"]
            ] = row["payload"]
        source_hashes = {r["path"]: r["sha256"] for r in original["documents"]}
        generation = "a" * 64
        publication = dict(
            generation=generation,
            manifest_sha256=generation,
            source_documents=source_hashes,
            raw_documents={},
            documents={},
            collections={},
        )
        rows_by_collection = {}
        requests = []

        def collection(name, rows, *, count=None):
            rows_by_collection[name] = rows
            keys = list(rows)
            row = dict(
                collection=name,
                kind="dict",
                count=len(rows) if count is None else count,
                ordered_keys_sha256=hashlib.sha256(
                    json.dumps(keys).encode()
                ).hexdigest(),
                representation="native_json",
            )
            publication["collections"][name] = row
            return {
                k: row[k]
                for k in ("collection", "kind", "count", "ordered_keys_sha256")
            }

        def source(path, name):
            return copy.deepcopy(by_source[(path, name)])

        def document(key, columns, header=None, *, logical=False, counts=None):
            header = {} if header is None else header
            entries = {
                name: collection(
                    key + "/" + name,
                    values,
                    count=None if counts is None else counts.get(name),
                )
                for name, values in columns.items()
            }
            encoded = json.dumps(header, ensure_ascii=True, separators=(",", ":"))
            entry = dict(
                root_kind="dict",
                layout=list(header) + list(columns),
                header=json.loads(json.dumps(header, sort_keys=True)),
                header_json=encoded,
                header_bytes=len(encoded.encode()),
                collections=entries,
            )
            if not logical:
                entry["source_sha256"] = source_hashes[key]
            publication["documents" if logical else "raw_documents"][key] = entry

        actor_path = "native-actor-characteristics.json"
        document(
            actor_path,
            {"characteristics": source(actor_path, "characteristics")},
            {"ordered_metadata": {"z": [2, {"b": 3, "a": 4}], "a": 1}},
        )
        if getattr(self, "_reward_finish_only", False) or getattr(
            self, "_targeted_access_only", False
        ):
            # Add the actual finite NPC constructor profile for the reward
            # fixture, retaining all original source values and default radii.
            semantic_inputs = json.loads(
                Path(
                    ".runtime/sublimation-phase1-dataset/manifest-semantic.json"
                ).read_bytes()
            )
            actor_input = semantic_inputs["documents"][actor_path]
            actor_bytes = Path(actor_input["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(actor_bytes).hexdigest(), actor_input["sha256"]
            )
            actor_source = json.loads(actor_bytes)
            header = {
                key: value
                for key, value in actor_source.items()
                if key not in ("characteristics", "npc_profiles")
            }
            document(
                actor_path,
                {
                    "characteristics": source(actor_path, "characteristics"),
                    "npc_profiles": actor_source["npc_profiles"],
                },
                header,
            )
        state_path = "combat-state-definitions.json"
        document(
            state_path,
            {
                "states": source(state_path, "states"),
                "effects": source(state_path, "effects"),
            },
        )
        spell_path = "native-spell-casting.json"
        document(spell_path, {"spells": source(spell_path, "spells")})
        npc_path = "native-npc-spell-effect-trees.json"
        document(
            npc_path,
            {
                "spells": source(npc_path, "spells"),
                "activation_policy": source(npc_path, "activation_policy"),
            },
        )
        retained_path = "native-retained-effect-metadata.json"
        document(retained_path, {"states": source(retained_path, "states")})
        costs = source("spell-costs.json", "spells")
        document("spell-costs.json", {"spells": costs})
        cost_entry = collection("logical/costs", costs)
        publication["documents"]["spell_audit.costs_catalog"] = dict(
            root_kind="record_mapping", root_collection=cost_entry["collection"]
        )
        document(
            "spell_audit.catalog",
            {"spells": source("spell-effect-trees.json", "spells")},
            logical=True,
        )
        document(
            "combat_casting_context.casting_root_catalog",
            {"roots": source("native-class-casting-roots.json", "roots")},
            logical=True,
        )
        for name in (
            "native-direct-target-policies.json",
            "native-zone-trigger-policies.json",
        ):
            document(
                name,
                {"effects": source(name, "effects")},
                {"schema": 1, "source_count": 1},
            )
        area_path = "native-area-effect-trees.json"
        document(area_path, {"effects": source(area_path, "effects")})
        for name, header in (
            ("item-recycling-metadata.json", {"record_count": 20230, "error_count": 0}),
            (
                "item-exchange-metadata.json",
                {"raw_records": 20230, "loaded_records": 20230, "errors": 0},
            ),
        ):
            # Count is the original full index contract; the sparse transport
            # refuses whole traversal instead of supplying invented item rows.
            document(
                name, {"items": source(name, "items")}, header, counts={"items": 20230}
            )
        copy_path = "native-copied-equipment-definitions.json"
        document(
            copy_path,
            {"definitions": source(copy_path, "definitions")},
            {"complete": True},
        )

        class Reader:
            representation = "native_json"

            def __init__(self, descriptor):
                self.descriptor = descriptor
                self.rows = rows_by_collection[descriptor["collection"]]

            def record_bytes(self, key):
                requests.append((self.descriptor["collection"], key))
                if key not in self.rows:
                    raise KeyError(key)
                return json.dumps(self.rows[key], separators=(",", ":")).encode()

            def __iter__(self):
                if len(self.rows) != self.descriptor["count"]:
                    raise AssertionError(
                        "Sparse qualification forbids whole catalog traversal"
                    )
                return iter(self.rows)

            def __contains__(self, key):
                return key in self.rows

            def get_many_bytes(self, keys):
                return {key: self.record_bytes(key) for key in keys if key in self.rows}

        manifest_path = Path("server/data/installation/catalogs/manifest.json")
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw)
        small_sources = PublishedMetadataPack(
            manifest_path,
            revision=manifest["releases"][0]["revision"],
            manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        )
        raw_loads = []
        semantic = json.loads(
            Path(
                ".runtime/sublimation-phase1-dataset/manifest-semantic.json"
            ).read_bytes()
        )
        imported_bytes = 0

        def small_load(path):
            nonlocal imported_bytes
            name = native_catalog._key(path)
            raw_loads.append(name)
            # Unrelated import metadata can use original bounded published bytes;
            # all converted documents must exclusively use indexed transport.
            if name in publication["raw_documents"]:
                raise AssertionError("Eager converted native document: " + name)
            if name in semantic["documents"]:
                entry = semantic["documents"][name]
                bounded = Path(entry["path"])
                if not bounded.is_absolute():
                    bounded = Path.cwd() / bounded
                content = bounded.read_bytes()
                if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                    raise AssertionError("Original bounded import checksum mismatch")
            else:
                content = small_sources.read(name)
            imported_bytes += len(content)
            if imported_bytes > 16 * 1024 * 1024:
                raise AssertionError("Import metadata exceeds lightweight budget")
            return json.loads(content)

        cached = []
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(os.environ, WAKFU_COMPILED_CATALOG_BUILD="0")
            )
            stack.enter_context(
                patch.object(
                    native_catalog, "release", return_value=original["source_revision"]
                )
            )
            stack.enter_context(
                patch.object(native_catalog, "load", side_effect=small_load)
            )
            stack.enter_context(
                patch.object(transport, "resolve_publication", return_value=publication)
            )
            stack.enter_context(
                patch.object(transport, "published_collection", side_effect=Reader)
            )
            try:
                callback = getattr(self, "_publication_check", None)
                if callback is not None:
                    callback(requests, publication, rows_by_collection)
                    return
                if getattr(self, "_targeted_access_only", False):
                    self._exercise_targeted_qualifiers_and_idle(
                        requests, publication, rows_by_collection
                    )
                    return
                if getattr(self, "_reward_finish_only", False):
                    self._exercise_published_reward_finish(requests, publication)
                    return
                modules = {
                    name: importlib.import_module("wakfu_server." + name)
                    for name in (
                        "spell_audit",
                        "combat_native_spell_casting",
                        "combat_actor_snapshot",
                        "combat_retained_runtime",
                        "combat_npc_attack",
                        "combat_casting_context",
                        "combat_direct_target",
                        "combat_trigger_identifiers",
                        "combat_effect_area_catalog",
                        "equipment_characteristics",
                        "combat_character_copy_equipment",
                    )
                }
                getters = (
                    modules["spell_audit"].catalog,
                    modules["spell_audit"].states_catalog,
                    modules["spell_audit"].costs_catalog,
                    modules["combat_native_spell_casting"].catalog,
                    modules["combat_actor_snapshot"].native_actor_catalog,
                    modules["combat_retained_runtime"].native_retained_metadata,
                    modules["combat_npc_attack"].npc_spell_catalog,
                    modules["combat_casting_context"].casting_root_catalog,
                    modules["combat_direct_target"].native_direct_target_policies,
                    modules["combat_trigger_identifiers"].zone_trigger_policies,
                    modules["combat_effect_area_catalog"].area_effect_catalog,
                    modules["equipment_characteristics"].native_rows,
                    modules[
                        "combat_character_copy_equipment"
                    ].native_copied_equipment_catalog,
                )
                cached.extend(getters)
                for getter in getters:
                    getter.cache_clear()
                    self.assertIsNotNone(getter())
                self.assertEqual(raw_loads.count("native-spell-casting.json"), 0)
                self.assertEqual(raw_loads.count("combat-state-definitions.json"), 0)
                caster = modules["combat_native_spell_casting"]
                record, index = caster.native_casting_table(7962, 1)
                self.assertIs(type(record), dict)
                self.assertIs(type(record["levels"]), list)
                self.assertEqual(index, 0)
                self.assertEqual(record, source(spell_path, "spells")["7962"])
                record["levels"].clear()
                self.assertTrue(caster.native_casting_table(7962, 1)[0]["levels"])
                from wakfu_server.combat_definitions import state_profile

                actual = state_profile(modules["spell_audit"].states_catalog(), 5995, 1)
                expected = state_profile(
                    {
                        "states": source(state_path, "states"),
                        "effects": source(state_path, "effects"),
                    },
                    5995,
                    1,
                )
                self.assertEqual(actual, expected)
                from wakfu_server.combat_drops import native_prospection_bonus

                self.assertEqual(
                    native_prospection_bonus(SimpleNamespace(effect_stats={33: 17})), 17
                )
                policy = modules["combat_npc_attack"].npc_spell_catalog()[
                    "activation_policy"
                ]
                self.assertIsNotNone(static_catalog_descriptor(policy))
                from wakfu_server.combat_npc_activation import imports_enabled
                from wakfu_server.combat_npc_event_controller import (
                    event_controller_record,
                )

                reference, activation = next(
                    (int(k), v)
                    for k, v in policy["enabled_monsters"].items()
                    if v.get("spell_ids") and "event_controller" not in v
                )
                self.assertTrue(
                    imports_enabled(
                        policy,
                        reference,
                        activation["min_level"],
                        activation["spell_ids"][0],
                    )
                )
                self.assertIsNone(
                    event_controller_record(policy, reference, activation["min_level"])
                )
                with self.assertRaises(ValueError):
                    native_prospection_bonus(SimpleNamespace(effect_stats={}))
                with self.assertRaises(ValueError):
                    imports_enabled(SimpleNamespace(), reference, 1, 1)
                equipment = modules["equipment_characteristics"].native_rows()
                self.assertEqual(
                    equipment[33], source(actor_path, "characteristics")["33"]
                )
                self.assertTrue(all(type(key) is int for key in equipment))
                recycling = importlib.import_module("wakfu_server.recycling")
                exchange = importlib.import_module("wakfu_server.exchange_rules")
                costs_module = importlib.import_module("wakfu_server.combat_spells")
                self.assertEqual(
                    recycling._catalog_document()["items"]["12"],
                    source("item-recycling-metadata.json", "items")["12"],
                )
                self.assertEqual(
                    exchange._catalog_document()["items"]["12"],
                    source("item-exchange-metadata.json", "items")["12"],
                )
                self.assertEqual(costs_module._cost_records()["4778"], costs["4778"])
                copied = modules[
                    "combat_character_copy_equipment"
                ].native_copied_equipment_catalog()
                self.assertEqual(
                    copied["definitions"]["12"], source(copy_path, "definitions")["12"]
                )
                loaded = documents.load_published_document(actor_path)
                self.assertEqual(list(loaded["ordered_metadata"]), ["z", "a"])
                self.assertEqual(list(loaded["ordered_metadata"]["z"][1]), ["b", "a"])
                loaded["ordered_metadata"]["z"].clear()
                self.assertTrue(
                    documents.load_published_document(actor_path)["ordered_metadata"][
                        "z"
                    ]
                )
                self.assertTrue(
                    documents.is_native_json_mapping(loaded["characteristics"])
                )
                self.assertFalse(documents.is_native_json_mapping(SimpleNamespace()))
                entry = publication["raw_documents"][actor_path]
                saved = copy.deepcopy(entry)
                entry["source_sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "original source"):
                    documents.load_published_document(actor_path)
                entry.clear()
                entry.update(copy.deepcopy(saved))
                entry["header_json"] = json.dumps({"oversized": "x" * 65536})
                with self.assertRaisesRegex(ValueError, "header bound"):
                    documents.load_published_document(actor_path)
                entry.clear()
                entry.update(copy.deepcopy(saved))
                entry["header_bytes"] += 1
                with self.assertRaisesRegex(ValueError, "ordered JSON"):
                    documents.load_published_document(actor_path)
                entry.clear()
                entry.update(copy.deepcopy(saved))
                entry["collections"]["characteristics"]["count"] += 1
                with self.assertRaisesRegex(ValueError, "differs from publication"):
                    documents.load_published_document(actor_path)
                self.assertTrue(requests)
            finally:
                for getter in cached:
                    getter.cache_clear()
