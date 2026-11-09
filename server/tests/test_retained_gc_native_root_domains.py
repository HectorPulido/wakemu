"""Exercise root-domain collision handling through an owned native GC preview."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_gc_authority import (
    certify_ready_runtime,
    native_callbacks_known,
)
from wakfu_server.combat_retained_gc_boundary import prepare_retired_gc
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_retained_collections import bound_collections


class NativePreviewRootDomainTests(unittest.TestCase):
    def test_queue_counter_and_actor_key_collisions_sweep_false_roots_preserve_uid_value(
        self,
    ):
        _, fight, _, dead, original_uid = OwnedCollectionGCTests().fixture()
        live_actor_id = 7
        actor_key_collision_uid = live_actor_id
        queue_counter_collision_uid = 10002

        storage = bound_collections(vars(fight))
        self.assertIsNotNone(storage)

        def add_group(uid):
            payload = group_payload(
                uid=uid,
                base_uid=uid,
                generic_effect=350552,
                caster_id=dead,
                target_id=None,
                cell=fight.actors[dead].position,
                container_type=None,
                container_id=None,
                timing_payload=b"",
            ).hex()
            row = asdict(
                RetainedEffect(
                    uid,
                    None,
                    949,
                    350552,
                    manager_id=dead,
                    container_present=False,
                )
            )
            storage.records.install_owned(uid, row)
            storage.order.append(uid)
            fight.native_owned_group_effects[uid] = dict(
                target_id=None,
                effect_class=949,
                state_uid=None,
                payload=payload,
            )

        add_group(actor_key_collision_uid)
        add_group(queue_counter_collision_uid)
        fight.native_delay_queue["next_sequence"] = queue_counter_collision_uid
        # A compatibility UID value preserves the existing fixture runner; it
        # does not make actor-keyed manager siblings operational roots.
        fight.native_social_contexts = {
            str(live_actor_id): {"source_parent_uid": original_uid}
        }

        provider = OwnedExpirationFactory(
            characters={live_actor_id: {"id": live_actor_id, "account_id": 1}},
            monsters={},
            decks={live_actor_id: b""},
            actor_id=live_actor_id,
            fight_start=True,
            area_callbacks=False,
        )
        serializer = NativeStats(
            characters=provider.characters,
            monsters=provider.monsters,
            fight_id=fight.id,
        )
        runtime = RuntimeMessages(
            fight,
            stats_serializer=serializer,
            runtime_stats_serializer=serializer,
            turn_start_provider=provider.turn_start,
            turn_end_provider=provider.turn_end,
            expiration_runtime_factory=provider,
        )
        adapter = CombatSessionAdapter.__new__(CombatSessionAdapter)
        certify_ready_runtime(adapter, runtime, serializer, provider)
        self.assertTrue(native_callbacks_known(runtime))

        previous = deepcopy(fight)
        prepare_retired_gc(previous, fight, runtime, ())

        self.assertTrue(native_callbacks_known(runtime))
        self.assertIn(original_uid, fight.native_retained_records)
        self.assertNotIn(actor_key_collision_uid, fight.native_retained_records)
        self.assertNotIn(queue_counter_collision_uid, fight.native_retained_records)
        self.assertIn(live_actor_id, fight.actors)
        self.assertTrue(storage.consistent())
