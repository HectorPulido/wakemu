"""Genuine MHS reconnect separates human appearances from native companions."""
import base64
from copy import deepcopy
from unittest.mock import patch

from protocol_codec import Reader
from test_rift_earned_rewards import RiftEarnedRewardTests
from wakfu_server import wire, native_catalog, bootstrap_capture
from wakfu_server.combat_companions import world_spawn
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Session
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_wire import decode_bootstrap
from wakfu_server.monsters import owned_instance


class CompanionOwnedReconnectTests(RiftEarnedRewardTests):
    def test_actual_mhs_reconnect_hydrates_hero_and_native_sidekick_before_bootstrap(
        self,
    ):
        (
            run,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        fight.rift_monsters = {
            identity: owned_instance(
                row["ref"],
                row["level"],
                identity,
                map_id=1134,
                instance_id=run["instance_id"],
                team=fight.actors[identity].team,
                x=fight.actors[identity].position[0],
                y=fight.actors[identity].position[1],
                z=fight.actors[identity].position[2],
            )
            for identity, row in fight.rift_monsters.items()
        }
        # Use the installed, authenticated World bootstrap source and its
        # actual synthetic/legacy layouts, never a manufactured appearance.
        with native_catalog._database().connection() as db:
            frames = bootstrap_capture.load(db)
        metadata = frames[0].get("synthetic_template")
        if metadata is not None:
            wire.register_synthetic_bootstrap(metadata)
        template = None
        for frame in frames:
            if frame["direction"] != "in" or frame["opcode"] != 12608:
                continue
            reader = Reader(base64.b64decode(frame["body_base64"]))
            reader.take(1)
            for _ in range(reader.number("B")):
                kind, identity = reader.number("B"), reader.number("q")
                blob = reader.take(reader.number("H"))
                if kind == 0 and identity == wire.TEMPLATE_CHARACTER:
                    template = blob
                    break
            if template is not None:
                break
        self.assertIsNotNone(template)
        appearances = []

        def appearance(character):
            appearances.append(character["id"])
            return 12608, wire.spawn_player(template, character)

        adapter = CombatSessionAdapter(self.store, player_appearance=appearance)
        session = Session(
            self.account, self.ids[0], self.generation, 1134, run["instance_id"]
        )
        arena = local_arena(
            1134, 0, (-4, -18, 0), (-4, -17, 0), relocate_monsters=False
        )
        from wakfu_server.combat_placement_policy import freeze as freeze_placement

        arena = freeze_placement(
            self.store,
            account_id=self.account,
            generation=self.generation,
            character_id=self.ids[0],
            fight_id=fight.id,
            map_id=1134,
            instance_id=run["instance_id"],
            selected_arena=arena,
            seeds={0: [(-4, -18, 0)], 1: [(-4, -17, 0)]},
        )
        leaders = {
            team: next(
                actor.id
                for actor in fight.actors.values()
                if actor.team == team and actor.id != companion_id
            )
            for team in (0, 1)
        }
        shared = adapter.registry.register(
            fight,
            session,
            join_context=dict(
                arena=arena,
                terrain_effect_id=arena["terrain_effect_id"],
                terrain_instance_id=fight.id,
                leaders=leaders,
                duration_ms=60000,
                actor_payload=adapter.actor_payload,
                hero_appearance=appearance,
                monsters=fight.rift_monsters,
            ),
        )
        reads = []
        original_character = self.store.character

        def character_source(account_id, identity, *args, **kwargs):
            reads.append(identity)
            if identity == companion_id:
                raise AssertionError(
                    "A native sidekick must not enter human Store hydration"
                )
            return original_character(account_id, identity, *args, **kwargs)

        with patch.object(self.store, "character", side_effect=character_source):
            packets = adapter.owned_reconnect_bootstrap(fight, shared, session)
        self.assertNotIn(companion_id, reads)
        self.assertEqual(appearances, [self.ids[1]])
        first_bootstrap = next(
            index for index, packet in enumerate(packets) if packet[0] == 12847
        )
        companion = fight.actors[companion_id]
        source = fight.native_companion_sources[str(companion_id)]
        expected_spawn = (
            12608,
            world_spawn(
                dict(
                    source,
                    x=companion.position[0],
                    y=companion.position[1],
                    z=companion.position[2],
                )
            ),
        )
        self.assertIn(expected_spawn, packets[:first_bootstrap])
        decoded = decode_bootstrap(packets[first_bootstrap][1])
        participant = next(
            row for row in decoded["participants"] if row["actor_id"] == companion_id
        )
        self.assertEqual(participant["myB"], 5)
        self.assertEqual(
            set(row["actor_id"] for row in decoded["participants"]), set(fight.actors)
        )
        self.assertTrue(companion.controlled)
        forged = deepcopy(fight)
        forged.native_companion_sources[str(companion_id)]["account_id"] += 1
        appearances.clear()
        with self.assertRaises(ValueError):
            adapter.owned_reconnect_bootstrap(forged, shared, session)
        self.assertEqual(appearances, [])
