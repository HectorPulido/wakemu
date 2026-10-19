"""Serialize external marker reads against atomic Fight adoption."""

from copy import deepcopy
import ast
from pathlib import Path
import threading
import unittest
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase


def _public_member_packet(store):
    source = (
        Path(__file__).resolve().parents[1].joinpath("local_game_server.py").read_text()
    )
    tree = ast.parse(source)
    owner = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_publish_external_marker_locked"
    )
    callback = next(
        node
        for node in ast.walk(owner)
        if isinstance(node, ast.FunctionDef) and node.name == "public_member_packet"
    )
    namespace = {"STORE": store}
    module = ast.Module(body=[callback], type_ignores=[])
    exec(
        compile(ast.fix_missing_locations(module), "local_game_server.py", "exec"),
        namespace,
    )
    return namespace["public_member_packet"]


class ExternalMarkerConcurrencyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "markrace" + uuid.uuid4().hex[:10], "test-password"
        )["id"]
        self.character = self.store.create_character(
            self.account, "MarkerRace", breed=4
        )
        self.character_id = self.character["id"]
        from wakfu_server.health import maximum
        from wakfu_server.characters.progression import level_xp

        max_hp = maximum(4, 32)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,level=32,max_hp=%s,hp=%s,x=18,y=-23,z=2 "
                "WHERE id=%s",
                (max_hp, max_hp, self.character_id),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(32), self.character_id),
            )
            db.execute(
                "UPDATE account_wallets SET kamas=1000 WHERE account_id=%s",
                (self.account,),
            )

    def test_marker_reader_waits_for_atomic_fight_adoption_and_uses_live_wp(self):
        from wakfu_server import monsters
        from wakfu_server.breed_resources import live_wp
        from wakfu_server.combat.combat_area_boundary import adopt_fight
        from wakfu_server.combat.combat_external_markers import ExternalFightMarkers
        from wakfu_server.combat.combat_multiplayer_wire import decode_external
        from wakfu_server.combat.combat_shared import Session, SharedFight
        from tests.test_combat_public_character_postgres import (
            CombatPublicCharacterPostgresTests,
        )

        _character, actor, fight = CombatPublicCharacterPostgresTests._fight(self)
        actor.controlled = True
        current_before, maximum = live_wp(fight, self.character_id)
        self.assertGreater(current_before, 1)
        public_packet = _public_member_packet(self.store)
        shared = SharedFight(
            fight=fight,
            map_id=1134,
            instance_id=0,
            runtime=None,
            participants={
                self.account: Session(
                    self.account, self.character_id, "marker-generation", 1134, 0
                )
            },
            connected={self.account},
            group_lease=((1134, 0, 77), "marker-generation", fight.id, 1),
            join_context={
                "arena": {
                    "map_id": 1134,
                    "instance_id": 0,
                    "x": 1,
                    "y": 2,
                    "width": 1,
                    "height": 1,
                    "min_z": -1,
                    "max_z": 0,
                    "cell_masks": [0],
                    "team_values": [],
                },
                "terrain_effect_id": 46,
                "leaders": {0: self.character_id, 1: -90},
                "monsters": {
                    -90: monsters.owned_instance(
                        5525, 1, -90, map_id=1134, x=20, y=-23, z=2
                    )
                },
                "world_marker_cells": ((18, -23),),
                "world_marker_origin": (18, -23, 2),
                "fight_started_at": 99.5,
            },
        )
        markers = ExternalFightMarkers()
        reader_started = threading.Event()
        reader_done = threading.Event()
        observed = []
        errors = []

        def live_wp_spy(source_fight, actor_id):
            result = live_wp(source_fight, actor_id)
            observed.append((source_fight is shared.fight, actor_id, result))
            return result

        def read_marker():
            reader_started.set()
            try:
                markers.update(
                    shared,
                    now_ms=100_000,
                    now_monotonic=100.0,
                    member_packet=public_packet,
                )
            except BaseException as error:
                errors.append(error)
            finally:
                reader_done.set()

        with patch(
            "wakfu_server.breed_resources.live_wp",
            side_effect=live_wp_spy,
        ):
            with shared.lock:
                reader = threading.Thread(target=read_marker)
                reader.start()
                self.assertTrue(reader_started.wait(2))
                # A reader that ignores SharedFight.lock can observe the clear
                # between these actual adoption operations.
                self.assertFalse(reader_done.wait(0.05))
                candidate = deepcopy(fight)
                candidate.actors[self.character_id].effect_stats[4] = 2
                adopt_fight(fight, candidate)
            reader.join(5)

        self.assertFalse(reader.is_alive(), "marker reader did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(observed, [(True, self.character_id, (2, maximum))])
        self.assertEqual(len(markers.snapshots(1134, 0)), 1)
        snapshot = decode_external(markers.snapshots(1134, 0)[0][1])
        self.assertIn((self.character_id, 0), snapshot["teams"])

        # Confirm the original failure mode against the same callback: if the
        # caller omits the shared-fight lock, a read in the clear/update window
        # observes a partially adopted Fight and live_wp fails closed.
        cleared = threading.Event()
        restore = threading.Event()
        candidate = deepcopy(fight)

        def legacy_unlocked_adoption():
            fight.__dict__.clear()
            cleared.set()
            if not restore.wait(2):
                raise AssertionError("test did not release the legacy clear window")
            fight.__dict__.update(candidate.__dict__)

        writer = threading.Thread(target=legacy_unlocked_adoption)
        writer.start()
        self.assertTrue(cleared.wait(2))
        try:
            with self.assertRaises(AttributeError):
                public_packet(actor, fight)
        finally:
            restore.set()
            writer.join(2)
        self.assertFalse(writer.is_alive())
