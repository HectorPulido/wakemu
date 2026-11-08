"""Native World ownership removes redundant copies, never shared rollback."""
from copy import deepcopy
from random import Random
import struct
import sys
import unittest
from unittest.mock import patch

from test_combat_spell_transaction import SpellTransactionTests
from test_combat_weapon import weapon_fixture, equipped
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Fight
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_weapon import prepare_server_weapon
from wakfu_server import combat_server_spell
from wakfu_server.combat_owned_native_spell_entry import (
    owned_native_spell_entry,
    owns_entry_commit,
)
from wakfu_server.combat_owned_spell_delivery import owned_spell_delivery
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID
from wakfu_server.spells import encode_deck


class OwnedNativeSpellEntryTests(unittest.TestCase):
    def fixture(self, kind):
        if kind == "spell":
            char, monster, fight = SpellTransactionTests().native_server_fixture(
                11, 6, native_qi=True, target_distance=2
            )
            body = struct.pack(
                ">qqiih", 7, (7 << 32) | 5043, *fight.actors[-7].position
            )
            deck = encode_deck([5043])
            producer = prepare_server_spell
        else:
            char, monster, fight = weapon_fixture(11, 200)
            char = equipped(char, 2027)
            body = struct.pack(">qqbiih", 7, 1000, 15, *fight.actors[-7].position)
            deck = encode_deck((), ())
            producer = prepare_server_weapon
        return char, monster, fight, body, deck, producer

    def state(self, shared):
        runtime = shared.runtime
        return (
            source_snapshot(shared.fight),
            shared.sequence,
            deepcopy(vars(shared.ack)),
            runtime.action_id,
            runtime.native_action_id,
            runtime.awaiting_ack,
            tuple(runtime.pending),
            runtime.last_native_delivery,
            {
                key: tuple((b.sequence, b.packets) for b in batches)
                for key, batches in shared.outboxes.items()
            },
        )

    def run_case(self, kind, enabled, *, failure=False, custom=False):
        char, monster, fight, body, deck, producer = self.fixture(kind)
        runtime = RuntimeMessages(fight)
        if failure:
            runtime.native_action_id = MAX_NATIVE_ACTION_ID
        session = Session(3, 7, "owned-entry", 1134, 0)
        registry = Registry(lambda value: value == session)
        shared = registry.register(fight, session, runtime=runtime)
        original = self.state(shared)
        escaped = {}
        serialize = lambda actor, state: struct.pack(
            ">qii", actor.id, actor.hp, actor.ap
        )

        def operation(candidate, private_runtime):
            with owned_native_spell_entry(
                private_runtime, producer, stats_serializer=serialize, enabled=enabled
            ):
                transaction = producer(
                    body,
                    char,
                    {-7: monster},
                    candidate,
                    3,
                    deck,
                    action_id=private_runtime.action_id + 1,
                    line_of_sight=lambda *a: True,
                    critical=False,
                    rng=Random(1),
                )
                escaped.update(
                    transaction=transaction,
                    runtime=private_runtime,
                    in_place=transaction.fight is candidate,
                )
                with owned_spell_delivery(private_runtime, transaction):
                    packets = commit_spell_transaction(
                        private_runtime, transaction, stats_serializer=serialize
                    )
                return Transition(transaction.fight, private_runtime, packets)

        counts = [0, 0]
        codes = (Fight.__deepcopy__.__code__, source_snapshot.__code__)

        def profile(frame, event, arg):
            if event == "call":
                for i, code in enumerate(codes):
                    if frame.f_code is code:
                        counts[i] += 1

        native_factory = combat_server_spell.server_runtime
        from contextlib import nullcontext

        gate = (
            patch.object(
                combat_server_spell, "server_runtime", side_effect=native_factory
            )
            if custom
            else nullcontext()
        )
        with gate:
            sys.setprofile(profile)
            try:
                if failure:
                    with self.assertRaises(ValueError):
                        registry.execute(fight.id, session, 7, operation)
                else:
                    registry.execute(fight.id, session, 7, operation)
            finally:
                sys.setprofile(None)
        self.assertFalse(
            owns_entry_commit(escaped["runtime"], escaped["transaction"], serialize)
        )
        if failure:
            self.assertEqual(self.state(shared), original)
            self.assertIs(shared.fight, fight)
            self.assertIs(shared.runtime, runtime)
        else:
            self.assertEqual(source_snapshot(fight), original[0])
            self.assertIs(shared.runtime.fight, shared.fight)
        return self.state(shared), counts, escaped

    def test_native_spell_weapon_equivalence_locality_rollback_and_custom_fallback(
        self,
    ):
        for kind in ("spell", "weapon"):
            baseline, old, old_alias = self.run_case(kind, False)
            current, new, new_alias = self.run_case(kind, True)
            self.assertEqual(baseline, current)
            self.assertFalse(old_alias["in_place"])
            self.assertTrue(new_alias["in_place"])
            self.assertEqual(old[0], new[0] + 1)
            self.assertEqual(old[1], new[1] + 3)
        self.run_case("spell", True, failure=True)
        baseline, _, _ = self.run_case("spell", False)
        fallback, _, aliases = self.run_case("spell", True, custom=True)
        self.assertEqual(baseline, fallback)
        self.assertFalse(aliases["in_place"])

    def test_expired_scope_releases_callback_runtime_and_legacy_payment_read_order(
        self,
    ):
        import ast
        from pathlib import Path
        from types import SimpleNamespace
        import weakref
        from wakfu_server import combat_weapon
        from wakfu_server.combat_owned_native_spell_entry import (
            registry_private_spell_pair,
            _ENTRY,
        )
        from wakfu_server.combat_spell_transaction import SpellTransaction

        # No game execution needed: exercise the real issuer/scope lifetime.
        fight = Fight.__new__(Fight)
        runtime = RuntimeMessages(fight)
        serialize = lambda actor, state: b""
        runtime_ref, serializer_ref = weakref.ref(runtime), weakref.ref(serialize)
        with registry_private_spell_pair(fight, runtime):
            with owned_native_spell_entry(
                runtime, prepare_server_weapon, stats_serializer=serialize
            ):
                marker = _ENTRY.get()[0]
                transaction = SpellTransaction(fight, {}, 0, (), (), (), marker, 1)
                self.assertIs(marker.runtime, runtime)
        self.assertFalse(owns_entry_commit(runtime, transaction, serialize))
        self.assertTrue(
            all(
                getattr(marker, name) is None
                for name in ("pair", "fight", "runtime", "serializer")
            )
        )
        del runtime, serialize
        self.assertIsNone(runtime_ref())
        self.assertIsNone(serializer_ref())
        self.assertIs(transaction.source_state, marker)

        tree = ast.parse(Path(combat_weapon.__file__).read_text())
        function = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "prepare_server_weapon"
        )
        capture = next(
            n
            for n in function.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "source_wp" for t in n.targets)
        )
        payment = next(
            n
            for n in function.body
            if isinstance(n, ast.Expr)
            and ast.unparse(n).startswith("caster.effect_stats.update(")
        )

        def code(node):
            return compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                combat_weapon.__file__,
                "exec",
            )

        for owned in (None, object()):
            reads = []
            state = {"phase": "capture", "wp": 6}

            class Stats(dict):
                def __getitem__(self, key):
                    reads.append((state["phase"], key))
                    return state["wp"]

            caster = SimpleNamespace(ap=4, mp=3, effect_stats={})
            env = dict(owned=owned, stats=Stats(), caster=caster, costs={"wp": 1})
            exec(code(capture), env)
            self.assertEqual(reads, [] if owned is None else [("capture", 4)])
            state.update(phase="payment", wp=8)
            exec(code(payment), env)
            self.assertEqual(
                reads, [("payment", 4)] if owned is None else [("capture", 4)]
            )
            self.assertEqual(caster.effect_stats[4], 7 if owned is None else 5)
