"""Paid player movement earns the original nearby five-moon prerequisite."""
import json
from pathlib import Path

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class FulMoonPaidNativePlayerMoonsTests(PostgresCase):
    def test_owned_player_earns_five_original_moons_near_living_boss(self):
        from native_paid_party_fixture import (
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )

        scene = reconstructed_fulmoon_scene(
            json.loads(
                (
                    ROOT / ".runtime/parallel-readiness-20261021/"
                    "supreme-entry-staging/map-1056.json"
                ).read_text()
            )
        )
        scene.update(reference=3870, level=185)
        build = NativePartyBuild(
            8,
            200,
            (4780,),
            ((1, 50), (23, 50), (19, 50), (2, 1), (3, 1), (4, 1), (8, 1)),
        )
        receipt = dict(
            scope="paid_player_original_4211_component",
            full_phase_or_victory=False,
            injected_states_or_resources=False,
            levels=[],
        )
        try:
            with original_bootstrap_publication():
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    _,
                    _,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,),
                    (scene["anchor"],),
                    name_prefix="fulmoon-player-moons",
                    encounter_layout=scene,
                )
            current = PaidComponentRuntime(
                fight, characters, monsters, decks, map_id=1056
            )
            identity = next(iter(characters))
            receipt["premise"] = premise
            current.runtime.turn_started(arm_deadline=False)

            def level():
                return sum(
                    entry.level
                    for entry in current.fight.actors[identity].state_ledger.entries
                    if entry.reference == 4211
                )

            def own_turn():
                for _ in range(16):
                    self.assertEqual(current.fight.phase, "active")
                    if current.fight.current.id == identity:
                        return
                    current.advance()
                self.fail("Actual player turn was not reached")

            own_turn()
            destination = (-4, -1, 0)
            self.assertIn(destination, scene["native_border_cells"])
            for _ in range(4):
                path = current.path_to(identity, lambda cell: cell == destination)
                self.assertIsNotNone(path)
                if not path:
                    break
                self.assertTrue(current.player_move_prefix(identity, path))
                if current.fight.actors[identity].position != destination:
                    current.advance()
                    own_turn()
            self.assertEqual(current.fight.actors[identity].position, destination)
            receipt["levels"].append(level())
            self.assertGreater(level(), 0)
            for _ in range(8):
                if level() >= 5:
                    break
                # Paid exits and reentries deliver the original entry10001 callback.
                other = (
                    (-3, -1, 0)
                    if current.fight.actors[identity].position == destination
                    else destination
                )
                path = current.path_to(identity, lambda cell: cell == other)
                self.assertIsNotNone(path)
                if not current.player_move_prefix(identity, path):
                    current.advance()
                    own_turn()
                    continue
                receipt["levels"].append(level())
            self.assertEqual(level(), 5)
            player, boss = current.fight.actors[identity], current.fight.actors[-200]
            distance = abs(player.position[0] - boss.position[0]) + abs(
                player.position[1] - boss.position[1]
            )
            self.assertLessEqual(distance, 5)
            self.assertGreater(boss.hp, 1)
            receipt.update(
                status="original_nearby_player_five_moons_earned",
                position=player.position,
                boss_position=boss.position,
                distance=distance,
                payments=current.payments,
            )
        finally:
            if "current" in locals():
                receipt["payments"] = current.payments
            (
                ROOT
                / ".runtime/ultimate-scenes-20261021/fulmoon-paid-native-player-moons.json"
            ).write_text(json.dumps(receipt, indent=2, default=str) + "\n")
