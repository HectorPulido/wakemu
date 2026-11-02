"""Private NEXT reviewed actions: ordinary public entries only, never admin."""
import json, struct, unittest
from pathlib import Path
from copy import deepcopy

B = Path(__file__).resolve().parent
from wakfu_server import combat_encounter_world_action_start as subject


class PublicEncounterActionCohortTests(unittest.TestCase):
    def cases(self):
        for entry in json.loads(
            (B / "fixtures/native_encounter_world_action_cohort.json").read_text()
        ):
            c = entry["config"]
            native = entry["native"]
            ref = native["ref"]
            map_id = c["route"]["start_map_id"]
            identity = 10000
            roster = c["compiled_plan"]["rooms"][0]["monsters"]
            room = dict(
                order=1,
                monsters=[dict(ref_id=m["ref_id"], count=m["count"]) for m in roster],
            )
            character = dict(
                id=7, account_id=3, map_id=map_id, instance_id=identity, x=0, y=0, z=0
            )
            group = dict(
                key=(map_id, identity, 900),
                status="available",
                members=[
                    dict(
                        id=-900,
                        ref=ref,
                        map_id=map_id,
                        instance_id=identity,
                        x=1,
                        y=0,
                        z=0,
                    )
                ],
            )
            args = dict(
                instance=dict(
                    instance_id=identity,
                    party_id=500,
                    status="active",
                    context_route_key=c["route"]["key"],
                    context_policy_version=c["version"],
                ),
                progress=dict(
                    instance_id=identity,
                    party_id=500,
                    status="active",
                    current_room=1,
                    catalog_hash=c["compiled_plan"]["document_sha256"],
                    rooms=[room],
                ),
                membership=dict(
                    instance_id=identity, party_id=500, character_id=7, status="active"
                ),
                spawn=dict(
                    instance_id=identity,
                    room_order=1,
                    asset_map_id=map_id,
                    group_id=900,
                ),
                group=group,
                config=c,
                native_source=lambda ref, native=native: native,
            )
            yield character, native, args

    def test_three_original_public_actions_enter_the_same_declared_group(self):
        for char, native, args in self.cases():
            action = next(a for a in native["world_actions"] if a["clT"] == "")
            with self.subTest(reference=native["ref"]):
                before = deepcopy(native)
                result = subject.admit_records(
                    char, struct.pack(">qq", -900, action["d"]), **args
                )
                self.assertEqual(result["group_key"], args["group"]["key"])
                self.assertEqual(native, before)
                self.assertIn(13, native["raw_native"]["csc"])
                self.assertEqual(result["action_id"], action["d"])

    def test_every_original_admin_action_is_denied(self):
        count = 0
        for char, native, args in self.cases():
            for action in native["world_actions"]:
                if action["clT"] != "IsAdmin()":
                    continue
                with self.subTest(
                    reference=native["ref"], action=action["d"]
                ), self.assertRaises(ValueError):
                    subject.admit_records(
                        char, struct.pack(">qq", -900, action["d"]), **args
                    )
                count += 1
        self.assertEqual(count, 12)

    def test_changed_source_stale_group_or_pinned_plan_cannot_start(self):
        for char, native, args in self.cases():
            action = next(a for a in native["world_actions"] if a["clT"] == "")
            body = struct.pack(">qq", -900, action["d"])
            args["group"]["status"] = "fighting"
            with self.assertRaises(ValueError):
                subject.admit_records(char, body, **args)
            args["group"]["status"] = "available"
            action["clT"] = "IsAdmin()"
            with self.assertRaises(ValueError):
                subject.admit_records(char, body, **args)

    def test_unreviewed_route_still_declines_ordinary_interact(self):
        for char, native, args in self.cases():
            args["instance"]["context_route_key"] = "unrelated-native-world-action"
            self.assertIsNone(
                subject.admit_records(char, struct.pack(">qq", -900, 908), **args)
            )


if __name__ == "__main__":
    unittest.main()
