"""One bounded native faM consumer; Rift pairing/loot has separate authority.

Original315/330/304/843, actual actor snapshots, QI and state retention run.
Flat terrain, initial roles and a preexisting native carry are declared component
premises. This is not a full class Ready or complete paid Rift encounter.
"""
from copy import copy, deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_ARTIFACT_DATASET"),
    "Explicit bounded Rift artifact source required",
)
class NativeRiftArtifactConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.sublimation_bounded_census import BoundedDataset

        raw = Path(os.environ["WAKFU_RIFT_ARTIFACT_DATASET"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != os.environ.get(
            "WAKFU_RIFT_ARTIFACT_SHA256"
        ):
            raise ValueError("Native artifact source must be hash-pinned")
        cls.native = json.loads(raw)
        cls.dataset = BoundedDataset(os.environ["WAKFU_SUBLIMATION_SEMANTIC_MANIFEST"])
        cls.dataset.install_catalog_backend()
        from wakfu_server import native_catalog

        inventory = cls.dataset.read(
            cls.dataset.manifest["semantic"]["published_document_inventory"]
        )
        native_catalog._exists = lambda revision, name: (
            revision == cls.dataset.manifest["revision"] and name in inventory
        )
        recipe = Path(
            os.environ.get(
                "WAKFU_RIFT_ARTIFACT_RECIPE",
                ".runtime/parallel-readiness-20261023/rift-phase2/native_artifact_recipe.py",
            )
        )
        expected = "66d1eb0e999c86c339b8689416b0ced14303e97e981dd6637507afc79c5831c3"
        if hashlib.sha256(recipe.read_bytes()).hexdigest() != expected:
            raise ValueError("Native artifact component recipe changed")
        spec = importlib.util.spec_from_file_location(
            "bounded_native_artifact_recipe", recipe
        )
        cls.recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.recipe)

    def test_original_fam_contact_assignment_false_criterion_and_private_failure(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_carrying import carry_registered, release_registered
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.recipe.build_fixture(
            effects=self.native["effects"],
            states=self.native["states"],
            registry=self.native["registry"],
            player_team=1,
            npc_team=0,
        )
        fight, player, enemy = fixture.fight, fixture.player, fixture.enemy
        runtime = fixture.dispatcher.native_area_events
        callbacks = []

        def collected(*, area_row, actor_id):
            self.assertNotIn(area_row["uid"], fight.native_effect_areas)
            callbacks.append((area_row["uid"], actor_id, area_row["reference"]))

        runtime.artifact_collected = collected

        def states(actor):
            return [
                (entry.reference, entry.level) for entry in actor.state_ledger.entries
            ]

        # Assignment is a genuine native activation with no contact callback.
        assigned = self.recipe.spawn_artifact(fixture, cell=(-1, 0, 0))
        assignment_position = enemy.position
        before_eligibility, eligibility_rng = snapshot(fight), fixture.rng.getstate()
        self.assertTrue(runtime.artifact_assignment_eligible(assigned["uid"], enemy.id))
        self.assertFalse(runtime.artifact_assignment_eligible(assigned["uid"], 999999))
        self.assertEqual(snapshot(fight), before_eligibility)
        self.assertEqual(fixture.rng.getstate(), eligibility_rng)
        assigned_result = runtime.assign_artifact(assigned["uid"], enemy.id)
        self.assertTrue(
            assigned_result,
            dict(
                actual_area={
                    key: assigned.get(key)
                    for key in (
                        "uid",
                        "reference",
                        "cell",
                        "owner_id",
                        "native_area_contract",
                    )
                },
                still_registered=assigned["uid"] in fight.native_effect_areas,
                player_states=states(player),
                enemy_states=states(enemy),
                receipt=getattr(fight, "native_artifact_activation_receipts", {}).get(
                    str(assigned["uid"])
                ),
                packet_opcodes=[opcode for opcode, _ in fixture.packets],
            ),
        )
        self.assertNotIn(assigned["uid"], fight.native_effect_areas)
        self.assertIn((6786, 6), states(enemy))
        self.assertEqual(enemy.position, assignment_position)
        self.assertEqual(callbacks, [])
        receipt = fight.native_artifact_activation_receipts[str(assigned["uid"])]
        self.assertEqual(
            (receipt["origin"], receipt["actor_id"], receipt["recipient_team"]),
            ("assignment", enemy.id, 0),
        )
        self.assertTrue(receipt["observed_state_changes"])
        before_retry = snapshot(fight)
        packet_count = len(fixture.packets)
        self.assertTrue(runtime.assign_artifact(assigned["uid"], enemy.id))
        self.assertEqual(snapshot(fight), before_retry)
        self.assertEqual(len(fixture.packets), packet_count)
        with self.assertRaises(ValueError):
            runtime.assign_artifact(assigned["uid"], player.id)

        # Actual paid movement enters a native artifact and consumes its Qq.
        contact = self.recipe.spawn_artifact(fixture, cell=(1, 0, 0))
        before_mp = player.mp
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        contact_trace = []
        with combat_diagnostic_scope(
            lambda **item: contact_trace.append(item), limit=128
        ):
            fight.move(
                3,
                player.id,
                [(1, 0, 0)],
                step_callback=lambda current, actor, origin, destination: runtime.movement(
                    actor.id, from_cell=origin, to_cell=destination
                ),
            )
        self.assertEqual(player.mp, before_mp - 1)
        self.assertEqual(
            callbacks,
            [(contact["uid"], player.id, 1561)],
            dict(
                player_position=player.position,
                player_states=states(player),
                area=fight.native_effect_areas.get(contact["uid"]),
                receipt=getattr(fight, "native_artifact_activation_receipts", {}).get(
                    str(contact["uid"])
                ),
                packets=[opcode for opcode, _ in fixture.packets],
                original_outcomes=contact_trace,
            ),
        )
        self.assertIn((6786, 6), states(player))
        actual = fight.native_artifact_activation_receipts[str(contact["uid"])]
        self.assertEqual(actual["origin"], "contact")
        self.assertEqual(actual["area_uid"], contact["uid"])
        self.assertTrue(actual["complete"])
        self.assertTrue(
            any(
                row["reference"] == 6786 and row["actor_id"] == player.id
                for row in actual["observed_state_changes"]
            )
        )
        with self.assertRaises(ValueError):
            runtime.assign_artifact(contact["uid"], player.id)
        self.assertEqual(len(callbacks), 1)

        # An optional contact admission denies before any native consumption.
        guarded = self.recipe.spawn_artifact(fixture, cell=(2, 0, 0))
        runtime.artifact_contact_eligible = lambda **_: False
        before_guard = snapshot(fight)
        runtime._deliver_event(
            guarded,
            runtime._definition(guarded),
            player,
            2243,
            artifact_origin="contact",
        )
        self.assertEqual(snapshot(fight), before_guard)
        self.assertNotIn(str(guarded["uid"]), fight.native_artifact_activation_receipts)
        runtime.artifact_contact_eligible = None

        # Actual carry/QI relation makes the original !IsCarried criterion false.
        blocked = self.recipe.spawn_artifact(fixture, cell=(-2, 0, 0))
        self.assertTrue(
            carry_registered(
                fight, enemy, player, source_uid=fight.allocate_effect_uid()
            )
        )
        before_states = (states(player), states(enemy))
        blocked_before = snapshot(fight)
        self.assertFalse(
            runtime.artifact_assignment_eligible(blocked["uid"], player.id)
        )
        self.assertEqual(snapshot(fight), blocked_before)
        blocked_trace = []
        with combat_diagnostic_scope(
            lambda **item: blocked_trace.append(item), limit=128
        ):
            blocked_result = runtime.assign_artifact(blocked["uid"], player.id)
        self.assertFalse(
            blocked_result,
            dict(
                player_states=states(player),
                enemy_states=states(enemy),
                player_fields={
                    key: value for key, value in vars(player).items() if "carr" in key
                },
                enemy_fields={
                    key: value for key, value in vars(enemy).items() if "carr" in key
                },
                receipt=getattr(fight, "native_artifact_activation_receipts", {}).get(
                    str(blocked["uid"])
                ),
                original_outcomes=blocked_trace,
            ),
        )
        self.assertNotIn(blocked["uid"], fight.native_effect_areas)  # Original843.
        self.assertNotIn(str(blocked["uid"]), fight.native_artifact_activation_receipts)
        self.assertEqual((states(player), states(enemy)), before_states)
        self.assertEqual(len(callbacks), 1)
        self.assertTrue(release_registered(fight, enemy, (1, 0, 0), direction=3))

        # Original orb1574 is GLYPH/bcT, not a faM artifact assignment.
        previous = set(fight.native_effect_areas)
        self.assertTrue(
            fixture.dispatcher.execute(
                EffectInvocation(
                    315925,
                    player.effective_level,
                    player.id,
                    None,
                    (0, 1, 0),
                    native_context_hex=transfer_value_context(
                        constructed_execution_context().payload(), 1574
                    ).hex(),
                    native_retained_container={"present": False},
                )
            )
        )
        (orb_uid,) = set(fight.native_effect_areas) - previous
        self.assertNotEqual(
            fight.native_effect_areas[orb_uid]["native_area_contract"], "faM"
        )
        with self.assertRaises(ValueError):
            runtime.assign_artifact(orb_uid, player.id)
        self.assertEqual(len(callbacks), 1)

        # A callback failure is private: its partial receipt and packets cannot
        # mutate the authoritative source or consume external transaction RNG.
        source_before = snapshot(fight)
        rng_before = fixture.rng.getstate()

        @rollback_external_rng
        def rejected(*, rng):
            preview = deepcopy(fight)
            dispatcher, packets = fixture.dispatcher_for(preview)
            private = copy(fixture)
            private.fight, private.player, private.enemy = (
                preview,
                preview.actors[player.id],
                preview.actors[enemy.id],
            )
            private.dispatcher, private.packets = dispatcher, packets
            row = self.recipe.spawn_artifact(private, cell=(1, 1, 0))

            def fail(**kwargs):
                self.assertNotIn(row["uid"], preview.native_effect_areas)
                rng.random()
                packets.append((12613, b"unpublished callback"))
                raise ValueError("after actual native artifact consumption")

            dispatcher.native_area_events.artifact_collected = fail
            preview.move(
                3,
                player.id,
                [(1, 1, 0)],
                step_callback=lambda current, actor, origin, destination: dispatcher.native_area_events.movement(
                    actor.id, from_cell=origin, to_cell=destination
                ),
            )

        with self.assertRaisesRegex(
            ValueError, "after actual native artifact consumption"
        ):
            rejected(rng=fixture.rng)
        self.assertEqual(snapshot(fight), source_before)
        self.assertEqual(fixture.rng.getstate(), rng_before)
