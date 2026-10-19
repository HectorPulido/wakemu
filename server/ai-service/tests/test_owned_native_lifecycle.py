"""Focused qualifications for private owned providers on staged native turns."""
from copy import deepcopy
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

_ROOT = Path(__file__).resolve().parents[3]
for _path in (
    str(_ROOT / "server"),
    str(_ROOT / "server" / "ai-service"),
    str(_ROOT / "server" / "ai-service" / "tests"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_ai.native.native_stats import NativeStats
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory


@contextmanager
def temporary_server_modules(modules):
    """Supply fake native boundaries without leaking package attributes."""
    import wakfu_server

    missing = object()
    names = {name.rsplit(".", 1)[-1] for name in modules}
    previous = {name: getattr(wakfu_server, name, missing) for name in names}
    try:
        with patch.dict(sys.modules, modules):
            yield
    finally:
        for name, value in previous.items():
            if value is missing:
                if hasattr(wakfu_server, name):
                    delattr(wakfu_server, name)
            else:
                setattr(wakfu_server, name, value)


def authority_fixture():
    characters = {
        10: {
            "id": 10,
            "account_id": 1,
            "map_id": 1134,
            "breed": 1,
            "level": 40,
            "nested": {"build": [1, 2], "future": b"character"},
        },
        20: {
            "id": 20,
            "account_id": 2,
            "map_id": 1134,
            "breed": 2,
            "level": 41,
            "nested": {"build": [3, 4], "future": b"other"},
        },
    }
    monsters = {
        -200: {
            "id": -200,
            "ref": 5525,
            "level": 1,
            "nested": {"states": [183304, 183305], "future": b"monster"},
        }
    }
    decks = {10: b"deck-one", 20: b"deck-two"}
    return characters, monsters, decks


class FakeFight:
    def __init__(self):
        self.id = 81
        self.phase = "active"
        self.turn_id = 9
        self.turn_index = 0
        self.order = [-200, 10]
        self.actors = {
            10: SimpleNamespace(
                id=10,
                team=0,
                controlled=True,
                position=(0, 0, 0),
                hp=60,
                ap=6,
                mp=3,
                effect_stats={4: 6},
                effect_maxima={4: 6},
            ),
            -200: SimpleNamespace(
                id=-200,
                team=1,
                controlled=False,
                position=(2, 0, 0),
                hp=20,
                ap=4,
                mp=2,
                effect_stats={4: 1},
                effect_maxima={4: 1},
            ),
        }

    @property
    def current(self):
        return self.actors[self.order[self.turn_index]]


class FakeRegistry:
    def __init__(self, shared, sessions):
        self.shared = shared
        self.sessions = sessions

    def lookup(self, fight_id):
        if fight_id != self.shared.fight.id:
            raise AssertionError("Unexpected shared fight lookup")
        return self.shared

    def _member(self, shared, session):
        if shared is not self.shared or session not in self.sessions:
            raise AssertionError("Unexpected shared session")


def shared_fixture(runtime):
    fight = FakeFight()
    runtime.fight = fight
    runtime.awaiting_ack = None
    runtime.pending = []
    session = SimpleNamespace(account_id=1, character_id=10, generation="first")
    other_session = SimpleNamespace(account_id=2, character_id=20, generation="second")
    shared = SimpleNamespace(
        fight=fight,
        runtime=runtime,
        sequence=0,
        lock=threading.RLock(),
        participants={1: session, 2: other_session},
        connected={1, 2},
        outboxes={1: [], 2: []},
    )
    adapter = SimpleNamespace(registry=FakeRegistry(shared, (session, other_session)))
    return shared, adapter, session


class OwnedNativeLifecycleTests(unittest.TestCase):
    def test_factory_isolates_complete_inputs_and_preserves_native_boundary_arguments(
        self,
    ):
        characters, monsters, decks = authority_fixture()
        source_snapshot = deepcopy((characters, monsters, decks))
        provider = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=10,
            fight_start=True,
            area_callbacks=True,
        )
        characters[10]["nested"]["build"].append(99)
        characters[20]["new"] = "caller mutation"
        monsters[-200]["nested"]["states"].clear()
        decks[10] = b"mutated deck"
        self.assertEqual(
            (provider.characters, provider.monsters, provider.decks), source_snapshot
        )

        preview = SimpleNamespace(actors={20: object()})
        started = (object(), ((1001, b"start"),))
        native_module = ModuleType("wakfu_server.combat_server_spell")
        native_module.prepare_server_turn_start = Mock(return_value=started)
        native_module.prepare_server_turn_end = Mock()
        native_module.server_runtime = Mock()
        with temporary_server_modules(
            {"wakfu_server.combat_server_spell": native_module}
        ):
            self.assertIs(
                provider.turn_start(preview, actor_id=20, action_id=71), started
            )
        prepare_start = native_module.prepare_server_turn_start
        self.assertEqual(
            prepare_start.call_args.args[:3],
            (provider.characters[20], provider.monsters, preview),
        )
        self.assertEqual(prepare_start.call_args.args[3], provider.decks[20])
        self.assertEqual(
            prepare_start.call_args.kwargs,
            {
                "native_events": True,
                "area_callbacks": True,
                "player_characters": provider.characters,
                "deck_blobs": provider.decks,
                "actor_id": 20,
                "action_id": 71,
            },
        )

        ended = (object(), ((1002, b"end"),))
        native_module.prepare_server_turn_end.return_value = ended
        with temporary_server_modules(
            {"wakfu_server.combat_server_spell": native_module}
        ):
            self.assertIs(provider.turn_end(preview, actor_id=20, action_id=72), ended)
        prepare_end = native_module.prepare_server_turn_end
        self.assertEqual(
            prepare_end.call_args.args[:4],
            (provider.characters[20], provider.monsters, preview, provider.decks[20]),
        )
        self.assertEqual(
            prepare_end.call_args.kwargs,
            {
                "actor_id": 20,
                "action_id": 72,
                "player_characters": provider.characters,
                "deck_blobs": provider.decks,
            },
        )

        runtime_factory = object()
        native_module.server_runtime.return_value = (runtime_factory, object())
        with temporary_server_modules(
            {"wakfu_server.combat_server_spell": native_module}
        ):
            self.assertIs(provider(action_id=73), runtime_factory)
        server_runtime = native_module.server_runtime
        self.assertEqual(
            server_runtime.call_args.args,
            (provider.characters[10], provider.monsters, provider.decks[10]),
        )
        self.assertEqual(
            server_runtime.call_args.kwargs,
            {
                "action_id": 73,
                "critical": False,
                "player_characters": provider.characters,
                "deck_blobs": provider.decks,
            },
        )

    def test_binding_replaces_only_private_runtime_with_full_owned_sources(self):
        characters, monsters, decks = authority_fixture()
        original_provider = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=10,
            fight_start=False,
        )
        socket_calls = []

        def poisoned(*_args, **_kwargs):
            socket_calls.append("called")
            raise AssertionError("shared socket-bound serializer was invoked")

        fight = SimpleNamespace(
            id=81,
            native_summon_registrations={
                900: {"reference": 5528, "level": 1, "uid": 991}
            },
            future_fight_authority={"nested": [b"preserve", 17]},
        )
        original_runtime = SimpleNamespace(
            fight=fight,
            expiration_runtime_factory=original_provider,
            turn_start_provider=original_provider.turn_start,
            turn_end_provider=original_provider.turn_end,
            stats_serializer=poisoned,
            runtime_stats_serializer=poisoned,
            awaiting_ack=None,
            pending=[],
            future_runtime_authority={"sequence": [1, 2, 3]},
        )
        original_start = original_runtime.turn_start_provider
        original_end = original_runtime.turn_end_provider
        original_snapshot = deepcopy(
            (
                original_provider.characters,
                original_provider.monsters,
                original_provider.decks,
                fight.native_summon_registrations,
                fight.future_fight_authority,
                original_runtime.future_runtime_authority,
            )
        )
        private_runtime = deepcopy(original_runtime)
        private_fight = private_runtime.fight
        session = SimpleNamespace(account_id=1, character_id=10)

        bind_private_sources(private_runtime, session)

        private_provider = private_runtime.expiration_runtime_factory
        self.assertIsInstance(private_provider, OwnedExpirationFactory)
        self.assertIsNot(private_provider, original_provider)
        self.assertIsNot(private_provider.characters, original_provider.characters)
        self.assertIsNot(private_provider.monsters, original_provider.monsters)
        self.assertIsNot(private_provider.decks, original_provider.decks)
        self.assertIs(private_runtime.turn_start_provider.__self__, private_provider)
        self.assertIs(private_runtime.turn_end_provider.__self__, private_provider)
        self.assertIsInstance(private_runtime.stats_serializer, NativeStats)
        self.assertIs(
            private_runtime.runtime_stats_serializer, private_runtime.stats_serializer
        )
        self.assertEqual(private_runtime.stats_serializer.fight_id, private_fight.id)
        self.assertEqual(
            private_runtime.stats_serializer.map_id, characters[10]["map_id"]
        )
        self.assertEqual(
            private_runtime.stats_serializer.registrations,
            private_fight.native_summon_registrations,
        )
        private_fight.native_summon_registrations[900]["uid"] = -1
        private_provider.characters[10]["nested"]["build"].append(55)
        private_provider.monsters[-200]["nested"]["states"].append(999)
        private_provider.decks[10] = b"private mutation"
        self.assertEqual(fight.native_summon_registrations[900]["uid"], 991)
        self.assertEqual(
            (
                original_provider.characters,
                original_provider.monsters,
                original_provider.decks,
                fight.native_summon_registrations,
                fight.future_fight_authority,
                original_runtime.future_runtime_authority,
            ),
            original_snapshot,
        )
        self.assertIs(original_runtime.expiration_runtime_factory, original_provider)
        self.assertIs(original_runtime.turn_start_provider, original_start)
        self.assertIs(original_runtime.turn_end_provider, original_end)
        self.assertIs(original_runtime.stats_serializer, poisoned)
        self.assertIs(original_runtime.runtime_stats_serializer, poisoned)
        self.assertEqual(socket_calls, [])

    def test_ready_transition_installs_owned_factory_after_all_owners_are_known(self):
        characters, monsters, decks = authority_fixture()
        actors = {
            identity: SimpleNamespace(
                id=identity,
                owner_id=identity,
                controlled=True,
                effect_stats={4: 6},
                effect_maxima={4: 6},
            )
            for identity in characters
        }
        fight = SimpleNamespace(id=81, order=[10, 20], actors=actors)
        initialize_calls = []
        stats_calls = []
        ready_args = {}

        def prepare_initialize(source, roster, preview, owner_id, deck_blob, **kwargs):
            initialize_calls.append(
                (source, roster, preview, owner_id, deck_blob, kwargs)
            )
            return preview, ((1000, str(owner_id).encode()),)

        def actual_stats(source, actor, fight_id, **kwargs):
            stats_calls.append((source, actor, fight_id, kwargs))
            return {"owner": source["id"], "fight": fight_id}

        def prepare_ready_stub(candidate, owner_id, ready, **kwargs):
            ready_args.update(kwargs)
            for actor in candidate.actors.values():
                kwargs["runtime_stats_serializer"](actor, candidate)
            preview, initial_packets = kwargs["initialize"](candidate, 77)
            ready_args["initial_packets"] = initial_packets
            return preview, None, ((2000, b"ready"),)

        shared_module = ModuleType("wakfu_server.combat_shared")
        shared_module.Registry = object
        shared_module.Session = object

        class Transition:
            def __init__(self, candidate, runtime, packets):
                self.fight, self.runtime, self.packets = candidate, runtime, packets

        shared_module.Transition = Transition
        fight_store = ModuleType("wakfu_server.fight_store")
        fight_store.join_participant = lambda *args, **kwargs: None
        actor_module = ModuleType("wakfu_server.combat_actor")
        actor_module.actor_effects = lambda: {}
        actor_module.actual_actor_stats = actual_stats
        actor_module.actual_monster_actor_stats = actual_stats
        ready_module = ModuleType("wakfu_server.combat_ready")
        ready_module.prepare_ready = prepare_ready_stub
        spell_module = ModuleType("wakfu_server.combat_server_spell")
        spell_module.prepare_server_initialization = prepare_initialize
        spell_module.prepare_server_turn_end = Mock()
        spell_module.prepare_server_turn_start = Mock()
        spells_module = ModuleType("wakfu_server.spells")
        spells_module.default_deck = lambda _character: b"default"
        modules = {
            "wakfu_server.combat_shared": shared_module,
            "wakfu_server.fight_store": fight_store,
            "wakfu_server.combat_actor": actor_module,
            "wakfu_server.combat_ready": ready_module,
            "wakfu_server.combat_server_spell": spell_module,
            "wakfu_server.spells": spells_module,
        }

        adapter_path = (
            _ROOT / "server" / "wakfu_server" / "combat" / "combat_session_adapter.py"
        )
        adapter_spec = importlib.util.spec_from_file_location(
            "wakfu_server._combat_session_adapter_staged_provider_test", adapter_path
        )
        adapter_module = importlib.util.module_from_spec(adapter_spec)
        session = SimpleNamespace(account_id=1)
        with temporary_server_modules(modules):
            adapter_spec.loader.exec_module(adapter_module)
            adapter = adapter_module.CombatSessionAdapter.__new__(
                adapter_module.CombatSessionAdapter
            )
            adapter.player_sources = lambda _fight: (characters, decks)
            transition = adapter.ready_transition(
                session,
                fight,
                None,
                True,
                monsters,
                fight_start=True,
                area_callbacks=True,
            )

        self.assertIsInstance(transition, Transition)
        self.assertIs(transition.fight, fight)
        self.assertIsNone(transition.runtime)
        self.assertEqual(transition.packets, ((2000, b"ready"),))
        provider = ready_args["expiration_runtime_factory"]
        self.assertIsInstance(provider, OwnedExpirationFactory)
        self.assertEqual(provider.actor_id, 10)
        self.assertEqual(provider.characters, characters)
        self.assertEqual(provider.monsters, monsters)
        self.assertEqual(provider.decks, decks)
        self.assertIs(ready_args["turn_start_provider"].__self__, provider)
        self.assertIs(ready_args["turn_end_provider"].__self__, provider)
        self.assertEqual([row[3] for row in initialize_calls], [10, 20])
        self.assertEqual(
            [row[5]["fight_start"] for row in initialize_calls], [False, True]
        )
        self.assertTrue(
            all(row[5]["player_characters"] is characters for row in initialize_calls)
        )
        self.assertTrue(all(row[5]["deck_blobs"] is decks for row in initialize_calls))
        self.assertEqual(
            [(row[0]["id"], row[2], row[3]["fight"].id) for row in stats_calls],
            [(10, 81, 81), (20, 81, 81)],
        )
        self.assertEqual(ready_args["initial_packets"], ((1000, b"10"), (1000, b"20")))

    def test_private_preparation_failure_never_calls_poisoned_shared_fallbacks(self):
        from wakfu_ai.bridge.world_shared import run_shared_turn

        runtime = SimpleNamespace(future_runtime_authority={"source": b"socket"})
        shared, adapter, session = shared_fixture(runtime)
        fight = shared.fight
        characters, monsters, decks = authority_fixture()
        characters[10]["account_id"] = 999
        provider = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=10,
        )
        poison_calls = []

        def poisoned(*_args, **_kwargs):
            poison_calls.append("socket-provider")
            raise AssertionError("poisoned shared provider must stay unused")

        runtime.expiration_runtime_factory = provider
        runtime.turn_start_provider = poisoned
        runtime.turn_end_provider = poisoned
        runtime.stats_serializer = poisoned
        runtime.runtime_stats_serializer = poisoned
        runtime.end_server_turn = poisoned
        source_fingerprint = tuple(
            (actor_id, deepcopy(vars(actor)))
            for actor_id, actor in sorted(fight.actors.items())
        )
        original_runtime = shared.runtime
        original_sequence = shared.sequence
        outboxes = {
            identity: deepcopy(list(queue))
            for identity, queue in shared.outboxes.items()
        }
        resource_state = {
            identity: deepcopy(
                (actor.ap, actor.mp, actor.effect_stats, actor.effect_maxima)
            )
            for identity, actor in fight.actors.items()
        }
        runner_calls = []

        def runner(_candidate):
            runner_calls.append(True)
            yield [], {}

        # run_shared_turn's import boundary is replaced only because the failure
        # must happen before a Transition is constructed; this keeps the test
        # independent of the native data catalogue and the engine adapter.
        transition_module = SimpleNamespace(
            Transition=lambda fight, native, packets: (fight, native, packets)
        )
        import wakfu_server

        prior_shared_module = getattr(wakfu_server, "combat_shared", None)
        with patch.dict(sys.modules, {"wakfu_server.combat_shared": transition_module}):
            with self.assertRaisesRegex(ValueError, "owned background viewer"):
                list(
                    run_shared_turn(
                        runtime,
                        adapter,
                        session,
                        runner,
                        prepare_candidate=bind_private_sources,
                    )
                )
        if prior_shared_module is None:
            if hasattr(wakfu_server, "combat_shared"):
                delattr(wakfu_server, "combat_shared")
        else:
            wakfu_server.combat_shared = prior_shared_module

        self.assertEqual(poison_calls, [])
        self.assertEqual(runner_calls, [])
        self.assertIs(shared.runtime, original_runtime)
        self.assertEqual(shared.sequence, original_sequence)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])
        self.assertEqual(
            {identity: list(queue) for identity, queue in shared.outboxes.items()},
            outboxes,
        )
        self.assertEqual(
            {
                identity: (actor.ap, actor.mp, actor.effect_stats, actor.effect_maxima)
                for identity, actor in fight.actors.items()
            },
            resource_state,
        )
        self.assertEqual(
            tuple(
                (actor_id, deepcopy(vars(actor)))
                for actor_id, actor in sorted(fight.actors.items())
            ),
            source_fingerprint,
        )
        self.assertFalse(hasattr(shared, "native_ai_turn_claim"))


if __name__ == "__main__":
    unittest.main()
