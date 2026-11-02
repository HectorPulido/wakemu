"""Native retired-Qq queries, producer repair and subsequent paid owned action.

One original-map native-carrier arena is an explicit component fixture. Normal contact
produces the retired UID; a separate scenario retires one genuine owned parent
through Qs before contact. The latter is a declared recovery premise, not proof
of an independently occurring live stale ledger. No victory, successor wave,
persistent reconnect, account creation or complete Rift journey is claimed.
"""
from copy import deepcopy
import json
from pathlib import Path
import os
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_ASSIGNMENT_COMPONENT") == "1",
    "Installed native publication required",
)
class RiftArtifactRetiredContactTests(unittest.TestCase):
    def test_native_retirement_reconciles_contact_and_preserves_paid_continuation(self):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests
        from test_rift_artifact_generation_component import (
            RiftArtifactGenerationComponentTests,
        )
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.combat_shared import Registry, Session, Transition
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server import combat_artifact_assignment
        from wakfu_server.rift_native_gameplay import (
            install_wave_state,
            register_artifact_group,
        )
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.spells import encode_deck
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = NativeRiftCarrierComponentTests()
        fixture.compiled = npc_runtime_catalog()
        fixture.registry = characteristic_registry()
        evidence = []
        # Both actual native pickup variants share the generic repair path.
        for selected_reference, retire_other in ((1592, False), (1594, True)):
            with self.subTest(
                reference=selected_reference, parent_retirement=retire_other
            ):
                component = fixture.fixture(2, native_geometry=True)
                fight = component.fight
                characters = component.characters
                character = characters[7]
                decks = {7: encode_deck((6972,)), 8: encode_deck()}
                rng = component.rng
                fight.rift_wave_state["policy"][
                    "native_gameplay"
                ] = RiftArtifactGenerationComponentTests.native_policy()
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
                fight, _ = prepare_server_initialization(
                    character,
                    fight.rift_monsters,
                    fight,
                    3,
                    decks[7],
                    action_id=1,
                    fight_start=False,
                    **common,
                )

                def factory(current, action_id=2):
                    return server_runtime(
                        character,
                        current.rift_monsters,
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0]

                def dispatcher_for(current):
                    return factory(current)(
                        current, {"native_retained_container": {"present": False}}
                    )

                dispatcher, _ = dispatcher_for(fight)
                native = fight.rift_wave_state["policy"]["native_gameplay"]
                template = native["artifacts"]["producer"]["template_effect_reference"]
                references = [selected_reference] + [
                    ref for ref in (1592, 1594, 1613, 1614) if ref != selected_reference
                ]
                cells = ((-8, -8, -1), (-8, -9, -1), (-7, -8, -1), (-7, -9, -1))
                self.assertTrue(set(cells) <= fight.walkable)
                created = []
                with fight.effect_resolution():
                    install_wave_state(dispatcher, actor_ids=(-200, -201), wave=1)
                    for reference, cell in zip(references, cells):
                        prior = set(fight.native_effect_areas)
                        self.assertTrue(
                            dispatcher.execute(
                                EffectInvocation(
                                    template,
                                    fight.actors[7].effective_level,
                                    7,
                                    None,
                                    cell,
                                    native_context_hex=transfer_value_context(
                                        constructed_execution_context().payload(),
                                        reference,
                                    ).hex(),
                                    native_retained_container={"present": False},
                                )
                            )
                        )
                        added = set(fight.native_effect_areas) - prior
                        self.assertEqual(len(added), 1)
                        created.append(added.pop())
                    group = register_artifact_group(fight, wave=1, area_uids=created)
                selected_uid = created[0]
                retired_uid = created[-1] if retire_other else None
                if retired_uid is not None:
                    # Source-backed Qs removal, never dict deletion, fabricated
                    # receipt, HP damage, grant, eligibility or wave completion.
                    before_budget = (fight.actors[7].ap, fight.actors[7].mp)
                    before_states = combat_artifact_assignment.state_observations(fight)
                    with fight.effect_resolution():
                        self.assertTrue(
                            dispatcher.native_area_events.remove_parent(
                                fight.native_effect_areas[retired_uid]
                            )
                        )
                    self.assertNotIn(retired_uid, fight.native_effect_areas)
                    self.assertIn(retired_uid, group["remaining"])
                    self.assertEqual(
                        combat_artifact_assignment.state_observations(fight),
                        before_states,
                    )
                    self.assertEqual(
                        (fight.actors[7].ap, fight.actors[7].mp), before_budget
                    )
                    self.assertNotIn(
                        str(retired_uid),
                        getattr(fight, "native_artifact_activation_receipts", {}),
                    )

                def serialize(actor, current):
                    serializer = (
                        actual_actor_stats
                        if actor.controlled
                        else actual_monster_actor_stats
                    )
                    source = (
                        characters[actor.id]
                        if actor.controlled
                        else current.rift_monsters[actor.id]
                    )
                    return serializer(
                        source,
                        actor,
                        current.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        direction=actor.direction,
                        fight=current,
                    )

                runtime = RuntimeMessages(fight, runtime_stats_serializer=serialize)
                session = Session(3, 7, "retired-artifact-component", 1134, 1)
                registry = Registry(lambda candidate: candidate == session)

                def accepted(shared, current, current_runtime, packets):
                    # These actions never clear a wave; still run the normal
                    # Rift accepted-action gate, without a checkpoint substitute.
                    self.assertIsNone(current.rift_wave_state.get("pending_wave"))
                    return finish_accepted_action(
                        current,
                        current_runtime,
                        packets,
                        initialize_actor=lambda *_: self.fail("Unexpected successor"),
                    )

                shared = registry.register(
                    fight,
                    session,
                    runtime=runtime,
                    join_context={"rift_accepted_action": accepted},
                )
                observed = []
                original_complete = combat_artifact_assignment.complete_activation

                def observe_retired(runtime, row, definition, target, **kwargs):
                    if (
                        kwargs["successful"]
                        and row["uid"] not in runtime.fight.native_effect_areas
                    ):
                        # The original consumer has actually retired this Qq,
                        # while complete_activation has not updated the producer.
                        before = snapshot(runtime.fight)
                        rng_before = rng.getstate()
                        self.assertFalse(
                            runtime.artifact_assignment_eligible(row["uid"], target.id)
                        )
                        self.assertFalse(runtime.assign_artifact(row["uid"], target.id))
                        self.assertEqual(snapshot(runtime.fight), before)
                        self.assertEqual(rng.getstate(), rng_before)
                        observed.append(
                            (row["uid"], row["reference"], kwargs["origin"])
                        )
                    return original_complete(runtime, row, definition, target, **kwargs)

                def move(current, current_runtime):
                    def area_provider(preview, **kwargs):
                        return prepare_area_movement(
                            character,
                            preview.rift_monsters,
                            preview,
                            decks[7],
                            **common,
                            **kwargs,
                        )

                    packets, result = apply_client(
                        current_runtime,
                        3,
                        struct.pack(">q", 7) + struct.pack(">iih", *cells[0]),
                        lambda actor: serialize(actor, current_runtime.fight),
                        runtime_stats_serializer=serialize,
                        area_provider=area_provider,
                    )
                    self.assertEqual(result.get("event", result)["cost"], 1)
                    return Transition(current_runtime.fight, current_runtime, packets)

                ap_before, mp_before = fight.actors[7].ap, fight.actors[7].mp
                with patch.object(
                    combat_artifact_assignment, "complete_activation", observe_retired
                ):
                    registry.execute(fight.id, session, 7, move)
                current = shared.fight
                self.assertGreater(mp_before, 0)
                self.assertEqual(current.actors[7].mp, 0)
                self.assertEqual(current.actors[7].ap, ap_before)
                self.assertIn((selected_uid, selected_reference, "contact"), observed)
                group = current.rift_wave_state["native_artifact_groups"]["1"]
                self.assertEqual(group["choices_made"], 1)
                self.assertEqual(len(group["assignments"]), 1)
                self.assertFalse(group.get("pending_pairs"))
                if retired_uid is not None:
                    self.assertEqual(
                        group["retired"][str(retired_uid)], "native_area_absent"
                    )
                    self.assertNotIn(retired_uid, group["remaining"])
                    self.assertNotIn(
                        str(retired_uid), current.native_artifact_activation_receipts
                    )
                before_followup = deepcopy(current.native_artifact_activation_receipts)
                choices_before = deepcopy(group)
                paid = []

                def owned_spell(current, current_runtime):
                    from wakfu_server.combat_effective_control import (
                        effective_input_owner,
                    )

                    facts = dict(
                        current=None if current.current is None else current.current.id,
                        actor=7,
                        same_current=current.current is current.actors[7],
                        owner=effective_input_owner(current, current.actors[7]),
                        phase=current.phase,
                        hp=current.actors[7].hp,
                        runtime_alias=current_runtime.fight is current,
                    )
                    self.assertEqual(facts["current"], 7, facts)
                    self.assertTrue(facts["same_current"], facts)
                    self.assertEqual(facts["owner"], 3, facts)
                    self.assertTrue(facts["runtime_alias"], facts)
                    try:
                        tx = prepare_server_spell(
                            struct.pack(
                                ">qqiih",
                                7,
                                (7 << 32) | 6972,
                                *current.actors[8].position,
                            ),
                            character,
                            current.rift_monsters,
                            current,
                            3,
                            decks[7],
                            action_id=current_runtime.action_id + 1,
                            # Original6972 permits allied targets and requires no LOS.
                            line_of_sight=lambda origin, destination, preview: authoritative_visible(
                                1134, origin, destination, preview
                            ),
                            critical=False,
                            **common,
                        )
                    except ValueError as error:
                        raise AssertionError(
                            dict(
                                facts,
                                error=str(error),
                                native_casting_diagnostic=getattr(
                                    error, "native_casting_diagnostic", None
                                ),
                            )
                        ) from error
                    paid.append(
                        dict(
                            costs=tx.plan["costs"],
                            before=current.actors[7].ap,
                            after=tx.fight.actors[7].ap,
                        )
                    )
                    packets = commit_spell_transaction(
                        current_runtime, tx, stats_serializer=serialize
                    )
                    return Transition(current_runtime.fight, current_runtime, packets)

                registry.execute(fight.id, session, 7, owned_spell)
                self.assertEqual(paid[0]["costs"]["ap"], 2)
                self.assertEqual(paid[0]["after"], paid[0]["before"] - 2)
                self.assertEqual(
                    shared.fight.native_artifact_activation_receipts, before_followup
                )
                self.assertEqual(
                    shared.fight.rift_wave_state["native_artifact_groups"]["1"],
                    choices_before,
                )
                self.assertEqual(shared.fight.rift_wave_state["wave"], 1)
                self.assertEqual(shared.fight.phase, "active")
                self.assertIsNone(shared.fight.winner)
                self.assertTrue(
                    any(
                        s.reference == 6325
                        for s in shared.fight.actors[8].state_ledger.entries
                    )
                )
                evidence.append(
                    dict(
                        reference=selected_reference,
                        public_parent_retirement_premise=retired_uid,
                        original_area_ids=created,
                        retired_queries=observed,
                        contact_budget=dict(
                            mp_before=mp_before,
                            mp_after=0,
                            ap_before=ap_before,
                            ap_after=ap_before,
                        ),
                        repaired_group=deepcopy(group),
                        activation_receipts=list(before_followup),
                        paid_followup=dict(
                            reference=6972, caster=7, target=8, **paid[0]
                        ),
                        registry_sequence=shared.sequence,
                        wave=shared.fight.rift_wave_state["wave"],
                        fight_phase=shared.fight.phase,
                        winner=shared.fight.winner,
                    )
                )
        self.assertEqual(
            len(evidence), 2, "Both variants must pass before emitting GREEN"
        )
        output = os.environ.get("WAKFU_RIFT_RETIREMENT_RECEIPT")
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    dict(
                        status="NATIVE_RETIRED_QQ_PAID_CONTINUATION_COMPONENT_GREEN",
                        variants=evidence,
                        scope=dict(
                            real_native_contact=True,
                            public_registry=True,
                            recovery_premise="one public owned-parent retirement",
                            naturally_independent_stale_ledger=False,
                            successor_wave=False,
                            durable_reconnect=False,
                            native_ai=False,
                            complete_rift=False,
                        ),
                    ),
                    indent=2,
                )
                + "\n"
            )
