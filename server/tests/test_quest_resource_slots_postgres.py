"""A reviewed story paint point uses the normal native occupation transaction."""

from copy import deepcopy
import json
from pathlib import Path
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import combat_terrain, quest_resource_slots, resource_collect
from wakfu_server.achievements import mission_character_events, mission_toolkit, storage
from wakfu_server.planting import RESOURCES
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field


ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"
RESOURCE_PROFILE = json.loads(
    (ROOT / "maps/quest_resource_profiles/whisper-paint1295.json").read_text()
)
GEOMETRY = json.loads(
    (
        ROOT / "maps/quest_resource_profiles/whisper-paint1295.exploration.json"
    ).read_text()
)
TOOLKIT_PROFILE = json.loads(
    (
        ROOT / "achievements/mission_profiles/whispering-kingdom-fort-candidate.json"
    ).read_text()
)


def _request(action_id, x, y):
    def unsigned(value):
        return value if value >= 0 else value + (1 << 64)

    return (
        proto_field(8, action_id)
        + proto_field(16, unsigned(x))
        + proto_field(24, unsigned(y))
    )


class QuestResourceSlotsPostgresTests(PostgresCase):
    def test_whisper_paint_uses_native_occupation_prerequisites_and_refills_once(self):
        from os import environ
        from wakfu_server.postgres import Database

        profile = deepcopy(RESOURCE_PROFILE)
        toolkit_profile = deepcopy(TOOLKIT_PROFILE)
        geometry = deepcopy(GEOMETRY)

        # Copy only the two native definitions referenced by the reviewed
        # activation from the read-only runtime catalog into this test schema.
        runtime = Database(
            environ["WAKFU_DATABASE_URL"],
            password_file=environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(runtime.close)
        with runtime.connection() as source:
            release = source.execute(
                "SELECT revision,source_sha256,source_export,definition_count "
                "FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
            ).fetchone()
            native = source.execute(
                "SELECT definition_id,data FROM native_quest_metadata_definitions "
                "WHERE revision=%s AND definition_id=ANY(%s) ORDER BY definition_id",
                (release["revision"], [4871, 4872]),
            ).fetchall()
        self.assertEqual({row["definition_id"] for row in native}, {4871, 4872})

        account = self.store.register("whisper-paint", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Paint Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        placement = profile["placements"][0]
        approach = placement["approach"]
        clock = [self.store.clock()]
        self.store.clock = lambda: clock[0]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases "
                "(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    release["revision"],
                    Jsonb(release["source_sha256"]),
                    release["source_export"],
                    release["definition_count"],
                ),
            )
            for row in native:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES(%s,%s,%s)",
                    (release["revision"], row["definition_id"], Jsonb(row["data"])),
                )
            db.execute(
                "UPDATE characters SET level=96,map_id=1295,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*approach, character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[96], character["id"]),
            )
            mission_toolkit.install(db, toolkit_profile, activate=True)

            # The prior fort and its two owned prerequisites are declared QA
            # fixtures; paint progress itself is produced only by real harvests.
            state = storage.load_locked(db, character["id"])
            state["completed"] = [4871]
            storage.store(db, character["id"], state)

        installed = mission_character_events.ready(
            self.store,
            account,
            generation,
            self.store.character(account, character["id"]),
        )
        self.assertIn(13205, [opcode for opcode, _ in installed])
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            self.assertIn(4872, state["running"])
            state["objectives"] = [10046, 10047, 10048]
            state["variables"]["726"] = 9
            storage.store(db, character["id"], state)
            definitions = mission_toolkit.definitions(db, toolkit_profile)
            self.assertEqual(
                quest_resource_slots.install(
                    db, self.store, profile, definitions, geometry
                ),
                10,
            )

        character = self.store.character(account, character["id"])
        action = profile["resource_actions"][0]["action_id"]
        target = profile["placements"][0]
        resource_body = _request(action, *target["position"][:2])
        wrong_position = dict(character, x=approach[0] + 1)

        # Missing native objective prerequisites and a nonmatching approach
        # fail before an occupation row can be reserved.
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["objectives"] = [10046]
            storage.store(db, character["id"], state)
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            resource_collect.prepare(
                self.store,
                account,
                generation,
                character["id"],
                resource_body,
                reachable=lambda *_: True,
            )
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["objectives"] = [10046, 10047, 10048]
            storage.store(db, character["id"], state)
        with self.assertRaisesRegex(ValueError, "approach"):
            resource_collect.prepare(
                self.store,
                account,
                generation,
                character["id"],
                resource_body,
                reachable=lambda *_: True,
                location_context=lambda _current: wrong_position,
            )

        # Runtime flora lookup uses combat geometry. All reviewed points and
        # approaches must therefore be real adjacent edges there as well.
        combat_edges = {
            (tuple(first), tuple(second))
            for first, second in combat_terrain.map_geometry(1295)["edges"]
        }
        for row in profile["placements"]:
            self.assertIn(
                (tuple(row["approach"]), tuple(row["position"])), combat_edges
            )

        prepared = resource_collect.prepare(
            self.store,
            account,
            generation,
            character["id"],
            resource_body,
            reachable=lambda owner, resource: tuple(owner[k] for k in ("x", "y", "z"))
            == tuple(target["approach"]),
        )
        self.assertEqual(prepared["rule"]["duration_ms"], 3000)
        before_xp = self.store.character(account, character["id"])["xp"]
        ticket = resource_collect.reserve(self.store, account, generation, prepared)
        self.assertEqual(ticket["duration_ms"], 3000)
        clock[0] += 3.0
        result = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertTrue(result["applied"])
        self.assertEqual(result["outcome"]["quantity"], 0)
        self.assertEqual(result["outcome"]["xp"], 0)
        replay = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["packets"], [])

        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            self.assertEqual(state["variables"]["726"], 10)
            self.assertIn(10088, state["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key LIKE %s",
                    (
                        character["id"],
                        f"mission-toolkit:resource_action_completed:{action}:%",
                    ),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources WHERE resource_uid=%s "
                    "AND map_id=1295 AND instance_id=0 AND x=%s AND y=%s "
                    "AND resource_reference=450 AND stage=1",
                    (target["resource_uid"], *target["position"][:2]),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planting_growth_outbox "
                    "WHERE resource_uid=%s AND resource->>'quest_resource_spawn'='true'",
                    (target["resource_uid"],),
                ).fetchone()["n"],
                1,
            )
        self.assertEqual(
            self.store.character(account, character["id"])["xp"], before_xp
        )
