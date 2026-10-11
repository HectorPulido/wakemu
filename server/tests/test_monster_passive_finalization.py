"""Final gate rederives passive qualification and still requires real attacks."""
import copy
import gzip
import hashlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_monster_activation_finalize as baseline
import test_monster_passive_initialization as fixture_data
import validate_monster_spell_activation as validator
from monster_passive_initialization import passive_initialization_proof


class PassiveFinalizationTests(unittest.TestCase):
    def prepare(self):
        base = baseline.MonsterActivationFinalizeTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        monster, document, casting = fixture_data.sources()
        monster.update(
            ref=1,
            native_abilities=[
                dict(spell_id=101, level_parameter=-1),
                dict(spell_id=102, level_parameter=-1),
            ],
        )
        document["spells"]["101"] = document["spells"].pop("4131")
        casting["101"] = casting.pop("4131")
        base.npc["spells"].update(document["spells"])
        base.npc["effects"].update(document["effects"])
        base.npc["activation_policy"]["enabled_monsters"]["1"][
            "initial_state_triples"
        ] = monster["initial_state_triples"]
        base.write_candidate()
        source_path = base.root / "monsters.json.gz"
        source_path.write_bytes(
            gzip.compress(json.dumps(dict(monsters=[monster])).encode())
        )
        casting_path = base.root / "casting.json.gz"
        casting_path.write_bytes(
            gzip.compress(json.dumps(dict(spells=casting)).encode())
        )
        base.manifest["native_source_provenance"] = dict(
            bundle_documents={
                "monsters.json.gz": baseline.finalizer.digest(source_path),
                "casting.json.gz": baseline.finalizer.digest(casting_path),
            }
        )
        base.write_manifest()
        base.audit["candidate_manifest_sha256"] = baseline.finalizer.digest(
            base.candidate / "manifest.json"
        )
        base.audit["changed_document_hashes"] = base.manifest["changed_documents"]
        base.audit["native_monsters_path"] = str(source_path)
        base.audit["native_monsters_sha256"] = baseline.finalizer.digest(source_path)
        next(row for row in base.audit["monsters"] if row["ref"] == 2)[
            "status"
        ] = "pending"
        row = next(row for row in base.audit["monsters"] if row["ref"] == 1)
        row["ai_commit"].update(
            level=1, native_initialization=fixture_data.receipt(monster, 1)
        )
        for observed in row["cases"]:
            initialized = fixture_data.receipt(monster, observed["level"])
            if observed["spell_id"] == 101:
                observed.update(
                    status="passive_initialization_only",
                    reference=1,
                    spell_level=observed["level"],
                    attempts=0,
                    errors={},
                    successful_targets=[],
                    initialization_receipts=[initialized],
                )
                observed["passive_initialization_proof"] = passive_initialization_proof(
                    monster,
                    observed["level"],
                    101,
                    observed["spell_level"],
                    document,
                    casting,
                    initialized,
                    validator.initialization_proven,
                )
            else:
                for target in observed["successful_targets"]:
                    target["native_initialization"] = initialized
        return base, row, monster, document, casting

    def test_valid_passive_and_real_attack_book_retains_all_owned_spells(self):
        base, row, monster, document, casting = self.prepare()
        base.write_audit()
        result = baseline.finalizer.finalize(
            base.candidate, base.validation, base.output
        )
        final_npc = json.loads(
            (base.output / "native-npc-spell-effect-trees.json").read_text()
        )
        self.assertEqual(
            final_npc["activation_policy"]["enabled_monsters"]["1"]["spell_ids"],
            [101, 102],
        )

    def test_forged_passive_missing_receipt_and_source_change_do_not_promote(self):
        for kind in ("missing", "forged", "source"):
            with self.subTest(kind=kind):
                base, row, monster, document, casting = self.prepare()
                passive = row["cases"][0]
                if kind == "missing":
                    passive["initialization_receipts"] = []
                elif kind == "forged":
                    passive["passive_initialization_proof"]["state_level"] = 999
                else:
                    Path(base.audit["native_monsters_path"]).write_bytes(b"changed")
                base.write_audit()
                with self.assertRaisesRegex(ValueError, "No completely validated"):
                    baseline.finalizer.finalize(
                        base.candidate, base.validation, base.output
                    )

    def test_only_passive_labels_cannot_replace_all_attacks(self):
        base, row, monster, document, casting = self.prepare()
        for observed in row["cases"]:
            if observed["spell_id"] == 102:
                observed.update(
                    status="passive_initialization_only",
                    attempts=0,
                    errors={},
                    successful_targets=[],
                    passive_initialization_proof=row["cases"][0][
                        "passive_initialization_proof"
                    ],
                )
        base.write_audit()
        with self.assertRaisesRegex(ValueError, "No completely validated"):
            baseline.finalizer.finalize(base.candidate, base.validation, base.output)


class PassiveValidatorHookTests(unittest.TestCase):
    def test_native_passive_fixture_does_not_preview_cast_or_describe_attack(self):
        monster, document, casting = fixture_data.sources()
        initialized = fixture_data.receipt(monster, 1)
        describe, prepare = Mock(), Mock()
        modules = {
            "wakfu_server.combat_ai_capabilities": types.SimpleNamespace(
                describe_spell=describe
            ),
            "wakfu_server.combat_npc_spell": types.SimpleNamespace(
                prepare_npc_spell=prepare
            ),
            "wakfu_server.combat_geometry_snapshot": types.SimpleNamespace(
                source_snapshot=Mock()
            ),
            "wakfu_server.combat_native_spell_casting": types.SimpleNamespace(
                catalog=lambda: casting
            ),
            "wakfu_server.combat_npc_attack": types.SimpleNamespace(
                npc_spell_catalog=lambda: document
            ),
        }
        context = (
            types.SimpleNamespace(
                native_npc_initialization_receipts={-200: initialized}
            ),
            None,
            {},
            [],
        )
        with patch.dict(sys.modules, modules), patch.dict(
            validator.NATIVE_SOURCE_MONSTERS, {2867: monster}
        ), patch.object(validator, "fixture", return_value=context):
            observed = validator.run_case(2867, 1, 4131, 1, [(-7, -7, -1)], 1)
            self.assertEqual(observed["status"], "passive_initialization_only")
            self.assertTrue(validator.case_qualification_complete(observed))
        describe.assert_not_called()
        prepare.assert_not_called()
        self.assertEqual(observed["attempts"], 0)
        self.assertEqual(observed["successful_targets"], [])
