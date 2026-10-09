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
