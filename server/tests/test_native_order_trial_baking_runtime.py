"""Real 885 instance transport and bounded native baking callback runtime."""

from contextlib import nullcontext
import json
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock

from postgres_case import PostgresCase
from native_order_trial_runtime_fixture import create_area768_fixture


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT / ".runtime/quest-archetypes/pizza/astrub-pizzlarva-885.configuration.json"
)


class _Profiler:
    def span(self, _name):
        return nullcontext()


class NativeOrderTrialBakingRuntimeTests(PostgresCase):
    def test_real_885_publication_npc_contact_runs_original_768_callback(self):
        from wakfu_server import (
            dungeon_instances,
            dungeon_runtime,
            dungeon_runtime_config,
            owned_story_generic_entry,
            dungeon_context,
            native_transports,
        )
        from wakfu_server.application.transport import Connection
        from wakfu_server.position_buffer import Positions

        configuration = json.loads(CONFIG.read_text())
        account = self.store.register("native-768-owner", "isolated-test-password")[
            "id"
        ]
        character = self.store.create_character(
            account, "Native Callback Owner", breed=8
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, configuration)
            db.execute(
                "UPDATE characters SET map_id=546,instance_id=0,x=-4,y=-8,z=3 WHERE id=%s",
                (character["id"],),
            )

        previous_routes = dungeon_instances._ROUTES
        try:
            dungeon_instances.load_runtime_routes(self.store)
            live = {(account, generation, character["id"])}
            positions = Positions(
                self.store,
                lease_active=lambda owner, lease, identity: (owner, lease, identity)
                in live,
            )
            positions.attach(
                account, generation, self.store.character(account, character["id"])
            )
            groups = Mock()

            def initialize(db, admitted):
                dungeon_runtime.initialize_instance(
                    db, admitted, groups=groups, geometry={}, store=self.store
                )

            with positions.account_barrier(account):
                positions.flush(account_id=account)
                entered = owned_story_generic_entry.enter(
                    self.store,
                    account,
                    generation,
                    self.store.character(account, character["id"]),
                    struct.pack(">qHH", 23626, 0, 0),
                    loaded=True,
                    blocked=False,
                    allowed_position_accounts=frozenset({account}),
                    initialize_instance=initialize,
                )
                positions.rebind_selected(account, generation, character["id"])
            instance_id = entered["instance_id"]
            current = self.store.character(account, character["id"])
            self.assertEqual(
                tuple(current[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                (885, instance_id, 0, 0, 0),
            )

            context = dungeon_context.for_instance(
                self.store, instance_id, fight_in_progress=False
            )
            packets = native_transports.bootstrap(current, dungeon_context=context)
            body = next(payload for opcode, payload in packets if opcode == 13974)
            scope = (account, generation, character["id"], 885, instance_id)
            left, right = socket.socketpair()
            self.addCleanup(left.close)
            self.addCleanup(right.close)
            connection = Connection(left, runtime=Mock(PROFILER=_Profiler()))
            connection.native_instance_scope = lambda: scope
            frame = struct.pack(">IH", len(body) + 6, 13974) + body
            connection.sendall(frame)
            self.assertEqual(right.recv(len(frame)), frame)
            self.assertEqual(
                connection.instance_publications.published.instance_id, instance_id
            )

            bound = []

            def bind_before_snapshots(fight, characters, monsters):
                accepted = connection.instance_publications.bind_encounter(
                    fight,
                    connection.native_instance_scope(),
                    npc_ids=tuple(monsters),
                    player_id=character["id"],
                )
                bound.append(accepted)

            with create_area768_fixture(
                character_source=current,
                instance_id=instance_id,
                before_initialize=bind_before_snapshots,
                candidate_trial=False,
                player_position=(0, 0, 0),
            ) as (case, dispatcher, factory):
                self.assertEqual(bound, [True])
                fight = case.fight
                self.assertTrue(fight.native_instance_publication_required)
                self.assertEqual(fight.native_instance_publication_receipt[1], scope)
                self.assertEqual(fight.order, [character["id"], -7])
                case.advance()
                self.assertEqual(case.fight.current.id, -7)
                from wakfu_server.combat_qi_fight import move_registered_actor

                entrant = case.fight.actors[-7]
                previous = tuple(entrant.position)
                self.assertIn((previous, (-4, -6, 0)), case.fight.edges)
                # Native larvae are not ordinary AI actors. This component
                # test exercises the actual registered relocation/area callback,
                # without asserting an authored conveyor decision or MP cost.
                move_registered_actor(case.fight, entrant, (-4, -6, 0))
                dispatcher, _ = factory(
                    case.fight, {"native_retained_container": {"present": False}}
                )
                dispatcher.native_area_events.movement(
                    entrant.id, from_cell=previous, to_cell=entrant.position
                )
                fight = case.fight
                actors = {
                    identity: {
                        entry.reference: (entry.uid, entry.level)
                        for entry in actor.state_ledger.entries
                    }
                    for identity, actor in fight.actors.items()
                }
                summons = [
                    identity
                    for identity in getattr(fight, "native_summon_registrations", {})
                    if identity in fight.actors
                    and fight.actors[identity].native_summon_source.get("ref")
                    in (3206, 3239, 3240)
                ]
                self.assertEqual(fight.actors[-7].hp, 0)
                kills = [
                    row
                    for row in fight.events
                    if row.get("kind") == "kill_hp_minimum_update"
                    and row.get("generic_effect") == 118950
                ]
                self.assertEqual(len(kills), 1)
                from wakfu_server.combat_environment_glyphs import (
                    registered_environment_kill_source,
                )

                self.assertTrue(registered_environment_kill_source(fight, kills[0]))
                for forged in (
                    dict(kills[0], source_id=89998),
                    dict(kills[0], generic_effect=120464),
                    dict(
                        kills[0],
                        native_container={
                            "present": True,
                            "type": 3,
                            "native_kind": "effect_area",
                            "id": 89998,
                        },
                    ),
                ):
                    self.assertFalse(registered_environment_kill_source(fight, forged))
                print(
                    "BAKING_TRACE",
                    dict(
                        phase=fight.phase,
                        winner=fight.winner,
                        actors=sorted(fight.actors),
                        summons307=summons,
                        states3124={
                            identity: rows[3124]
                            for identity, rows in actors.items()
                            if 3124 in rows
                        },
                        area768=[
                            (uid, row.get("cell"))
                            for uid, row in fight.native_effect_areas.items()
                            if row.get("reference") == 768
                        ],
                        payments=case.payments,
                    ),
                    flush=True,
                )
        finally:
            dungeon_instances._ROUTES = previous_routes


if __name__ == "__main__":
    unittest.main()
