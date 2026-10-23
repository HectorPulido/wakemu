"""Source-corpus and closed-policy tests for the offline resource compiler."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import build_environmental_resource_profiles as compiler


class EnvironmentalResourceProfileCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(compiler.INVENTORY.read_text())
        records = json.loads(compiler.RECORDS.read_text())
        resources = {
            r["payload"]["resource_reference"]: r["payload"]
            for r in records["plant-resources.json"]
        }
        cls.originals = {}
        for scenario in cls.inventory["scenarios"]:
            config = {k.lower(): v for k, v in scenario["configuration"].items()}
            if "ressourcerefid" not in config:
                continue
            resource = resources[int(config["ressourcerefid"])]
            actions = [
                a
                for stage in resource["stage_definitions"]
                if stage["stage_id"] == int(config["ressourcestep"])
                for a in stage["actions"]
            ]
            cls.originals[scenario["id"]] = (
                scenario,
                config,
                actions[0] if actions else None,
            )

    @staticmethod
    def policy(identity, **changes):
        row = dict(
            zip(
                compiler.POLICY_COLUMNS,
                (
                    identity,
                    1134,
                    1,
                    60000,
                    0,
                    None,
                    "quantity",
                    "reviewed-runtime-policy",
                    "reviewed-reward-policy",
                    None,
                    None,
                    17,
                    None,
                ),
            )
        )
        row.update(changes)
        return row

    @classmethod
    def eligible(cls):
        return [
            (identity, scenario, config, action)
            for identity, (scenario, config, action) in sorted(cls.originals.items())
            if action is not None
            and not action["criteria"]
            and not action["item_reference"]
            and not action["product_references"]
        ]

    def test_all_313_original_scenarios_preserve_source_values_without_activation(self):
        sql, census, summary = compiler.compile_profiles()
        self.assertEqual(len(self.originals), 313)
        self.assertEqual({r["scenario_id"] for r in census}, set(self.originals))
        matched = [a for _, _, a in self.originals.values() if a is not None]
        self.assertEqual(len(matched), 305)
        self.assertEqual(
            len(
                {
                    (int(c["ressourcerefid"]), int(c["ressourcestep"]), a["action_id"])
                    for _, c, a in self.originals.values()
                    if a is not None
                }
            ),
            78,
        )
        self.assertEqual(
            sorted(i for i, (_, _, a) in self.originals.items() if a is None),
            [-1880, -1879, -1878, -1877, -1637, -1636, -1635, -1634],
        )
        self.assertEqual(sum(bool(a["criteria"]) for a in matched), 4)
        self.assertEqual(
            sum(bool(a["item_reference"] or a["product_references"]) for a in matched),
            1,
        )
        self.assertEqual(len(self.eligible()), 300)
        for row in census:
            scenario, config, action = self.originals[row["scenario_id"]]
            with self.subTest(scenario=row["scenario_id"]):
                self.assertEqual(
                    (
                        row["resource_reference"],
                        row["resource_step"],
                        row["required_quantity"],
                        row["spawn_quantity"],
                        row["level_min"],
                        row["level_max"],
                    ),
                    tuple(
                        int(config[k])
                        for k in (
                            "ressourcerefid",
                            "ressourcestep",
                            "nbresourceforreward",
                            "ressourcequantitytospawn",
                            "challengelevelmin",
                            "challengelevelmax",
                        )
                    ),
                )
                self.assertEqual(
                    row["action_id"], None if action is None else action["action_id"]
                )
                self.assertEqual(row["native_duration_raw"], scenario["duration_raw"])
                self.assertEqual(row["native_subtype"], scenario["subtype"])
                self.assertEqual(
                    row["original_base_xp"],
                    [r["field_agO"] for r in scenario["rewards"]],
                )
                self.assertIn("explicit_runtime_policy", row["missing"])
        self.assertEqual(
            (
                summary["native_scenarios"],
                summary["current_producer_candidates"],
                summary["policy_rows"],
                summary["activated_profiles"],
            ),
            (313, 300, 0, 0),
        )
        self.assertNotIn("INSERT INTO environmental_runtime_profiles", sql)
        self.assertNotIn("INSERT INTO environmental_profile_rewards", sql)

    def test_typed_csv_bulk_emits_only_eligible_disabled_profiles_and_explicit_rewards(
        self,
    ):
        representatives = {}
        for identity, scenario, config, action in self.eligible():
            representatives.setdefault(scenario["subtype"], (identity, config, action))
        self.assertTrue(representatives)
        rows = [
            self.policy(
                identity,
                unit="interaction" if n % 2 else "quantity",
                recurrence_period_ms=120000 if n % 2 else None,
                reward_item_reference=999999 if n == 0 else None,
                reward_item_quantity=2 if n == 0 else None,
            )
            for n, (identity, _, _) in enumerate(representatives.values())
        ]
        blocked = {}
        for identity, (_, _, action) in self.originals.items():
            category = (
                "blocked_missing_stage"
                if action is None
                else "blocked_criteria"
                if action["criteria"]
                else "blocked_product_settlement"
                if action["item_reference"] or action["product_references"]
                else None
            )
            if category:
                blocked.setdefault(category, identity)
        rows.extend(self.policy(identity) for identity in blocked.values())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=compiler.POLICY_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            parsed = compiler.policies(path)
        self.assertEqual(parsed, tuple(rows))
        sql, census, summary = compiler.compile_profiles(policy_rows=parsed)
        supported = [
            row
            for row in rows[: len(representatives)]
            if self.originals[row["scenario_id"]][0]["subtype"] in (1, 4)
        ]
        self.assertEqual(len(census), 313)
        self.assertEqual(summary["disabled_profiles_emitted"], len(supported))
        self.assertEqual(
            summary["blocked_unsupported_mode"], len(representatives) - len(supported)
        )
        for category in blocked:
            self.assertEqual(summary[category], 1)
        self.assertEqual(
            sql.count("INSERT INTO environmental_runtime_profiles"), len(supported)
        )
        self.assertEqual(sql.count(",FALSE,FALSE);"), len(supported))
        self.assertNotIn("TRUE", sql)
        self.assertEqual(summary["activated_profiles"], 0)
        for row in supported:
            identity = row["scenario_id"]
            scenario, config, action = self.originals[identity]
            required = int(
                config["ressourcequantitytospawn"]
                if scenario["subtype"] == 4
                else config["nbresourceforreward"]
            )
            key = f"resource-native-{abs(identity)}-1134-1"
            self.assertIn(
                f"(E'{key}',1,E'resource',E'resource_collect',"
                f"{int(config['ressourcerefid'])},{action['action_id']},"
                f"{int(config['ressourcestep'])},E'{row['unit']}',"
                f"{required});",
                sql,
            )
            self.assertIn(
                f",{int(config['challengelevelmin'])},{int(config['challengelevelmax'])},"
                f"{int(config['nbresourceforreward'])},E'reviewed-runtime-policy'",
                sql,
            )
            self.assertIn(f"E'xp',NULL,17,E'reviewed-reward-policy'", sql)

    def test_closed_policy_schema_rejects_overrides_partial_authority_and_invalid_csv(
        self,
    ):
        identity = self.eligible()[0][0]
        valid = self.policy(identity)
        invalid = [
            dict(valid, **change)
            for change in (
                {"action_id": 999},
                {"required_quantity": 1},
                {"map_id": True},
                {"duration_ms": 0},
                {"anchor_ms": -1},
                {"recurrence_period_ms": 59999},
                {"unit": "inferred"},
                {"authority": ""},
                {"reward_authority": "bad\0authority"},
                {"reward_item_reference": 1},
                {"reward_xp": True},
                {"reward_xp": 2**31},
                {"reward_xp": None},
                {"scenario_id": -2147483649},
            )
        ]
        invalid.append({k: v for k, v in valid.items() if k != "duration_ms"})
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                compiler.compile_profiles(policy_rows=(row,))
        with self.assertRaises(ValueError):
            compiler.compile_profiles(policy_rows=(valid, dict(valid)))
        foreign = next(
            s["id"]
            for s in self.inventory["scenarios"]
            if s["id"] not in self.originals
        )
        with self.assertRaises(ValueError):
            compiler.compile_profiles(policy_rows=(self.policy(foreign),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for content in (
                "scenario_id,map_id\n-1,1\n",
                ",".join(compiler.POLICY_COLUMNS) + "\n-1,1\n",
            ):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    compiler.policies(path)
        # Territory membership is checked by original SQL authority, not guessed offline.
        identity = next(
            i for i, scenario, _, _ in self.eligible() if scenario["subtype"] in (1, 4)
        )
        sql, _, summary = compiler.compile_profiles(
            policy_rows=(
                self.policy(identity, map_id=2147483647, region_id=2147483646),
            )
        )
        self.assertIn(
            "IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations", sql
        )
        self.assertIn(
            f"AND scenario_id={identity} AND map_id=2147483647 AND region_id=2147483646 AND native_cells_present",
            sql,
        )
        self.assertIn(
            "RAISE EXCEPTION 'Resource profile lacks original scenario territory'", sql
        )
        self.assertIn(",FALSE,FALSE);", sql)
        self.assertEqual(summary["activated_profiles"], 0)

    def test_generated_source_policies_keep_seconds_rewards_and_refuse_unsupported_modes(
        self,
    ):
        rows, omissions = compiler.generate_policies()
        self.assertEqual((len(rows), len({r["scenario_id"] for r in rows})), (261, 225))
        with compiler.LOCATIONS.open(newline="") as stream:
            scopes = {
                (int(r["scenario_id"]), int(r["map_id"]), int(r["region_id"]))
                for r in csv.DictReader(stream)
                if r["native_cells_present"] == "True"
                and r["map_id"]
                and r["region_id"]
                and r["native_criteria"] == ""
            }
        for row in rows:
            scenario, config, action = self.originals[row["scenario_id"]]
            with self.subTest(
                scenario=scenario["id"], map=row["map_id"], region=row["region_id"]
            ):
                self.assertIn((scenario["id"], row["map_id"], row["region_id"]), scopes)
                self.assertEqual(row["duration_ms"], scenario["duration_raw"] * 1000)
                self.assertEqual(
                    row["duration_ms"], int(config["challengeduration"]) * 1000
                )
                self.assertEqual(
                    (row["anchor_ms"], row["recurrence_period_ms"], row["unit"]),
                    (0, None, "interaction"),
                )
                self.assertFalse(
                    action["criteria"]
                    or action["item_reference"]
                    or action["product_references"]
                )
                self.assertEqual(len(scenario["rewards"]), 1)
                reward = scenario["rewards"][0]
                self.assertEqual(row["reward_xp"], reward["field_agO"] or None)
                self.assertEqual(row["reward_kamas"], reward["field_aHk"] or None)
                self.assertEqual(
                    row["reward_item_reference"], reward["field_aAi"] or None
                )
                self.assertEqual(
                    row["reward_item_quantity"],
                    reward["field_aHj"] if reward["field_aAi"] else None,
                )
                self.assertIn("wakemu-", row["authority"])
                self.assertIn("not-original-server-grant", row["reward_authority"])
        conditional = [
            r
            for r in omissions
            if r["reason"] == "conditional_or_ranked_reward_policy_unqualified"
        ]
        self.assertEqual(len(conditional), 87)
        self.assertTrue(
            all(
                self.originals[r["scenario_id"]][0]["subtype"] == 3 for r in conditional
            )
        )
        sql, census, summary = compiler.compile_profiles(policy_rows=rows)
        self.assertEqual(len(census), 313)
        self.assertEqual(
            (
                summary["disabled_profiles_emitted"],
                summary["blocked_unsupported_mode"],
                summary["activated_profiles"],
            ),
            (174, 87, 0),
        )
        self.assertEqual(sql.count("INSERT INTO environmental_runtime_profiles"), 174)
        self.assertNotIn("TRUE", sql)
        self.assertNotIn("E'race'", sql)
        self.assertNotIn("E'competitive'", sql)
        self.assertIn("AND native_cells_present AND native_criteria=''", sql)

    def test_changed_or_missing_original_source_fails_before_generating_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            path.write_bytes(compiler.INVENTORY.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                compiler.compile_profiles(inventory_path=path)
            records = json.loads(compiler.RECORDS.read_text())
            records["plant-resources.json"][0]["payload"]["resource_reference"] += 1
            path.write_text(json.dumps(records))
            with self.assertRaises(ValueError):
                compiler.compile_profiles(records_path=path)
            with self.assertRaises(FileNotFoundError):
                compiler.compile_profiles(records_path=Path(directory) / "absent.json")


if __name__ == "__main__":
    unittest.main()
