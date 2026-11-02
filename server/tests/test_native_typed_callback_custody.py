"""Focused native typed-custody and unchanged legacy closure qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
from wakfu_server import combat_ai_callback_spells as policy
from wakfu_server import native_catalog

SCHEDULED = frozenset(
    (7272, 7274, 7275, 7276, 7277, 7278, 7279, 7280, 7281, 7282, 7284, 7287, 7288)
)
POLICY = "wakemu-rushu-native-vestige-callbacks-v1"


def record(row):
    return dict(
        actor_reference=row["actor_reference"],
        initial_state=row["initial_state"],
        native_revision=row["native_revision"],
        source_closure_sha256=row["source_closure_sha256"],
        paths=[policy._layout_source_path(row)],
    )


def qualified_rows():
    fixture = json.loads(
        (HERE / "fixtures/rushu_vestige_callback_custody.json").read_text()
    )
    return fixture["legacy"], fixture["typed"]


class NativeTypedCustody(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy, cls.rows = qualified_rows()

    def test_native_thirteen_paths_and_existing_hashes(self):
        self.assertEqual({r["spell_reference"] for r in self.rows}, SCHEDULED)
        for row in self.legacy + self.rows:
            with self.subTest(spell=row["spell_reference"]):
                witness, spells = policy.source_closure(record(row))
                self.assertEqual(spells, {row["spell_reference"]})
                self.assertEqual(
                    hashlib.sha256(policy._canonical(witness).encode()).hexdigest(),
                    row["source_closure_sha256"],
                )
                self.assertEqual(
                    policy._qualified(
                        policy._canonical(record(row)), native_catalog.release()
                    ),
                    spells,
                )

    def test_normalized_path_ambiguity_order_and_endpoint_guards(self):
        original = self.rows[0]
        variants = []
        row = deepcopy(original)
        row["source_effect_path"] = [324322]
        variants.append(row)
        row = deepcopy(original)
        row["source_nodes"][2][0] = 4
        variants.append(row)
        row = deepcopy(original)
        row["source_nodes"] = {}
        variants.append(row)
        row = deepcopy(original)
        row["source_nodes"][-1][2] = 7306
        variants.append(row)
        row = deepcopy(original)
        row["source_nodes"] = []
        variants.append(row)
        for row in variants:
            with self.assertRaises(ValueError):
                policy._layout_source_path(row)

    def test_native_area_state_edges_and_area_witness_guard(self):
        original = record(self.rows[0])
        for kind in ("area", "state"):
            changed = deepcopy(original)
            node = next(n for n in changed["paths"][0][1:] if n[0] == kind)
            node[1] += 1
            with self.assertRaises(ValueError):
                policy.source_closure(changed)
        changed = deepcopy(original)
        changed["paths"][0][1][0] = "unknown"
        with self.assertRaises(ValueError):
            policy.source_closure(changed)
        from wakfu_server import combat_effect_area

        areas = deepcopy(combat_effect_area.native_effect_areas())
        area = next(n[1] for n in original["paths"][0] if n[0] == "area")
        areas[str(area)]["entry_masks"] = [9999]
        policy._qualified.cache_clear()
        with patch.object(
            combat_effect_area, "native_effect_areas", return_value=areas
        ):
            with self.assertRaisesRegex(ValueError, "closure changed"):
                policy._qualified(policy._canonical(original), native_catalog.release())
        policy._qualified.cache_clear()

    def test_advice_preserves_native_book_and_unqualified_spells(self):
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.monsters import native_abilities

        constructor = npc_spell_catalog()["activation_policy"]["enabled_monsters"][
            "5306"
        ]
        actor = SimpleNamespace(id=-200, controlled=False, effective_level=230)
        fight = SimpleNamespace(
            current=actor,
            native_encounter_scene_layout=dict(
                policy=self.rows[0]["layout_policy"],
                map_id=1332,
                authority=self.rows[0]["layout_authority"],
                original_world_coordinates=False,
            ),
            native_npc_initialization_receipts={
                -200: dict(
                    initialized=True,
                    ref=5306,
                    descriptor_level=230,
                    raw_triples=constructor["initial_state_triples"],
                )
            },
        )
        monsters = {-200: dict(id=-200, ref=5306)}
        book = {r["spell_id"]: r["spell_level"] for r in native_abilities(5306, 230)}
        before = dict(book)
        with patch.object(
            policy, "_layout_declarations", return_value=tuple(self.legacy + self.rows)
        ):
            advice = policy._layout_deliberate_spells(fight, book, monsters)
        self.assertEqual(book, before)
        self.assertEqual(set(book) - set(advice), SCHEDULED | {7292, 7293, 7294, 7295})
        self.assertTrue({7283, 7285, 7286, 7306} == advice.keys())
        self.assertEqual(
            advice,
            {
                r: l
                for r, l in book.items()
                if r not in SCHEDULED | {7292, 7293, 7294, 7295}
            },
        )


if __name__ == "__main__":
    unittest.main()
