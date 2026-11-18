import unittest
from dataclasses import replace

from wakfu_server.combat_death_events import deliver_owned_death
from wakfu_server.combat_encounter_scene_policy import _digest
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_state import Actor, Fight


class ConvoyLastAllyTests(unittest.TestCase):
    def test_only_last_registered_ally_publishes_for_bound_carrier(self):
        for room, carrier_ref, ally_ref in ((1, 3589, 3565), (2, 3711, 3568)):
            with self.subTest(room=room):
                self.assert_last_ally_reaction(room, carrier_ref, ally_ref)

    def assert_last_ally_reaction(self, room, carrier_ref, ally_ref):
        player = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        first = Actor(-7, 1, (1, 0, 0), 1, 6, 3, 5, 1)
        last = Actor(-8, 1, (2, 0, 0), 1, 6, 3, 5, 1)
        carrier = Actor(-9, 1, (3, 0, 0), 1, 6, 3, 5, 1)
        actors = (player, first, last, carrier)
        fight = Fight(
            77,
            actors,
            {actor.position for actor in actors},
            {
                0: {player.position},
                1: {first.position, last.position, carrier.position},
            },
        )
        fight.ready(3)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        scene = dict(
            schema_version=1,
            descriptor={"policy_id": f"wakemu.kelba.native-cargo-stage-{room}.v1"},
            scope=dict(
                route_key="quest-map-947-25104-2199",
                map_id=947,
                room_order=room,
                actor_bindings=[
                    dict(actor_id=first.id, ref=ally_ref),
                    dict(actor_id=last.id, ref=ally_ref),
                    dict(actor_id=carrier.id, ref=carrier_ref),
                ],
            ),
            room_cells=[actor.position for actor in actors],
        )
        fight.native_encounter_scene = dict(scene, sha256=_digest(scene))
        fight.native_owned_state_containers = {
            1: dict(reference=3478, caster_id=carrier.id, target_id=carrier.id)
        }
        listener = dict(
            target_id=carrier.id,
            state_uid=1,
            invocation=dict(reference=152002, caster_id=carrier.id),
        )
        fight.native_owned_group_effects = {
            4: listener,
            5: dict(
                listener, invocation=dict(listener["invocation"], reference=151997)
            ),
        }
        authority = object()
        reactions = []

        def replay(source, *, authority, eligible_uids=None):
            if source.event_ids == (1041,):
                reactions.append((source, eligible_uids))
            return ()

        effect = NativeEventSource(
            uid=123,
            generic_effect=350204,
            value=1,
            caster_id=player.id,
            target_id=first.id,
            cell=first.position,
            event_ids=(1013,),
            channel=6,
            manager_actor_id=first.id,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            effect_action_id=4,
        )

        def death(actor_id):
            actor = fight.actors[actor_id]
            source = replace(
                effect,
                uid=123 - actor_id,
                target_id=actor_id,
                cell=actor.position,
                manager_actor_id=actor_id,
            )
            deliver_owned_death(
                fight, actor_id, source=source, replay=replay, authority=authority
            )

        fight.apply_effect_damage(player.id, first.id, 1, native_death_delivery=death)
        self.assertEqual(reactions, [])
        self.assertEqual(carrier.hp, 1)
        fight.apply_effect_damage(player.id, last.id, 1, native_death_delivery=death)
        self.assertEqual(len(reactions), 1)
        source, uids = reactions[0]
        self.assertEqual((source.channel, source.manager_actor_id), (61, carrier.id))
        self.assertEqual((source.caster_id, source.target_id), (player.id, last.id))
        self.assertEqual(uids, frozenset({4}))
        death(last.id)
        self.assertEqual(len(reactions), 1)


if __name__ == "__main__":
    unittest.main()
