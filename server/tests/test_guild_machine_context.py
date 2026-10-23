"""Native interaction cells and installed-machine identity fence guild actions."""
import unittest

from wakfu_server.guild_machine_context import machines, validate


class GuildMachineContextTests(unittest.TestCase):
    @staticmethod
    def context(machine):
        x, y, z = machine["use_cell"]
        character = dict(map_id=machine["map_id"], x=x, y=y, z=z, instance_id=0)
        x, y, z = machine["object_position"]
        installed = dict(
            id=machine["object_id"],
            type="GuildMachine",
            map_id=machine["map_id"],
            x=x,
            y=y,
            z=z,
        )
        return character, installed

    def test_each_native_machine_accepts_only_its_exact_use_cell(self):
        for machine in machines():
            with self.subTest(object_id=machine["object_id"]):
                character, installed = self.context(machine)
                result = validate(character, [installed])
                self.assertEqual(result["object_id"], machine["object_id"])
                self.assertEqual(result["use_cell"], tuple(machine["use_cell"]))
                for field in ("x", "y", "z"):
                    with self.subTest(displaced=field):
                        with self.assertRaises(ValueError):
                            validate(
                                dict(character, **{field: character[field] + 1}),
                                [installed],
                            )

    def test_correct_cell_requires_the_original_installed_machine(self):
        character, installed = self.context(machines()[0])
        for changed in (
            dict(installed, id=installed["id"] + 1),
            dict(installed, type="Chest"),
            dict(installed, map_id=installed["map_id"] + 1),
            dict(installed, z=installed["z"] + 1),
        ):
            with self.subTest(installed=changed):
                with self.assertRaises(ValueError):
                    validate(character, [changed])
        for objects in ([], [installed, dict(installed)]):
            with self.assertRaises(ValueError):
                validate(character, objects)

    def test_private_instances_and_missing_live_positions_cannot_authorize(self):
        character, installed = self.context(machines()[0])
        with self.assertRaises(ValueError):
            validate(dict(character, instance_id=1), [installed])
        for field in ("map_id", "x", "y", "z"):
            with self.subTest(missing=field):
                missing = dict(character)
                del missing[field]
                with self.assertRaises(ValueError):
                    validate(missing, [installed])


if __name__ == "__main__":
    unittest.main()
