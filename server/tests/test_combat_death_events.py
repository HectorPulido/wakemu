"""Actual damage death precedes terminal reconciliation and local Qf delivery."""
import unittest
import json
from pathlib import Path
from wakfu_server.paths import DATA_ROOT
import test_combat_damage_handler as damage_fixture
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_death_events import deliver_owned_death
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server import native_catalog


class OwnedDeathEventsTests(unittest.TestCase):
    def test_real_cire_5357_333863_damage_produces_qualified_death_receipt(self):
        from copy import deepcopy
        from wakfu_server import native_catalog
        from wakfu_server.maps.owned_story_defeat_qualification import qualified
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        target, cire = fight.actors[7], fight.actors[-7]
        fight.order = [cire.id, target.id]
        fight.turn_index = 0
        cire.turn_count = 1
        fight._event("turn_started", actor_id=cire.id, actor_turn=1)
        target.hp = 1
        target.effect_stats[92] = 0
        target.effect_stats[97] = 0
        target.effect_stats.update({28: 0, 29: 0, 30: 0, 31: 0})
        cire.effect_stats.update({21: 0, 22: 0, 23: 0, 24: 0})

        from wakfu_server.paths import DATA_ROOT

        effect = native_catalog.record(
            DATA_ROOT / "native-npc-spell-effect-trees.json", "effects", "333863"
        )
        self.assertEqual(
            (effect["effect_class"], effect["parameters"]), (917, [100.0, 0.0])
        )
        invocation = EffectInvocation(7530, 230, cire.id, target.id, target.position)
        authority = object()
        source = NativeEventSource(
            uid=123,
            generic_effect=333863,
            value=100,
            caster_id=cire.id,
            target_id=target.id,
            cell=target.position,
            event_ids=(1013,),
            channel=6,
            manager_actor_id=target.id,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            effect_action_id=917,
        )

        class Events:
            def phase(self, *_args, **_kwargs):
                return None

            def death(self, actor_id, **_kwargs):
                return deliver_owned_death(
                    fight,
                    actor_id,
                    source=source,
                    replay=lambda *_args, **_kwargs: (),
                    authority=authority,
                )

        fixture.handler.event_lifecycle = Events()
        self.assertTrue(fixture.handler(effect, {}, invocation))
        self.assertEqual(target.hp, 0)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, cire.team)

        story_path = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/owned_story_profiles/ereboria-cire-1366.configuration.json"
        )
        story = json.loads(story_path.read_text())["topology"]["owned_story_controller"]
        originals = [{"id": cire.id, "ref": 5357}]
        self.assertTrue(qualified(story, fight, target.id, originals, 1))

        wrong_receipt = deepcopy(fight)
        next(iter(wrong_receipt.native_death_event_deliveries.values()))[
            "generic_effect"
        ] = 999999
        self.assertFalse(qualified(story, wrong_receipt, target.id, originals, 1))
        ordinary_loss = deepcopy(fight)
        ordinary_loss.events = [
            event for event in ordinary_loss.events if event.get("kind") != "damage"
        ]
        self.assertFalse(qualified(story, ordinary_loss, target.id, originals, 1))

    def test_lethal_transition_preserves_source_before_finish_and_checkpoint_once(self):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        deliveries = []
        authority = object()
        source = NativeEventSource(
            123,
            fixture.invocation.reference,
            100,
            7,
            -7,
            fixture.invocation.cell,
            (1013,),
            6,
            -7,
            None,
            False,
            False,
            False,
            True,
        )

        def replay(source, *, authority):
            from wakfu_server.combat_native_events import (
                subscription_actor_ids,
                subscription_selection,
            )

            source.validate()
            self.assertEqual(fight.phase, "active")
            if source.event_ids == (1010,):
                if source.channel == 60:
                    # Actual retained Cra listener 351404 uses a reversed
                    # 1010 mask and target-code 5. Its target must be rebound
                    # to the lethal source target, not its original self.
                    metadata = json.loads(
                        native_catalog.read_text(
                            DATA_ROOT / "native-retained-effect-metadata.json"
                        )
                    )["effects"]["351404"]
                    masks = (None, None, None, None, None, (1010,), None)
                    self.assertEqual(
                        subscription_selection(
                            masks=masks,
                            event_ids=source.event_ids,
                            channel=source.channel,
                            global_subscription=metadata["event_global_subscription"],
                            reversed_subscription=metadata[
                                "event_reverse_subscription"
                            ],
                            flags=(17,),
                            source_present=True,
                        ),
                        "activate",
                    )
                    caster_id, target_id = subscription_actor_ids(
                        target_code=metadata["event_target_code"],
                        caster_code=metadata["event_caster_code"],
                        original_caster=7,
                        original_target=7,
                        manager_actor=source.manager_actor_id,
                        source_caster=source.caster_id,
                        source_target=source.target_id,
                        source_present=True,
                    )
                    self.assertEqual((caster_id, target_id), (7, -7))
                    self.assertNotEqual(
                        fight.actors[caster_id].team, fight.actors[target_id].team
                    )
                deliveries.append(source)
                return ()
            if source.event_ids == (1012,):
                self.assertEqual(source.channel, 61)
                self.assertEqual(
                    (source.uid, source.caster_id, source.target_id), (123, 7, -7)
                )
                deliveries.append(source)
                return ()
            self.assertEqual(
                (source.manager_actor_id, source.event_ids, source.channel),
                (-7, (1013,), 6),
            )
            self.assertEqual(
                (source.uid, source.caster_id, source.target_id), (123, 7, -7)
            )
            # Original Qa.aZL returns beD: retained mask5, not field-order3.
            self.assertEqual(
                subscription_selection(
                    masks=(None, None, None, None, None, (1013,), None),
                    event_ids=source.event_ids,
                    channel=source.channel,
                    global_subscription=False,
                    reversed_subscription=False,
                    flags=(9,),
                    source_present=True,
                ),
                "activate",
            )
            deliveries.append(source)
            return ()

        def death(actor_id):
            return deliver_owned_death(
                fight, actor_id, source=source, replay=replay, authority=authority
            )

        fight.apply_effect_damage(7, -7, 100, native_death_delivery=death)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(
            [(row.manager_actor_id, row.channel) for row in deliveries[:2]],
            [(7, 60), (-7, 6)],
        )
        self.assertEqual(deliveries[-1].event_ids, (1013,))
        self.assertEqual(sum(row.event_ids == (1013,) for row in deliveries), 1)
        from wakfu_server.combat_global_pv_collections import global_pv_iterator

        global_rows = [
            row for row in deliveries if row.event_ids == (1010,) and row.channel == 61
        ]
        self.assertEqual(
            [row.manager_actor_id for row in global_rows],
            list(global_pv_iterator(fight, caster_id=7)),
        )
        self.assertLess(
            max(deliveries.index(row) for row in global_rows),
            deliveries.index(
                next(row for row in deliveries if row.event_ids == (1013,))
            ),
        )
        global_deaths = [
            row for row in deliveries if row.event_ids == (1012,) and row.channel == 61
        ]
        self.assertEqual(
            [row.manager_actor_id for row in global_deaths],
            list(global_pv_iterator(fight, caster_id=7)),
        )
        self.assertLess(
            max(deliveries.index(row) for row in global_rows),
            min(deliveries.index(row) for row in global_deaths),
        )
        self.assertLess(
            max(deliveries.index(row) for row in global_deaths),
            deliveries.index(
                next(row for row in deliveries if row.event_ids == (1013,))
            ),
        )
        self.assertTrue(
            all(row.channel == 61 for row in deliveries if row.event_ids == (1012,))
        )
        self.assertEqual(
            next(iter(fight.native_death_event_deliveries.values()))[
                "global_death_event_id"
            ],
            1012,
        )
        fight.native_death_event_deliveries = json.loads(
            json.dumps(fight.native_death_event_deliveries)
        )
        previous = len(deliveries)
        death(-7)
        self.assertEqual(len(deliveries), previous)

    def test_nonlethal_damage_never_publishes_death_events(self):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        callbacks = []
        fight.apply_effect_damage(
            7, -7, 1, native_death_delivery=lambda actor_id: callbacks.append(actor_id)
        )
        self.assertEqual(fight.actors[-7].hp, 99)
        self.assertEqual(callbacks, [])
        self.assertFalse(any(event.get("kind") == "death" for event in fight.events))
        self.assertFalse(getattr(fight, "native_death_event_deliveries", {}))

    def test_hp_zero_without_registered_death_cannot_emit_capture_event(self):
        fixture = damage_fixture.DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.actors[-7].hp = 0
        with self.assertRaisesRegex(ValueError, "corpse registration"):
            deliver_owned_death(
                fight, -7, source=None, replay=lambda *_: (), authority=None
            )
