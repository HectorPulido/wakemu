"""Paid native owned dialogue and successive contracts on the same actor."""
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import owned_story_npcs as npcs
from wakfu_server.achievements import (
    conversation,
    conversation_turnin,
    mission_toolkit,
    service,
)
import test_owned_story_npcs as fixture


class OwnedStoryExchangeTests(unittest.TestCase):
    def test_native_wool_exchange_keeps_payment_output_and_profile_authority_together(
        self,
    ):
        directory = Path(npcs.__file__).with_name("owned_story_npc_profiles")
        wool = json.loads((directory / "wild-estate-sufokia-715-wool.json").read_text())
        old = json.loads(
            (directory / "wild-estate-sufokia-715-debrief.json").read_text()
        )
        native = fixture.native_dialogue()
        graph, _, terminal, guard = npcs._dialogue_contract(
            wool, wool["npcs"][0], native
        )
        self.assertEqual((terminal, graph[(2331, 5634)]), (2366, 2366))
        self.assertIn("GetItemQuantity(17832)>=10", guard)
        tampered = json.loads(json.dumps(wool))
        tampered["npcs"][0]["item_turn_in"]["quantity"] = 9
        with self.assertRaises(ValueError):
            npcs._dialogue_contract(tampered, tampered["npcs"][0], native)
        current_state = fixture.state(
            running=(1646,), completed=(1679,), objectives=(3055,)
        )
        store = fixture._Store(
            dict(
                id=41,
                account_id=7,
                map_id=715,
                instance_id=(1 << 57) + 47,
                x=0,
                y=-2,
                z=0,
            )
        )
        store.db.version = 2
        with (
            patch.object(npcs, "profiles", return_value=(old, wool)),
            patch.object(
                npcs.owned_story_controller, "recognizes_instance", return_value=True
            ),
            patch.object(
                npcs.owned_story_controller,
                "_scope",
                return_value=(
                    {"id": wool["controller_id"]},
                    {"sufokian-ghosts-defeated", "sufokian-storehouse-discovered"},
                ),
            ),
            patch.object(npcs.owned_story_refresh, "pending", return_value=None),
            patch.object(npcs.storage, "load_locked", return_value=current_state),
        ):
            rows = npcs._rows(store.db, store, store.current)
            self.assertEqual([entry[0]["id"] for entry in rows], [wool["id"]])
            with patch.object(
                npcs.owned_story_controller,
                "_scope",
                return_value=(
                    {"id": wool["controller_id"]},
                    {"sufokian-storehouse-discovered"},
                ),
            ):
                self.assertEqual(
                    [
                        entry[0]["id"]
                        for entry in npcs._rows(store.db, store, store.current)
                    ],
                    [wool["id"]],
                )
        actor = npcs.actor_id(store.current["instance_id"], 1)
        row = dict(
            wool["npcs"][0],
            actor_id=actor,
            map_id=715,
            instance_id=store.current["instance_id"],
            enabled=True,
        )
        selected = [wool]

        def locked(*_args):
            return store.current, selected[0], row, current_state

        definition = dict(
            d=1646, native_class="aJM", aqb=False, cjJ=[dict(d=3055), dict(d=3056)]
        )
        applied = [True]
        failure = [False]

        def settle(
            db,
            domain,
            character,
            session,
            binding,
            original,
            requirement,
            *,
            node_id,
            choice_id,
            speaker_row,
        ):
            conversation.authorize_fact(
                character,
                speaker_row,
                session,
                binding,
                original,
                node_id=node_id,
                choice_id=choice_id,
            )
            self.assertEqual(
                requirement, conversation_turnin.TurnInRequirement(17832, 10)
            )
            if failure[0]:
                raise ValueError("insufficient native payment")
            return dict(applied=applied[0], packets=[])

        with (
            patch.object(npcs, "_locked", side_effect=locked),
            patch.object(npcs.npc_dialogue, "catalog", return_value=native),
            patch.object(npcs, "_criterion", return_value=True),
            patch.object(npcs, "_nearby", return_value=True),
            patch.object(
                mission_toolkit, "definitions", return_value={1646: definition}
            ),
            patch.object(conversation_turnin, "settle", side_effect=settle) as payment,
            patch.object(npcs.storage, "enqueue_reward") as output,
            patch.object(service, "drain_rewards", return_value=[]),
            patch.object(mission_toolkit, "settle") as ordinary,
        ):

            def opened():
                session, _ = npcs.begin(
                    store, 7, "generation", store.current, actor, 440
                )
                npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 2331, 5634),
                )
                self.assertEqual(session.node_id, 2366)
                output.assert_not_called()
                return session

            session = opened()
            failure[0] = True
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 2366, 5740),
                )
            self.assertEqual(session.node_id, 2366)
            output.assert_not_called()
            failure[0] = False
            npcs.choose(
                store,
                7,
                "generation",
                store.current,
                session,
                struct.pack(">ii", 2366, 5740),
            )
            self.assertEqual(output.call_count, 1)
            self.assertEqual(output.call_args.args[-1]["ckl"], [17828, 1])
            ordinary.assert_not_called()
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 2366, 5740),
                )
            self.assertEqual(output.call_count, 1)
            output.reset_mock()
            applied[0] = False
            session = opened()
            npcs.choose(
                store,
                7,
                "generation",
                store.current,
                session,
                struct.pack(">ii", 2366, 5740),
            )
            output.assert_not_called()
            applied[0] = True
            session = opened()
            current_state["objectives"] = []
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 2366, 5740),
                )
            output.assert_not_called()
            current_state["objectives"] = [3055]
            selected[0] = old
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "generation",
                    store.current,
                    session,
                    struct.pack(">ii", 2366, 5740),
                )
            output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
