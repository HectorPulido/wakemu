"""Native boss-born player counters must grow at real round boundaries."""
from unittest.mock import patch
from postgres_case import PostgresCase


class SupremePlayerTableStatesTests(PostgresCase):
    def test_actual_nogord_and_shadow_player_carriers_grow_once_at_table_two(self):
        from native_paid_party_fixture import (
            NativeGear,
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server import combat_encounter_player_table_events as player_tables

        player_tables._declarations.cache_clear()
        self.addCleanup(player_tables._declarations.cache_clear)

        build = NativePartyBuild(
            breed=1,
            level=230,
            active_spells=(6972, 6982),
            aptitudes=((1, 58), (35, 1)),
            gear=tuple(
                NativeGear(ref, slot, damage_mask=26)
                for ref, slot in (
                    (20722, 3),
                    (20723, 5),
                    (20724, 13),
                    (20725, 0),
                    (20726, 12),
                    (20727, 4),
                    (20728, 7),
                    (20729, 15),
                    (20730, 8),
                )
            ),
        )
        for reference, map_id, state_id in ((3433, 1092, 4510), (4770, 1229, 5662)):
            with self.subTest(
                reference=reference
            ), original_bootstrap_publication(), patch.object(
                player_tables, "_database", return_value=self.store
            ):
                scene = resolve_supreme_scene(reference, published_geometry(map_id))
                scene.update(reference=reference, level=200)
                fight, characters, monsters, decks, _, _, _ = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,),
                    (scene["anchor"],),
                    name_prefix="counter-nogord"
                    if reference == 3433
                    else "counter-shadow",
                    encounter_layout=scene,
                    production_scene=True,
                )
                player_id = next(iter(characters))

                def grade(current):
                    entries = [
                        s
                        for s in current.actors[player_id].state_ledger.entries
                        if s.reference == state_id
                    ]
                    self.assertEqual(len(entries), 1)
                    self.assertEqual(entries[0].target_id, player_id)
                    return entries[0].level

                self.assertEqual(grade(fight), 1)
                self.assertFalse(
                    any(
                        s.reference == state_id
                        for s in fight.actors[-200].state_ledger.entries
                    )
                )
                runtime = PaidComponentRuntime(
                    fight, characters, monsters, decks, map_id=map_id
                )
                runtime.runtime.turn_started(arm_deadline=False)
                for _ in range(20):
                    if runtime.fight.native_timeline_round == 2:
                        break
                    self.assertEqual(runtime.fight.phase, "active")
                    runtime.advance()
                self.assertEqual(runtime.fight.native_timeline_round, 2)
                self.assertEqual(grade(runtime.fight), 2)
                record = runtime.fight.native_encounter_scene_round_starts["2"]
                selected = [
                    row for row in record["deliveries"] if row["actor_id"] == player_id
                ]
                self.assertEqual(record["table_turn"], 2)
                self.assertEqual(len(selected), 1)
                self.assertEqual(len(selected[0]["eligible_uids"]), 1)
                # Original boss attacks then kill this solo fixture. Do not
                # bypass them to turn a round-publication check into a fight.
                # Successor ancestry is covered by test_player_table_source_custody.
