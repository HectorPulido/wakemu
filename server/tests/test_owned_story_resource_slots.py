"""Representative source, ownership and reward boundaries for story harvesting."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock

from wakfu_server import owned_story_resource_slots as owned
from wakfu_server import owned_story_mechanics, quest_resource_slots as slots
from wakfu_server import owned_story_item_gates

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryResourceTests(TestCase):
    def setUp(self):
        self.selected = json.loads((ROOT / "wild-estate-brak-723.v2.json").read_text())
        self.native = json.loads(
            (ROOT / "wild-estate-brak-723.native.v2.json").read_text()
        )
        self.geometry = json.loads(
            (ROOT / "wild-estate-brak-723.exploration.json").read_text()
        )
        self.owner = dict(id=91, instance_id=1001, map_id=723)
        self.source = patch.object(owned.mechanics, "sources", return_value=self.native)
        self.source.start()
        self.addCleanup(self.source.stop)

    def profile(self):
        result = owned._template(self.selected)
        result["owned_story"] = dict(
            controller_id=self.selected["id"],
            owner_id=91,
            instance_id=1001,
            native_sources_sha256=self.selected["native_sources"]["sha256"],
        )
        return result

    def test_original_getter_products_and_native_floor_are_required(self):
        profile = self.profile()
        definitions = {
            1677: dict(native_class="aJM", d=1677, aqb=False, cjJ=[dict(d=3105)])
        }
        self.assertEqual(
            len(slots.validate(profile, definitions, self.geometry)["placements"]), 6
        )
        changed = deepcopy(profile)
        changed["resource_actions"][0]["native_loot"]["table_id"] = 2352
        with self.assertRaisesRegex(ValueError, "original getter"):
            slots.validate(changed, definitions, self.geometry)
        self.native["harvest_getter_proofs"]["1343"]["loot_table"] = 2352
        with self.assertRaisesRegex(ValueError, "original native loot getter"):
            owned._template(self.selected)

    def test_dynamic_uids_do_not_escape_original_owner_and_template(self):
        profile = self.profile()
        profile["placements"][0]["resource_uid"] = 999
        with patch.object(
            owned.controller, "_scope", return_value=(self.selected, set())
        ):
            owned.authorize(None, None, self.owner, profile)
            with self.assertRaisesRegex(ValueError, "original private story owner"):
                owned.authorize(None, None, dict(self.owner, id=92), profile)
            profile["placements"][0]["position"][0] += 1
            with self.assertRaisesRegex(ValueError, "changed after source publication"):
                owned.authorize(None, None, self.owner, profile)

    def test_productless_consumers_remain_inert_and_real_draw_is_delivered(self):
        self.assertIsNone(slots.products(None, None, 1, 2, {}, {}))
        authorization = dict(
            native_loot={"table_id": 2355},
            loot_tables=self.native["resource_slots"]["loot_tables"],
            native_action_id=1343,
            resource_uid=1,
            occupation_token="owned-occupation",
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"secret": b"x" * 32}
        from wakfu_server import item_action_delivery

        with patch.object(
            item_action_delivery,
            "grant_outputs",
            return_value={"packets": [], "character": self.owner},
        ) as delivery, patch.object(
            owned_story_mechanics, "allowed", return_value=True
        ), patch(
            "wakfu_server.random_item_actions.PrivateDraw.randbelow", return_value=0
        ):
            result = slots.products("store", db, 1, 2, self.owner, authorization)
            self.assertEqual(result["products"], {17820: 1})
            delivery.assert_called_once_with("store", db, 1, 2, self.owner, {17820: 1})

    def test_original_merge_output_can_qualify_a_workshop_gate(self):
        effect = dict(
            kind="native_item_gate", reference=17821, quantity=1, consume=True
        )
        owned_story_item_gates.validate(self.selected, effect, self.native)
        changed = deepcopy(self.selected)
        changed["item_gates"][1]["source_reference"] = 17820
        with self.assertRaisesRegex(ValueError, "no frozen original"):
            owned_story_item_gates.validate(changed, effect, self.native)

    def test_retry_after_capacity_failure_reuses_the_same_private_draw(self):
        from wakfu_server import item_action_delivery

        authorization = dict(
            native_loot={"table_id": 2355},
            loot_tables=self.native["resource_slots"]["loot_tables"],
            native_action_id=1343,
            resource_uid=1,
            occupation_token="same-owned-occupation",
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"secret": b"x" * 32}
        with patch.object(
            item_action_delivery,
            "grant_outputs",
            side_effect=[
                ValueError("capacity"),
                {"packets": [], "character": self.owner},
            ],
        ) as grant, patch.object(owned_story_mechanics, "allowed", return_value=True):
            with self.assertRaisesRegex(ValueError, "capacity"):
                slots.products("store", db, 1, 2, self.owner, authorization)
            slots.products("store", db, 1, 2, self.owner, authorization)
            self.assertEqual(
                grant.call_args_list[0].args[-1], grant.call_args_list[1].args[-1]
            )
