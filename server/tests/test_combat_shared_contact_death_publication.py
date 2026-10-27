"""Original faM lethal contact reaches the shared death publication boundary.

The source fixture has genuine native snapshots, equipment initialization and
opening1028. Its class Ready and synthetic flat terrain remain explicit
component premises; this is not a complete client/HeroDB route.
"""
from copy import deepcopy
import os
import struct
import unittest
from unittest.mock import patch


class SharedContactDeathPublicationTests(unittest.TestCase):
    def test_original_paid_lethal_contact_publishes_before_checkpoint_once(self):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server import native_catalog, native_catalog_document
        from wakfu_server.paths import DATA_ROOT

        manifest = os.environ["WAKFU_RIFT_ARTIFACT_MANIFEST"]
        source_metadata = BoundedDataset(manifest)
        source_metadata.install_catalog_backend()

        # Keep raw getters and the one required derived-cost view on the
        # original hash-verified component backend. Reuse the exact production
        # common-spell transformation; do not relabel a current SQL generation.
        def bounded_document(path):
            name = native_catalog_document._document_key(path)
            if name == "spell_audit.costs_catalog":
                from wakfu_server.combat_common_spell_catalog import merge_cost_records

                return merge_cost_records(
                    native_catalog.load(DATA_ROOT / "spell-costs.json")["spells"]
                )
            if not name.endswith(".json"):
                raise ValueError("Unlisted derived component metadata: " + name)
            return native_catalog.load(DATA_ROOT / name)

        metadata = patch.object(
            native_catalog_document,
            "load_published_document",
            side_effect=bounded_document,
        )
        metadata.start()
        self.addCleanup(metadata.stop)
        # Materialize/validate the bounded cost/casting/common closure before
        # constructing gameplay. No publication/Ready or actor is fabricated.
        costs = bounded_document("spell_audit.costs_catalog")
        casting = bounded_document("native-spell-casting.json")["spells"]
        self.assertIn("5623", costs)
        self.assertIn("5623", casting)

        from test_rift_artifact_generation_component import (
            RiftArtifactGenerationComponentTests,
        )
        from tools.sublimation_semantic_fixture import build_fixture, _factory
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_death import newly_registered_death_messages
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_owned_equipment_factory import (
            OwnedEquipmentRuntimeFactory,
        )
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_shared import Registry, Session, Transition
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.rift_native_gameplay import (
            install_wave_state,
            register_artifact_group,
        )

        native = RiftArtifactGenerationComponentTests.native_policy()
        catalog = dict(
            type="ULTIMATE_INFINITE_WAVE", map_id=1134, wave_id=1, species_refs=[5525]
        )
        policy = dict(
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
        roles = roles_for_catalog(catalog, policy, monster_references=(5525,))
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
            policy=policy,
            seed="shared-original-lethal-contact",
            world_group_id=source.id,
        )
        source.rift_monsters = deepcopy(fixture.monster_sources)
        dispatcher, _ = fixture.dispatcher_for(source)
        self.assertTrue(install_wave_state(dispatcher, actor_ids=(-200,), wave=1))
        # Same pre-existing source fixture premise as the qualified lethal
        # artifact component: actual damage leaves1HP; the original faM kills.
        source.apply_effect_damage(-200, 7, source.actors[7].hp - 1)
        self.assertEqual(source.actors[7].hp, 1)
        template = native["artifacts"]["producer"]["template_effect_reference"]
        with patch(
            "wakfu_server.combat_server_spell.compiled_runtime_catalog",
            return_value=fixture.compiled,
        ):
            rows = []
            for reference, cell in zip((1588, 1561, 1562, 1563), arms):
                previous = set(source.native_effect_areas)
                self.assertTrue(
                    dispatcher.execute(
                        EffectInvocation(
                            template,
                            source.actors[7].effective_level,
                            7,
                            None,
                            cell,
                            native_context_hex=transfer_value_context(
                                constructed_execution_context().payload(), reference
                            ).hex(),
                            native_retained_container={"present": False},
                        )
                    )
                )
                created = set(source.native_effect_areas) - previous
                self.assertEqual(len(created), 1)
                rows.append(source.native_effect_areas[created.pop()])
            register_artifact_group(
                source, wave=1, area_uids=[row["uid"] for row in rows]
            )
        baseline = snapshot(source)
        rng = fixture.factory.transaction_rng

        def serialize(actor, fight):
            if actor.controlled:
                return actual_actor_stats(
                    fixture.character,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    direction=actor.direction,
                    fight=fight,
                )
            return actual_monster_actor_stats(
                fight.rift_monsters[actor.id],
                actor,
                fight.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                direction=actor.direction,
                fight=fight,
            )

        for already_published, reject_checkpoint in (
            (False, True),
            (False, False),
            (True, False),
        ):
            with self.subTest(
                already_published=already_published, reject_checkpoint=reject_checkpoint
            ):
                fight = deepcopy(source)
                runtime = RuntimeMessages(fight, runtime_stats_serializer=serialize)
                session = Session(3, 7, "shared-lethal-contact", 1134, 9)
                registry = Registry(lambda selected: selected == session)
                observed = []

                def unexpected_birth(*args, **kwargs):
                    raise AssertionError("Terminal contact cannot create another wave")

                def checkpoint(shared, candidate, current, packets):
                    observed.append(
                        (
                            candidate.actors[7].native_death_status["last_writer"],
                            7 in current._reported_deaths,
                        )
                    )
                    result = finish_accepted_action(
                        candidate, current, packets, initialize_actor=unexpected_birth
                    )
                    if reject_checkpoint:
                        raise ValueError("reject genuine prepared contact checkpoint")
                    return result

                shared = registry.register(
                    fight,
                    session,
                    runtime=runtime,
                    join_context=dict(rift_accepted_action=checkpoint),
                )

                def contact(candidate, current):
                    def area_provider(state, *, actor_id, action_id, path, origin):
                        preview = deepcopy(state)
                        factory = _factory(
                            fixture.character,
                            preview.rift_monsters,
                            fixture.compiled,
                            fixture.registry,
                            rng,
                        )
                        factory.action_id = action_id
                        actual, callbacks = OwnedEquipmentRuntimeFactory(
                            factory, fixture.compiled
                        )(preview, fixture.plan)
                        with preview.effect_resolution():
                            actual.native_area_events.movement(
                                actor_id, from_cell=origin, to_cell=path[-1]
                            )
                        return preview, callbacks

                    before = candidate.sequence
                    packets, accepted = apply_client(
                        current,
                        3,
                        struct.pack(">qiih", 7, *arms[0]),
                        lambda actor: serialize(actor, current.fight),
                        runtime_stats_serializer=serialize,
                        area_provider=area_provider,
                    )
                    self.assertEqual(accepted["cost"], 1)
                    self.assertEqual(candidate.actors[7].hp, 0)
                    packets = list(current.prepare_delivery(packets))
                    if already_published:
                        packets.extend(
                            newly_registered_death_messages(
                                current, after_sequence=before
                            )
                        )
                    return Transition(candidate, current, tuple(packets))

                @rollback_external_rng
                def execute(*, rng):
                    return registry.execute(
                        source.id,
                        session,
                        7,
                        contact,
                        expected_sequence=shared.sequence,
                    )

                rng_before = rng.getstate()
                if reject_checkpoint:
                    with self.assertRaisesRegex(
                        ValueError, "genuine prepared contact checkpoint"
                    ):
                        execute(rng=rng)
                    self.assertIs(shared.fight, fight)
                    self.assertEqual(snapshot(fight), baseline)
                    self.assertEqual(registry.drain(source.id, session), [])
                    self.assertEqual(rng.getstate(), rng_before)
                else:
                    execute(rng=rng)
                    batches = registry.drain(source.id, session)
                    self.assertEqual(len(batches), 1)
                    states = [
                        struct.unpack_from(">qB", body, 12)
                        for opcode, body in batches[0].packets
                        if opcode == 12727
                    ]
                    self.assertEqual(states, [(7, 0)])
                    self.assertEqual(shared.fight.actors[7].hp, 0)
                    self.assertEqual(shared.fight.winner, roles.npc_team)
                    self.assertIsNone(shared.fight.rift_wave_state.get("pending_wave"))
                    stable = snapshot(shared.fight)
                    self.assertEqual(
                        newly_registered_death_messages(
                            shared.runtime, after_sequence=source.sequence
                        ),
                        [],
                    )
                    self.assertEqual(snapshot(shared.fight), stable)
                self.assertEqual(observed, [("owned.aTS.F.type0", True)])
        self.assertEqual(snapshot(source), baseline)
