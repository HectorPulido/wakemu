from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_actor_source import registered_source
from wakfu_ai.native.native_oracle import NativeOracle


class RegisteredCreatureSourceTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=901,
            controlled=True,
            effective_level=20,
            team=1,
            position=(2, 3, 4),
            hp=20,
            native_summon_source=dict(
                ref=5525,
                level=20,
                direction=3,
                caster_id=7,
                controller_id=7,
                future=b"complete",
            ),
        )
        self.record = dict(
            actor_id=901,
            caster_id=7,
            controller_id=7,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=5525,
                native_real_level=20,
                native_instance_id=1134,
            ),
        )
        self.fight = SimpleNamespace(
            current=self.actor,
            actors={901: self.actor},
            native_summon_registrations={901: self.record},
        )

    def test_source_keeps_positive_identity_height_and_future_fields(self):
        descriptor = registered_source(self.actor, self.record)
        self.assertEqual(descriptor["id"], 901)
        self.assertEqual((descriptor["x"], descriptor["y"], descriptor["z"]), (2, 3, 4))
        self.assertEqual(descriptor["future"], b"complete")
        self.assertEqual(descriptor["map_id"], 1134)

    def test_controller_kind_does_not_replace_registered_creature_ownership(self):
        oracle = NativeOracle.__new__(NativeOracle)
        oracle.characters, oracle.monsters = {}, {}
        with patch(
            "wakfu_server.monsters.native_abilities",
            return_value=[{"spell_id": 7962, "spell_level": 20}],
        ) as catalogue, patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ):
            self.assertEqual(oracle.owned_spells(self.fight), {7962: 20})
            catalogue.assert_called_once_with(5525, 20)

    def test_corrupted_registration_rejected_before_native_catalogue_access(self):
        mutations = (
            ("actor_id", 902),
            ("caster_id", 8),
            ("controller_id", 8),
            ("authority", dict(self.record["authority"], breed_id=1)),
            ("authority", dict(self.record["authority"], native_real_level=1)),
            ("authority", dict(self.record["authority"], is_player=True)),
        )
        for key, value in mutations:
            record = deepcopy(self.record)
            record[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(
                ValueError, "registered summon"
            ):
                registered_source(self.actor, record)
        self.actor.effective_level = 19
        with self.assertRaisesRegex(ValueError, "registered summon"):
            registered_source(self.actor, self.record)
