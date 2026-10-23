"""Actual native luminous cells prepare the player-side reflection premise."""
from dataclasses import replace
import json
from pathlib import Path

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class TalKashaNativeClairPreparationTests(PostgresCase):
    def test_actual_six_owner_party_earns_clair_from_original_luminous_cell(self):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )

        scene = reconstructed_talkasha_scene(
            json.loads(
                (
                    ROOT / ".runtime/parallel-readiness-20261021/"
                    "supreme-entry-staging/map-1400.json"
                ).read_text()
            )
        )
        scene.update(reference=5500, level=155)
        build = replace(native_endgame_iop_build(), active_spells=(4775,))
        receipt = dict(
            scope="actual_original_1845_entry_earns_clair_preparation",
            injected_states_or_resources=False,
            damage_isolations=[],
            samples=[],
        )
        output = (
            ROOT
            / ".runtime/ultimate-scenes-20261021/talkasha-native-clair-preparation.json"
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
                    (build,) * 6,
                    tuple(scene["party_placement_cells"][:6]),
                    name_prefix="talkasha-clair",
                    encounter_layout=scene,
                )
            current = PaidComponentRuntime(
                fight, characters, monsters, decks, map_id=1400
            )
            receipt.update(premise=premise, scene_policy=scene["policy"])
            self.assertTrue(all(current.fight.actors[i].team == 1 for i in characters))
            self.assertEqual(current.fight.actors[-200].team, 0)
            self.assertTrue(
                any(
                    row["reference"] == 1845
                    for row in fight.native_effect_areas.values()
                ),
                "Original initial luminous producer did not create1845",
            )
            current.runtime.turn_started(arm_deadline=False)
            for _ in range(12):
                self.assertEqual(current.fight.phase, "active")
                actor = current.fight.current
                glyphs = [
                    dict(uid=row["uid"], cell=row["cell"])
                    for row in current.fight.native_effect_areas.values()
                    if row["reference"] == 1845
                ]
                receipt["samples"].append(
                    dict(
                        turn=current.fight.turn_id,
                        current=actor.id,
                        glyphs=glyphs,
                        players={
                            i: dict(
                                position=current.fight.actors[i].position,
                                hp=current.fight.actors[i].hp,
                                mp=current.fight.actors[i].mp,
                                states=[
                                    entry.reference
                                    for entry in current.fight.actors[
                                        i
                                    ].state_ledger.entries
                                ],
                            )
                            for i in characters
                        },
                    )
                )
                if actor.id in characters and glyphs:
                    destinations = {tuple(row["cell"]) for row in glyphs}
                    path = current.path_to(actor.id, lambda cell: cell in destinations)
                    if (
                        path
                        and len(path) <= actor.mp
                        and current.player_move_prefix(actor.id, path)
                    ):
                        earned = current.fight.actors[actor.id]
                        self.assertIn(
                            8242,
                            {entry.reference for entry in earned.state_ledger.entries},
                        )
                        receipt["earned"] = dict(
                            actor=actor.id,
                            position=earned.position,
                            states=[
                                entry.reference for entry in earned.state_ledger.entries
                            ],
                        )
                        current.advance()
                        receipt["after_real_own_end"] = dict(
                            actor=actor.id,
                            states=[
                                entry.reference
                                for entry in current.fight.actors[
                                    actor.id
                                ].state_ledger.entries
                            ],
                        )
                        receipt["status"] = "original_paid_luminous_entry_earned_clair"
                        return
                current.advance()
            self.fail(
                "No affordable genuine luminous entry reached in bounded actual chronology"
            )
        finally:
            if "current" in locals():
                receipt["payments"] = current.payments
                receipt["areas"] = [
                    dict(reference=row["reference"], cell=row["cell"])
                    for row in current.fight.native_effect_areas.values()
                ]
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
