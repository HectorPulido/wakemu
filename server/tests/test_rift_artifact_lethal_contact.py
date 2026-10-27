"""One bounded native lethal-pickup component, not a complete Rift outcome."""
from copy import deepcopy
import gc
import os
import unittest
from unittest.mock import patch


class RiftArtifactLethalContactTests(unittest.TestCase):
    def test_original_lethal_contacts_receipts_retry_and_tamper_rollback(self):
        from test_rift_artifact_generation_component import (
            RiftArtifactGenerationComponentTests,
        )
        from tools.sublimation_semantic_fixture import build_fixture
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.rift_native_gameplay import (
            apply_artifact_collection,
            artifact_contact_eligible,
            install_wave_state,
            register_artifact_group,
        )

        manifest = os.environ["WAKFU_RIFT_ARTIFACT_MANIFEST"]
        native = RiftArtifactGenerationComponentTests.native_policy()
        catalog = dict(
            type="ULTIMATE_INFINITE_WAVE", map_id=1134, wave_id=1, species_refs=[5525]
        )
        wave_policy = dict(
            policy_kind="local_dev_not_official",
            enabled=True,
            max_members=6,
            turn_budget=40,
            starting_wave=1,
            classic_wave_size=2,
            ultimate_wave_size=2,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            rewards="callback_only",
            native_gameplay=native,
        )
        roles = roles_for_catalog(catalog, wave_policy, monster_references=(5525,))
        arms = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0))
        fixture = build_fixture(
            27152,
            manifest,
            constructor_roles=roles,
            terrain_cells=set(arms) | {(0, 0, 0), (3, 0, 0)},
        )
        source = fixture.fight
        source.rift_wave_state = dict(
            instance_id=9,
            wave=1,
            turn_budget=40,
            wave_actor_ids=[-200],
            catalog=catalog,
            policy=wave_policy,
            seed="lethal-artifact-component",
            world_group_id=source.id,
        )
        source.rift_monsters = deepcopy(fixture.monster_sources)
        initial, _ = fixture.dispatcher_for(source)
        self.assertTrue(install_wave_state(initial, actor_ids=(-200,), wave=1))
        del initial
        # Explicit low-HP fixture premise through the actual damage/PA setter;
        # no HP resurrection, stat override or modified original artifact root.
        source.apply_effect_damage(-200, 7, source.actors[7].hp - 1)
        self.assertEqual(source.actors[7].hp, 1)
        self.assertTrue(source._in_play(source.actors[7]))
        canonical = snapshot(source)
        rng = fixture.factory.transaction_rng
        template = native["artifacts"]["producer"]["template_effect_reference"]

        @rollback_external_rng
        def attempt(reference, *, tamper=False, discard=False, rng):
            preview = deepcopy(source)
            dispatcher, packets = fixture.dispatcher_for(preview)
            self.assertIs(dispatcher.rift_artifact_rng, rng)
            with patch(
                "wakfu_server.combat_server_spell.compiled_runtime_catalog",
                return_value=fixture.compiled,
            ):
                rows = []
                for area_reference, cell in zip((reference, 1561, 1562, 1563), arms):
                    before = set(preview.native_effect_areas)
                    self.assertTrue(
                        dispatcher.execute(
                            EffectInvocation(
                                template,
                                preview.actors[7].effective_level,
                                7,
                                None,
                                cell,
                                native_context_hex=transfer_value_context(
                                    constructed_execution_context().payload(),
                                    area_reference,
                                ).hex(),
                                native_retained_container={"present": False},
                            )
                        )
                    )
                    created = set(preview.native_effect_areas) - before
                    self.assertEqual(len(created), 1)
                    rows.append(deepcopy(preview.native_effect_areas[created.pop()]))
                group = register_artifact_group(
                    preview, wave=1, area_uids=[row["uid"] for row in rows]
                )
                row = rows[0]
                self.assertTrue(
                    artifact_contact_eligible(preview, area_row=row, actor_id=7)
                )
                self.assertFalse(
                    artifact_contact_eligible(preview, area_row=row, actor_id=-200)
                )
                if tamper:
                    original_callback = dispatcher.native_area_events.artifact_collected

                    def corrupt_consumed_receipt(**contact):
                        preview.native_artifact_activation_receipts[str(row["uid"])][
                            "actor_id"
                        ] = -200
                        return original_callback(**contact)

                    dispatcher.native_area_events.artifact_collected = (
                        corrupt_consumed_receipt
                    )
                trace = []
                with preview.effect_resolution(), combat_diagnostic_scope(
                    lambda **record: trace.append(record), limit=512
                ):
                    movement = preview.move(
                        3,
                        7,
                        [arms[0]],
                        step_callback=lambda fight, actor, old, new: dispatcher.native_area_events.movement(
                            actor.id, from_cell=old, to_cell=new
                        ),
                    )
                self.assertEqual(movement["cost"], 1)
                self.assertEqual(preview.actors[7].hp, 0)
                self.assertFalse(preview._in_play(preview.actors[7]))
                self.assertFalse(
                    artifact_contact_eligible(preview, area_row=row, actor_id=7)
                )
                self.assertTrue(
                    any(
                        item.get("effect_class") == 304
                        and item.get("target_id") == 7
                        and item.get("status") == "completed"
                        for item in trace
                    )
                )
                self.assertTrue(
                    any(
                        item.get("effect_class") == 1
                        and item.get("target_id") == 7
                        and item.get("status") == "completed"
                        for item in trace
                    )
                )
                receipt = preview.native_artifact_activation_receipts[str(row["uid"])]
                self.assertTrue(receipt["complete"])
                self.assertEqual(receipt["origin"], "contact")
                self.assertEqual(receipt["reference"], reference)
                self.assertNotIn(row["uid"], preview.native_effect_areas)
                self.assertEqual(group["choices_made"], 1)
                self.assertEqual(len(group["assignments"]), 1)
                paired = group["assignments"][0]["opponent"]
                self.assertTrue(
                    preview.native_artifact_activation_receipts[str(paired)]["complete"]
                )
                before_retry, rng_before_retry = snapshot(preview), rng.getstate()
                self.assertFalse(
                    apply_artifact_collection(dispatcher, area_row=row, actor_id=7)
                )
                self.assertEqual(
                    dispatcher.native_area_events.movement(
                        7, from_cell=(0, 0, 0), to_cell=arms[0]
                    ),
                    ((), (), ()),
                )
                self.assertEqual(snapshot(preview), before_retry)
                self.assertEqual(rng.getstate(), rng_before_retry)
                if discard:
                    raise ValueError("discard genuine lethal pickup preview")

        for reference in (1588, 1589, 1590):
            with self.subTest(reference=reference):
                before_rng = rng.getstate()
                with self.assertRaisesRegex(
                    ValueError, "actual consumed native contact receipt"
                ):
                    attempt(reference, tamper=True, rng=rng)
                self.assertEqual(snapshot(source), canonical)
                self.assertEqual(rng.getstate(), before_rng)
                gc.collect()
                with self.assertRaisesRegex(
                    ValueError, "discard genuine lethal pickup preview"
                ):
                    attempt(reference, discard=True, rng=rng)
                self.assertEqual(snapshot(source), canonical)
                self.assertEqual(rng.getstate(), before_rng)
                gc.collect()
                attempt(reference, rng=rng)
                self.assertEqual(snapshot(source), canonical)
                gc.collect()
