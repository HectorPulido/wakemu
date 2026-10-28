"""A same-connection hero swap republishes its actual pinned dungeon context."""
import ast
from contextlib import contextmanager
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_context, hero_wire, heroes, inventory_move
from wakfu_server.combat_instance_publication import (
    InstancePublicationTracker,
    refresh_owned_encounter,
    require_current_publication,
)
from wakfu_server.maps.proto_dungeon import encode


class HeroSwitchInstancePublicationTests(unittest.TestCase):
    def test_actual_swap_completion_republishes_before_join_and_restores_admission(
        self,
    ):
        for private, fighting, fail_write in (
            (True, False, False),
            (True, True, False),
            (False, False, False),
            (True, False, True),
        ):
            with self.subTest(
                private=private, fighting=fighting, fail_write=fail_write
            ):
                self._run_swap(private, fighting, fail_write)

    def _run_swap(self, private, fighting, fail_write):
        instance = 144115188075855918 if private else 0
        before = dict(
            id=64,
            account_id=11,
            level=59,
            breed=16,
            map_id=1091,
            instance_id=instance,
            x=0,
            y=-9,
            z=0,
        )
        after = dict(before, id=25, breed=2)
        context = dict(difficulty_level=2, is_fight_in_progress=fighting)
        tracker = InstancePublicationTracker()
        events, packets = [], []
        scope = lambda actor: (11, "actual-lease", actor["id"], 1091, instance)

        def frame(opcode, body):
            return struct.pack(">IH", 6 + len(body), opcode) + body

        bootstrap = b"".join(
            struct.pack(">H", len(value)) + value
            for value in (b"entity", b"", b"\0\0", encode(context))
        )
        tracker.after_write(frame(13974, bootstrap), scope(before))
        original = tracker.lease.current
        self.assertIsNotNone(original)

        class Positions:
            @contextmanager
            def account_barrier(self, account):
                yield

            def attach(self, *args):
                pass

        class Store:
            @contextmanager
            def connection(self):
                owner = self

                class Query:
                    def execute(self, statement, parameters):
                        events.append(("fighting-query", statement, parameters))
                        return SimpleNamespace(fetchone=lambda: {"fighting": fighting})

                yield Query()

            def current_character_session(self, account, generation, identity):
                return (account, generation, identity) == (11, "actual-lease", 25)

        ns = dict(
            loaded=True,
            hero_switch_pending=None,
            character=before,
            account_id=11,
            generation="actual-lease",
            connection=object(),
            service="world",
            fight=None,
            combat_session=None,
            bag_session=None,
            ranch_session=None,
            chest_opening=None,
            npc_dialogue_session=None,
            active_private_session=lambda: None,
            PLANTINGS=SimpleNamespace(cancel=lambda *args: None),
            HARVESTS=SimpleNamespace(cancel=lambda *args, **kwargs: None),
            cancel_flora=lambda: None,
            cancel_crafting=lambda: None,
            flush_positions=lambda **kwargs: None,
            STORE=Store(),
            POSITIONS=Positions(),
            WORLD=SimpleNamespace(leave=lambda *args: None),
            Movement=lambda value: value,
            OWNED_HERO_TEMPLATE=b"template",
            wire=SimpleNamespace(adapt=lambda *args: b"guild"),
            fixture=lambda opcode: b"fixture",
            rich_inventory_packet=lambda actor: (13220, b"inventory"),
            publish_custom_task_cards=lambda: None,
            deliver_custom_task_rewards=lambda: None,
            record=lambda **data: events.append(("record", data)),
            is_dungeon_run=lambda identity: private and identity == instance,
        )

        def send(connection, service, opcode, payload):
            if fail_write and opcode == 13339:
                tracker.invalidate()
                raise OSError("Actual native context socket write failed")
            tracker.after_write(frame(opcode, payload), scope(ns["character"]))
            events.append(("sent", opcode))
            packets.append((opcode, payload))

        def join(*args, **kwargs):
            events.append(("join", tracker.lease.current))
            if private:
                other = InstancePublicationTracker()
                other_scope = (10, "other-live-lease", 67, 1091, instance)
                other.after_write(frame(13974, bootstrap), other_scope)
                fight = SimpleNamespace(
                    actors={
                        67: SimpleNamespace(id=67, controlled=True, owner_id=10),
                        -100: SimpleNamespace(id=-100, controlled=False, owner_id=None),
                    }
                )
                self.assertTrue(
                    other.bind_encounter(
                        fight, other_scope, npc_ids=(-100,), player_id=67
                    )
                )
                fight.actors[25] = SimpleNamespace(id=25, controlled=True, owner_id=11)
                try:
                    refresh_owned_encounter(fight, publication=(tracker, scope(after)))
                except ValueError as error:
                    self.fail(str(error))
                require_current_publication(fight)
                self.assertIsNotNone(tracker.lease.current)
                self.assertEqual(tracker.published.session_actor_id, 25)

        ns.update(send=send, join_world=join)
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branches = {
            opcode: next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == f"opcode == {opcode} and loaded"
            )
            for opcode in (12006, 12054)
        }

        def dispatch(opcode, identity):
            ns.update(opcode=opcode, body=struct.pack(">q", identity))
            loop = ast.For(
                target=ast.Name("_once", ast.Store()),
                iter=ast.Tuple([ast.Constant(0)], ast.Load()),
                body=[branches[opcode]],
                orelse=[],
            )
            module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
            exec(compile(module, str(source), "exec"), ns)

        with patch.object(
            heroes, "switch_main", return_value={"leader": after}
        ), patch.object(
            hero_wire, "refresh", return_value=(13046, b"components")
        ), patch.object(
            hero_wire, "statistics", return_value=(13046, b"statistics")
        ), patch.object(
            inventory_move, "synchronization", return_value=(13221, b"sync")
        ), patch.object(
            dungeon_context, "for_instance", return_value=context
        ) as produce:
            dispatch(12006, 25)
            self.assertEqual(ns["character"]["id"], 25)
            self.assertIsNone(tracker.lease.current)
            self.assertIsNone(tracker.published)
            self.assertEqual(ns["hero_switch_pending"], 25)
            if fail_write:
                with self.assertRaisesRegex(OSError, "socket write failed"):
                    dispatch(12054, 25)
                self.assertIsNone(tracker.lease.current)
                self.assertFalse(any(event[0] == "join" for event in events))
                return
            dispatch(12054, 25)
            self.assertIsNone(ns["hero_switch_pending"])
            if not private:
                produce.assert_not_called()
                self.assertNotIn(13339, [opcode for opcode, _ in packets])
                return
            produce.assert_called_once_with(
                ns["STORE"], instance, fight_in_progress=fighting
            )
        receipt = tracker.lease.current
        self.assertNotEqual(receipt, original)
        self.assertEqual(receipt[1], scope(after))
        self.assertGreater(receipt[2], original[2])
        publication = next(
            i for i, event in enumerate(events) if event == ("sent", 13339)
        )
        joined = next(i for i, event in enumerate(events) if event[0] == "join")
        self.assertLess(publication, joined)
        other = InstancePublicationTracker()
        other_scope = (10, "other-live-lease", 67, 1091, instance)
        other.after_write(frame(13974, bootstrap), other_scope)
        fight = SimpleNamespace(
            actors={
                67: SimpleNamespace(id=67, controlled=True, owner_id=10),
                -100: SimpleNamespace(id=-100, controlled=False, owner_id=None),
            }
        )
        self.assertTrue(
            other.bind_encounter(fight, other_scope, npc_ids=(-100,), player_id=67)
        )
        fight.actors[25] = SimpleNamespace(id=25, controlled=True, owner_id=11)
        self.assertTrue(
            refresh_owned_encounter(fight, publication=(tracker, scope(after)))
        )
        require_current_publication(fight)
        self.assertEqual(fight.native_instance_difficulty_snapshots[-100].difficulty, 2)


if __name__ == "__main__":
    unittest.main()
