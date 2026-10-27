"""Bounded native lifecycle history versus signed-byte presentation capacity."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class RiftHistoricalRosterProjectionTests(unittest.TestCase):
    def test_native_retirement_keeps_history_but_bounds_wave_and_reconnect_rosters(
        self,
    ):
        from wakfu_server import native_catalog
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor import actual_monster_actor_stats
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            register_global_fighter,
            set_global_fighter_status,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
            current_registry,
        )
        from wakfu_server.combat_timeline_snapshot import insert
        from wakfu_server.combat_ordinary_qi_retirement import (
            complete_ordinary_qi_death,
        )
        from wakfu_server.combat_snapshot_actor_visibility import (
            hidden_snapshot_actor_ids,
        )
        from wakfu_server.combat_recovery import timeline
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_wire import arena, decode_bootstrap
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.rift_npc_creation import prepare_wave_npcs
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_combat_adapter import world_snapshot, creation_replay
        from wakfu_server.rift_currency_rewards import reward_context
        from wakfu_server.monsters import owned_instance

        manifest_path = os.environ.get("WAKFU_SUBLIMATION_SEMANTIC_MANIFEST")
        if not manifest_path:
            raise RuntimeError(
                "Historical Rift component requires the bounded source manifest"
            )
        manifest = json.loads(Path(manifest_path).read_bytes())
        root = Path(__file__).resolve().parents[2]

        def read_published(name):
            entry = manifest["documents"].get(name)
            if entry is None:
                raise ValueError("Unlisted historical-roster source: " + name)
            path = Path(entry["path"])
            raw = (path if path.is_absolute() else root / path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("Historical-roster bounded source changed")
            return raw

        # Only hash-pinned native document bytes are supplied. NPC creation,
        # damage, retirement, QI, roster, source and reward validators are real.
        with patch.object(
            native_catalog, "release", return_value=manifest["revision"]
        ), patch.object(native_catalog, "_read_published", side_effect=read_published):
            sources = {}

            def monster(identity, x, y):
                source = owned_instance(
                    5525, 1, identity, map_id=1134, instance_id=9, x=x, y=y, z=0
                )
                sources[identity] = source
                return source

            first, survivor = prepare_wave_npcs(
                [
                    monster(-200, 3, 3),
                    monster(-201, 3, 1),
                ]
            )
            pc = Actor(
                7, 0, (0, 0, 0), 100, 6, 6, 10000, 1, owner_id=1, controlled=True
            )
            pc.physical_radius = 0
            pc.native_fight_property_counts = {}
            pc.effect_stats = {1: 100, 2: 6, 3: 6, 4: 0, 36: 0}
            cells = {(x, y, 0) for x in range(4) for y in range(4)}
            edges = {
                (a, b)
                for a in cells
                for b in cells
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            }
            fight = Fight(
                99,
                [pc, first, survivor],
                cells,
                {0: {pc.position}, 1: {first.position, survivor.position}},
                valid_edges=edges,
            )
            fight.native_qi_snapshot = dict(
                x=0, y=0, width=4, height=4, cell_masks=[0x100] * 16
            )
            initialize_global_pv_collections(fight, tuple(fight.actors))
            install_fresh_actor_slots(
                fight,
                prepare_fresh_actor_slots(
                    fight, physical_radii={identity: 0 for identity in fight.actors}
                ),
            )
            fight.ready(1)

            # Admit and finally retire 130 ordinary actors sequentially. They
            # never exceed four concurrent QI entries; no UID is ever reused.
            for index in range(130):
                actor = prepare_wave_npcs([monster(-1000 - index, 2, 2)])[0]
                registry = current_registry(fight)
                slot = registry.register(
                    dict(
                        identity=["actor", actor.id],
                        position=[2, 2],
                        radius=0,
                        indexed=False,
                        movement_blocking=True,
                    )
                )
                self.assertGreaterEqual(slot, 0)
                actor.native_obstacle_id = slot
                actor.native_controlled_by_ai = False
                fight.native_qi_slots = registry.serialized_slots()
                fight.native_qi_touched_cells = registry.serialized_cells()
                fight.native_qi_byte_topology = registry.serialized_byte_topology()
                fight.actors[actor.id] = actor
                register_global_fighter(fight, actor.id)
                insert(fight, actor.id, len(fight.order))
                fight.order.append(actor.id)
                if getattr(fight, "native_base_turn_order", None) is not None:
                    fight.native_base_turn_order.append(actor.id)
                fight.apply_effect_damage(pc.id, actor.id, actor.hp)
                self.assertTrue(complete_ordinary_qi_death(fight, actor))
                self.assertEqual(actor.native_obstacle_id, -1)

            hidden = hidden_snapshot_actor_ids(fight)
            self.assertEqual(len(hidden), 130)
            self.assertEqual(len(fight.actors), 133)
            self.assertGreater(len(fight.native_timeline_removed), 127)
            timeline(fight, deadline_ms=12345)
            old_actor = fight.actors[-1000]
            stats_before = actual_monster_actor_stats(
                sources[-1000],
                old_actor,
                fight.id,
                wp_current=0,
                wp_maximum=0,
                fight=fight,
            )
            self.assertTrue(stats_before)
            history = {uid: actor for uid, actor in fight.actors.items()}
            source_before = deepcopy(sources)

            # A forged status alone cannot release capacity. OFF_PLAY remains
            # visible, with its original QI slot and reversible corpse identity.
            set_global_fighter_status(fight, first.id, "OUT_OF_PLAY")
            with self.assertRaisesRegex(ValueError, "retirement"):
                hidden_snapshot_actor_ids(fight)
            set_global_fighter_status(fight, first.id, "IN_PLAY")
            fight.apply_effect_damage(pc.id, first.id, first.hp)
            self.assertNotIn(first.id, hidden_snapshot_actor_ids(fight))
            self.assertGreaterEqual(first.native_obstacle_id, 0)
            self.assertTrue(complete_ordinary_qi_death(fight, first))

            policy = dict(
                enabled=True,
                policy_kind="local_dev_not_official",
                turn_budget=40,
                max_members=6,
                classic_wave_size=1,
                ultimate_wave_size=1,
                starting_wave=1,
                selection="uniform_with_replacement",
                scaling="native_base_grade",
                rewards="callback_only",
            )
            catalog = dict(
                wave_id=3, map_id=1134, type="INFINITE_WAVE", species_refs=[5525]
            )
            fight.rift_wave_state = dict(
                instance_id=9,
                wave=1,
                turn_budget=40,
                wave_actor_ids=[survivor.id],
                catalog=catalog,
                policy=policy,
                seed="historical-capacity",
                actor_id_pool=[-2000],
            )
            fight.rift_monsters = deepcopy(sources)
            fight.apply_effect_damage(pc.id, survivor.id, survivor.hp)
            self.assertTrue(complete_ordinary_qi_death(fight, survivor))
            self.assertIsNotNone(fight.rift_wave_state["pending_wave"])
            runtime = RuntimeMessages(fight)
            transition = finish_accepted_action(
                fight, runtime, (), initialize_actor=lambda *_: ()
            )
            self.assertEqual(fight.phase, "active")
            self.assertEqual(fight.rift_wave_state["wave"], 2)
            self.assertIn(13091, [opcode for opcode, _ in transition.packets])
            self.assertEqual(set(fight.actors), set(history) | {-2000})
            for uid, actor in history.items():
                self.assertIs(fight.actors[uid], actor)
            self.assertIs(fight.actors[pc.id], pc)
            for uid in source_before:
                self.assertEqual(fight.rift_monsters[uid], source_before[uid])
            self.assertEqual(
                actual_monster_actor_stats(
                    sources[-1000],
                    old_actor,
                    fight.id,
                    wp_current=0,
                    wp_maximum=0,
                    fight=fight,
                ),
                stats_before,
            )
            self.assertEqual(len(world_snapshot(fight)), 1)
            self.assertEqual(
                [code for code, _ in creation_replay(fight)], [12608, 13091]
            )
            timeline(fight, deadline_ms=12345)

            fight.native_fight_model = 2
            fight.native_retained_tracking = True
            fight.native_retained_records = {}
            fight.native_retained_order = []
            shared = SimpleNamespace(
                runtime=runtime,
                map_id=1134,
                instance_id=9,
                join_context=dict(
                    arena=arena(1134, 0, cells, fight.placement),
                    terrain_effect_id=378,
                    terrain_instance_id=-300,
                    leaders={0: pc.id, 1: -2000},
                ),
            )
            reconnect = owned_snapshot(
                fight,
                shared,
                SimpleNamespace(account_id=1),
                actor_payload=lambda *_: (b"declared-player-or-npc-wire", b"\x00\x00"),
            )
            visible = {
                row["actor_id"]
                for row in decode_bootstrap(reconnect[0][1])["participants"]
            }
            self.assertEqual(visible, {pc.id, -2000})
            self.assertEqual(len(fight.actors), 134)

            # The reward source still sees every genuine old actor and kill;
            # presentation capacity never substitutes a missing actor as dead.
            all_sources = fight.rift_monsters
            roster = dict(
                actor_ids=list(all_sources),
                species_refs=[s["ref"] for s in all_sources.values()],
                actor_species_pairs=[(uid, s["ref"]) for uid, s in all_sources.items()],
            )
            context, killed = reward_context(
                fight,
                dict(id=pc.id, account_id=1, level=1),
                dict(catalog=catalog, policy=policy, instance_id=9, members=[pc.id]),
                [roster],
                [pc.id],
            )
            self.assertIsNotNone(context)
            self.assertEqual(
                {row["actor_id"] for row in killed}, set(history) - {pc.id}
            )
