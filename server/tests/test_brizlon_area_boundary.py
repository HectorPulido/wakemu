"""Source/turn guards for the scoped reconstructed1173 end producer."""
from copy import deepcopy
from types import SimpleNamespace as N
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_brizlon_area_boundary import deliver_brizlon_area_turn_end


class BrizlonAreaBoundaryTests(unittest.TestCase):
    def fixture(self, reference=4251):
        player = N(id=7, controlled=True, hp=100, position=(0, 0, 0), physical_radius=0)
        owner = N(id=-7, hp=100)
        creator = 189472 if reference == 4251 else 197885
        row = dict(
            uid=10,
            reference=1173,
            owner_id=-7,
            effect_uid=20,
            native_area_contract="faY",
            effect_class=315,
            effect_reference=creator,
            executing=False,
            remaining_activations=-1,
            native_cells_xy=((0, 0),),
        )
        fight = N(
            current=player,
            phase="active",
            turn_id=3,
            actors={7: player, -7: owner},
            native_effect_areas={10: row},
            native_turn_event_deliveries={
                "3:7:end": dict(
                    actor_id=7, turn_id=3, event_id=1002, phase="end", suppressed=False
                )
            },
            native_npc_initialization_receipts={
                -7: dict(ref=reference, initialized=True)
            },
            native_owned_area_effects={
                20: dict(
                    uid=20, area_uid=10, effect_class=315, caster_id=-7, executed=True
                )
            },
        )
        callbacks = N(
            _definition=Mock(
                return_value=dict(
                    type="GLYPH", entry_masks=[10016], effect_ids=[189484, 189460]
                )
            ),
            _deliver_event=Mock(return_value=("actual-consumer-result",)),
        )
        dispatcher = N(native_retention=N(fight=fight), native_area_events=callbacks)
        return dispatcher, fight, row, callbacks

    def invoke(self, dispatcher):
        with patch(
            "wakfu_server.combat_area_authority.area_guards",
            return_value=dict(baG=False, baK=False, baF=True),
        ):
            return deliver_brizlon_area_turn_end(dispatcher, actor_id=7)

    def test_exact_owned_sources_select_original_consumer_without_changing_area(self):
        for reference in (4251, 4280):
            with self.subTest(reference=reference):
                dispatcher, fight, row, callbacks = self.fixture(reference)
                original = deepcopy(row)
                self.assertEqual(self.invoke(dispatcher), ("actual-consumer-result",))
                self.assertEqual(row, original)
                self.assertEqual(
                    callbacks._deliver_event.call_args.args,
                    (row, callbacks._definition.return_value, fight.current, 10016),
                )

    def test_wrong_owner_creator_and_unexecuted_runner_never_deliver(self):
        mutations = (
            lambda f, r: r.update(
                effect_reference=189472
                if f.native_npc_initialization_receipts[-7]["ref"] == 4280
                else 197885
            ),
            lambda f, r: f.native_npc_initialization_receipts[-7].update(
                initialized=False
            ),
            lambda f, r: f.native_owned_area_effects[20].update(caster_id=-8),
            lambda f, r: f.native_owned_area_effects[20].update(area_uid=99),
            lambda f, r: f.native_owned_area_effects[20].update(executed=False),
            lambda f, r: f.native_npc_initialization_receipts[-7].update(ref=1),
        )
        for reference in (4251, 4280):
            for index, mutate in enumerate(mutations):
                with self.subTest(reference=reference, mutation=index):
                    dispatcher, fight, row, callbacks = self.fixture(reference)
                    mutate(fight, row)
                    self.assertEqual(self.invoke(dispatcher), ())
                    callbacks._deliver_event.assert_not_called()

    def test_only_alive_controlled_current_player_on_live_area_can_trigger(self):
        mutations = (
            lambda f, r: setattr(f.current, "controlled", False),
            lambda f, r: setattr(f.current, "hp", 0),
            lambda f, r: setattr(f.current, "position", (1, 0, 0)),
            lambda f, r: setattr(f, "phase", "finished"),
            lambda f, r: r.update(remaining_activations=0),
            lambda f, r: r.update(executing=True),
            lambda f, r: f.native_turn_event_deliveries["3:7:end"].update(
                suppressed=True
            ),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                dispatcher, fight, row, callbacks = self.fixture()
                mutate(fight, row)
                self.assertEqual(self.invoke(dispatcher), ())
                callbacks._deliver_event.assert_not_called()

    def test_missing_actual_end_stamp_and_modified_native_consumer_fail_closed(self):
        dispatcher, fight, row, callbacks = self.fixture()
        fight.native_turn_event_deliveries = {}
        with self.assertRaisesRegex(ValueError, "actual owned player end"):
            self.invoke(dispatcher)
        callbacks._deliver_event.assert_not_called()
        dispatcher, fight, row, callbacks = self.fixture()
        callbacks._definition.return_value["entry_masks"] = [10000]
        with self.assertRaisesRegex(ValueError, "original native consumer"):
            self.invoke(dispatcher)
        callbacks._deliver_event.assert_not_called()

    def test_duplicate_native_end_rejection_cannot_reach_added_producer(self):
        from wakfu_server.combat_turn_events import deliver_turn_end

        dispatcher, fight, row, callbacks = self.fixture()
        with patch(
            "wakfu_server.combat_turn_events._deliver",
            side_effect=ValueError("Owned turn boundary already delivered"),
        ):
            with self.assertRaisesRegex(ValueError, "already delivered"):
                deliver_turn_end(dispatcher, actor_id=7)
        callbacks._deliver_event.assert_not_called()
