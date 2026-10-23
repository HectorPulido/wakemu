"""One focused compiler delta; no geometry heap or PostgreSQL fixture."""
import hashlib
import json
import unittest

import build_environmental_resource_profiles as compiler


class EnvironmentalResourceLevelCriteriaCompilerTests(unittest.TestCase):
    def test_four_original_level_criteria_require_opt_in_without_changing_frozen_seeds(
        self,
    ):
        source = json.loads(compiler.INVENTORY.read_text())
        scenarios = {row["id"]: row for row in source["scenarios"]}
        resources = {
            entry["payload"]["resource_reference"]: entry["payload"]
            for entry in json.loads(compiler.RECORDS.read_text())[
                "plant-resources.json"
            ]
        }
        action = next(
            action
            for stage in resources[757]["stage_definitions"]
            if stage["stage_id"] == 2
            for action in stage["actions"]
            if action["action_id"] == 2118
        )
        self.assertEqual(action["criteria"], "GetLevel() >= 10")
        self.assertEqual(compiler._criterion_minimum(action["criteria"]), 10)
        wanted = {
            -1953: "collaborative",
            -1949: "competitive",
            -1945: "race",
            -1941: "solo",
        }
        default, _ = compiler.generate_policies(include_competitive=True)
        self.assertFalse(wanted.keys() & {row["scenario_id"] for row in default})
        generated, _ = compiler.generate_policies(
            include_competitive=True, evaluated_resource_criteria=True
        )
        policies = [row for row in generated if row["scenario_id"] in wanted]
        self.assertEqual(len(policies), 4)
        self.assertEqual(
            {(row["map_id"], row["region_id"]) for row in policies}, {(1276, 89901)}
        )
        arguments = dict(
            policy_rows=policies,
            declared_character_races=True,
            declared_resource_competitions=True,
        )
        blocked_sql, _, blocked = compiler.compile_profiles(**arguments)
        self.assertEqual(blocked["blocked_criteria"], 4)
        self.assertNotIn("INSERT INTO environmental_runtime_profiles", blocked_sql)
        sql, _, admitted = compiler.compile_profiles(
            **arguments, evaluated_resource_criteria=True
        )
        self.assertEqual(admitted["disabled_profiles_emitted"], 4)
        self.assertEqual(admitted["activated_profiles"], 0)
        self.assertEqual(sql.count("INSERT INTO environmental_runtime_profiles"), 4)
        self.assertEqual(sql.count(",FALSE,FALSE);"), 4)
        self.assertNotIn("environmental_profile_resource_criteria", sql)
        for policy in policies:
            identity = policy["scenario_id"]
            config = {
                key.lower(): value
                for key, value in scenarios[identity]["configuration"].items()
            }
            self.assertEqual(
                (
                    config["challengelevelmin"],
                    config["challengelevelmax"],
                    config["ressourcerefid"],
                    config["ressourcestep"],
                ),
                ("201", "245", "757", "2"),
            )
            self.assertEqual(
                policy["duration_ms"], int(config["challengeduration"]) * 1000
            )
            key = f"resource-native-{abs(identity)}-1276-89901"
            required = int(
                config["ressourcequantitytospawn"]
                if wanted[identity] == "collaborative"
                else config["nbresourceforreward"]
            )
            self.assertIn(
                f"(E'{key}',1,E'resource',E'resource_collect',757,2118,2,E'interaction',{required});",
                sql,
            )
            self.assertIn(f",201,245,{int(config['nbresourceforreward'])},E'", sql)
            self.assertIn(
                f"AND scenario_id={identity} AND map_id=1276 AND region_id=89901 "
                "AND native_cells_present AND native_criteria=''",
                sql,
            )
        seed_hashes = {
            "environmental_resource_profiles.sql": "7d2eace560c5bc466bb73c6128ba026d6720e6e5e188e49e23c1761cc2cdbe2b",
            "environmental_resource_races.sql": "5ccc89f749e7e98d12df6240dd2b2c7f865fadf925a7026adfe4062f23d3b2e5",
            "environmental_resource_competitions.sql": "0c18f56a635fc9c44f091f1d3a0c4db6b3d793a9aebdb2c9dd0c97b631563e2e",
            "environmental_resource_results.sql": "b1ab66b98fd64703a06e21ca2997f825c9368b18ab599abb2aa4f4bf40b3f666",
        }
        for filename, digest in seed_hashes.items():
            self.assertEqual(
                hashlib.sha256(
                    (compiler.ROOT / "server/seeds" / filename).read_bytes()
                ).hexdigest(),
                digest,
            )
