"""Pinned native story states use the ordinary durable buff carrier and wire."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_gameplay_states as marker_states
from wakfu_server.achievements import storage
from wakfu_server.items import quest_inventory


PROFILE = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.json"
)


def native_descriptor(state_id=3679):
    return dict(
        state_id=state_id,
        maximum_level=1,
        duration_base=-1,
        realtime_duration_base=-1000,
        skip_turn_timer=True,
        marker_effect_id=48123,
        marker_generic=400,
        marker_parameters=[0, 0],
        source_sha256="a" * 64,
    )


class OwnedStoryGameplayStatePolicyTests(unittest.TestCase):
    def test_native_marker_descriptor_is_strict_and_native_state_effect_is_scalar(self):
        selected = {"map_id": 887}
        descriptor = native_descriptor()
        with patch.object(
            __import__("wakfu_server.owned_story_mechanics", fromlist=["sources"]),
            "sources",
            return_value={"marker_states": {"3679": descriptor}},
        ):
            self.assertEqual(marker_states.descriptor(selected, 3679), descriptor)
            for key, value in (
                ("maximum_level", 0),
                ("duration_base", 0),
                ("realtime_duration_base", 0),
                ("skip_turn_timer", False),
                ("marker_effect_id", 0),
                ("marker_generic", 399),
                ("marker_parameters", [1, 0]),
                ("source_sha256", "bad"),
            ):
                malformed = dict(descriptor, **{key: value})
                with self.subTest(field=key), self.assertRaisesRegex(
                    ValueError, "native marker"
                ):
                    marker_states.validate_descriptor(malformed, 3679)

        profile = json.loads(PROFILE.read_text())
        invalid_effects = (
            dict(kind="native_state", state_id=0, active=True),
            dict(kind="native_state", state_id=-1, active=True),
            dict(kind="native_state", state_id=32768, active=True),
            dict(kind="native_state", state_id=3679, active=1),
        )
        for effect in invalid_effects:
            malformed = deepcopy(profile)
            malformed["steps"][0]["effects"].append(effect)
            with self.subTest(effect=effect), self.assertRaisesRegex(
                ValueError, "native identity"
            ):
                controller.policy(dict(topology=dict(owned_story_controller=malformed)))

    def test_has_state_handles_null_and_malformed_origins_and_scopes_story_markers(
        self,
    ):
        actor = dict(id=7, instance_id=99)
        for origin in (None, {"kind": "native-state", "character_id": 7}):
            self.assertTrue(
                marker_states.has_state(
                    dict(
                        actor,
                        consumable_states=[dict(state_id=3679, native_origin=origin)],
                    ),
                    3679,
                )
            )
        self.assertTrue(
            marker_states.has_state(
                dict(actor, consumable_states=[dict(state_id=3679)]), 3679
            )
        )
        story_origin = dict(
            kind="owned-story-native-marker", character_id=7, instance_id=99
        )
        carrier = dict(state_id=3679, native_origin=story_origin)
        self.assertTrue(
            marker_states.has_state(dict(actor, consumable_states=[carrier]), 3679)
        )
        self.assertFalse(
            marker_states.has_state(
                dict(actor, instance_id=100, consumable_states=[carrier]), 3679
            )
        )
        self.assertFalse(
            marker_states.has_state(
                dict(id=8, instance_id=99, consumable_states=[carrier]), 3679
            )
        )
        self.assertFalse(
            marker_states.has_state(
                dict(
                    actor,
                    consumable_states=[dict(state_id=3679, native_origin="bad")],
                ),
                3679,
            )
        )


class OwnedStoryGameplayStatePostgresTests(PostgresCase):
    def test_marker_hydration_scope_delta_removal_and_existing_item_origin(self):
        account = self.store.register("story-marker-state", "isolated-password")["id"]
        actor = self.store.create_character(account, "Story Marker")
        generation = self.store.begin_session(account, ttl=10000)
        self.store.select_character(account, generation, actor["id"])
        actor_id = actor["id"]
        instance_id = 919
        selected = json.loads(PROFILE.read_text())
        active = dict(kind="native_state", state_id=3679, active=True)
        inactive = dict(kind="native_state", state_id=3679, active=False)
        step = next(row for row in selected["steps"] if row["id"] == "room1-victory")
        step["effects"].extend((active, inactive))
        native = native_descriptor()

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=887,instance_id=%s WHERE id=%s",
                (instance_id, actor_id),
            )
            before_mission = storage.load_locked(db, actor_id)
            before_items = db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE character_id=%s ORDER BY reference,uid",
                (actor_id,),
            ).fetchall()

            # A normal item-origin buff remains valid under the extended origin
            # CHECK. Its item and carrier also provide an unchanged baseline.
            container = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (actor_id,),
            ).fetchone()["uid"]
            item_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,10380,1,%s,0) RETURNING uid",
                (actor_id, container),
            ).fetchone()["uid"]
            item_buff = db.execute(
                "INSERT INTO character_consumable_buffs(character_id,state_id,level,"
                "source_item_ref,source_item_uid,clock,duration_ms,remaining_ms,metadata) "
                "VALUES(%s,3678,1,10380,%s,'event',0,0,%s) RETURNING uid",
                (
                    actor_id,
                    item_uid,
                    Jsonb({"metadata": {"native_realtime_duration_base": -1}}),
                ),
            ).fetchone()
            before_items = db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE character_id=%s ORDER BY reference,uid",
                (actor_id,),
            ).fetchall()

            def scope(_db, _store, character):
                if (
                    character["id"] != actor_id
                    or character["instance_id"] != instance_id
                ):
                    raise ValueError("marker does not belong to this owner and run")
                return selected, {"room1-victory"}

            mechanics = __import__(
                "wakfu_server.owned_story_mechanics", fromlist=["sources"]
            )
            with patch.object(
                mechanics,
                "sources",
                return_value={"marker_states": {"3679": native}},
            ), patch.object(controller, "_scope", side_effect=scope):
                hydrated_before = self.store.character(account, actor_id, db)
                packets = marker_states.apply(
                    db, self.store, hydrated_before, selected, active
                )
                self.assertIn(12613, [opcode for opcode, _ in packets])
                hydrated = self.store.character(account, actor_id, db)
                self.assertTrue(marker_states.has_state(hydrated, 3679))
                marker = db.execute(
                    "SELECT uid,source_item_ref,source_item_uid,metadata,native_origin "
                    "FROM character_consumable_buffs WHERE character_id=%s AND state_id=3679",
                    (actor_id,),
                ).fetchone()
                self.assertIsNone(marker["source_item_ref"])
                self.assertIsNone(marker["source_item_uid"])
                self.assertEqual(
                    marker["metadata"]["metadata"]["native_marker_generic"], 400
                )
                self.assertEqual(marker["native_origin"]["instance_id"], instance_id)

                foreign = self.store.create_character(account, "Foreign Marker")
                for misplaced in (
                    dict(hydrated, id=foreign["id"]),
                    dict(hydrated, instance_id=instance_id + 1),
                ):
                    with self.subTest(
                        owner=misplaced["id"], instance=misplaced["instance_id"]
                    ):
                        with self.assertRaisesRegex(ValueError, "owner and run"):
                            marker_states.apply(
                                db, self.store, misplaced, selected, active
                            )
                still_present = db.execute(
                    "SELECT uid,native_origin FROM character_consumable_buffs "
                    "WHERE character_id=%s AND state_id=3679",
                    (actor_id,),
                ).fetchone()
                self.assertEqual(still_present["uid"], marker["uid"])
                self.assertEqual(
                    still_present["native_origin"], marker["native_origin"]
                )

                packets = marker_states.apply(
                    db, self.store, hydrated, selected, inactive
                )
                self.assertIn(13560, [opcode for opcode, _ in packets])
                self.assertFalse(
                    marker_states.has_state(
                        self.store.character(account, actor_id, db), 3679
                    )
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM character_consumable_buffs WHERE character_id=%s AND state_id=3679",
                        (actor_id,),
                    ).fetchone()
                )
                self.assertEqual(storage.load_locked(db, actor_id), before_mission)
                after_items = db.execute(
                    "SELECT reference,quantity FROM inventory_items WHERE character_id=%s ORDER BY reference,uid",
                    (actor_id,),
                ).fetchall()
                self.assertEqual(after_items, before_items)
                self.assertEqual(
                    db.execute(
                        "SELECT uid,source_item_ref,source_item_uid FROM character_consumable_buffs "
                        "WHERE character_id=%s AND state_id=3678",
                        (actor_id,),
                    ).fetchone(),
                    dict(
                        uid=item_buff["uid"],
                        source_item_ref=10380,
                        source_item_uid=item_uid,
                    ),
                )
