"""Legitimate native innates/casts; no injected state or inflated NPC health."""
import importlib.util
import math
import struct
from pathlib import Path
import tempfile
import unittest


class CinetosisChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).resolve().parents[1]
            / "tools/audit_displacement_spell_reactions.py"
        )
        spec = importlib.util.spec_from_file_location(
            "native_movement_reactions_audit", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            cls.report = module.run(output_name=str(Path(directory) / "audit.json"))

    def test_normal_reaction_two_original_listeners(self):
        rows = [
            r
            for r in self.report["cases"]
            if r["spell_id"] == 5041 and r["scenario"] == "normal"
        ]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["status"], "executed")
            self.assertEqual(row["after"]["-7"]["hp"], 84)
            from wakfu_server.combat_parameters import parameter_value

            # Native normal415996 creates4801 at floor(float32(1+.1*level)).
            # Its selected normal listener416111 is AIR, base=statelevel, flags22/34.
            state_level = parameter_value([1.0, 0.1], 0, row["level"])
            applied = [
                s for s in row["after"]["-7"]["states"] if s["reference"] == 4801
            ]
            self.assertEqual([s["level"] for s in applied], [state_level])
            from wakfu_server.combat_damage_healing import damage_amount, consume_damage

            calculations = row["damage_calculations"]
            consumptions = row["damage_consumptions"]
            # Exactly one selected normal state4801 listener consumes damage.
            self.assertEqual(len(calculations), 1)
            self.assertEqual(len(consumptions), 1)
            calculation, consumption = calculations[0], consumptions[0]
            self.assertEqual(
                (calculation["base"], calculation["element"]), (state_level, 5)
            )
            source = {int(k): v for k, v in calculation["source_stats"].items()}
            target = {int(k): v for k, v in calculation["target_stats"].items()}
            bounds = [
                damage_amount(
                    state_level,
                    5,
                    source,
                    target,
                    coefficient_mask=calculation["coefficient_mask"],
                    arithmetic_context=calculation["arithmetic_context"],
                    rng=lambda: sample,
                )
                for sample in (0.0, 0.999999)
            ]
            self.assertGreaterEqual(calculation["amount"], min(bounds))
            self.assertLessEqual(calculation["amount"], max(bounds))
            self.assertEqual(consumption["value"], calculation["amount"])
            # Native eXt applies ceil(float32(value*.8)) for an actual BLOCK,
            # then source barrier / target armor / virtualHP / HP consumption.
            expected = consume_damage(consumption["value"], **consumption["context"])
            self.assertEqual(consumption["result"], expected)
            f32 = lambda value: struct.unpack(">f", struct.pack(">f", value))[0]
            native_value = (
                math.ceil(f32(f32(consumption["value"]) * f32(0.8)))
                if consumption["context"]["blocked"]
                else consumption["value"]
            )
            self.assertEqual(expected["value"], native_value)
            actual = row["after"]["-7"]["hp"] - row["after_pull"]["-7"]["hp"]
            self.assertEqual(actual, expected["hp_loss"])
            self.assertNotEqual(
                row["after"]["-7"]["position"], row["after_pull"]["-7"]["position"]
            )
            self.assertTrue(row["rollback_preserved"])
            self.assertTrue(row["pull_rollback_preserved"])

    def test_legitimate_berserker_innate_also_hits_on_cast(self):
        for row in self.report["cases"]:
            if row["scenario"] != "berserker":
                continue
            self.assertEqual(row["status"], "executed")
            self.assertIn(9315, [s["reference"] for s in row["before"]["7"]["states"]])
            self.assertTrue(row["preparation_casts"])
            self.assertTrue(
                all(cast["reference"] == 5028 for cast in row["preparation_casts"])
            )
            self.assertLess(row["before"]["7"]["hp"] * 2, row["before"]["7"]["max_hp"])
            self.assertLess(row["after"]["-7"]["hp"], row["before"]["-7"]["hp"])
            self.assertTrue(row["rollback_preserved"])
            self.assertTrue(row["pull_rollback_preserved"])

    def test_without_state_displacement_does_not_invent_damage(self):
        for row in self.report["cases"]:
            if row["scenario"] != "without_state":
                continue
            self.assertEqual(row["status"], "executed")
            self.assertNotEqual(
                row["before"]["-7"]["position"], row["after"]["-7"]["position"]
            )
            self.assertEqual(row["before"]["-7"]["hp"], row["after"]["-7"]["hp"])

    def test_fulgor_teleport_and_armor_both_levels(self):
        for row in self.report["cases"]:
            if row["spell_id"] != 5042:
                continue
            self.assertEqual(row["status"], "executed")
            self.assertNotEqual(
                row["before"]["7"]["position"], row["after"]["7"]["position"]
            )
            self.assertGreater(row["after"]["7"]["armor"], row["before"]["7"]["armor"])
            self.assertTrue(row["rollback_preserved"])
        self.assertTrue(self.report["sources_stable"])
