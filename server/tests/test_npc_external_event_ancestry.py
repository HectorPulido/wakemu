"""NPC event ancestry guards through canonical Wakfu imports."""
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids


class NativeCloneAuthority:
    def __init__(self, executable, condition_context):
        self.executable, self.condition_context = executable, condition_context


class OrdinaryHealingEvents:
    def executable(self, *args):
        return True

    def conditions(self, *args):
        return None


class OrdinaryActorAuthority:
    pass


class RegisteredSummonAuthority:
    def __init__(self, ordinary):
        self.ordinary = ordinary

    def __call__(self, fight, actor):
        if (
            actor.id in fight.expected
            and fight.native_summon_registrations.get(actor.id)
            != fight.expected[actor.id]
        ):
            raise ValueError("stale fixture registration")
        return fight.facts[actor.id]


def ordinary_roster_authority(authority):
    return isinstance(authority, OrdinaryActorAuthority) or (
        isinstance(authority, RegisteredSummonAuthority)
        and isinstance(authority.ordinary, OrdinaryActorAuthority)
    )


@dataclass(frozen=True)
class NativeActorAuthority:
    is_player: bool
    native_actor_type: int
    native_npc_prototype_ref: int
    is_summon: bool


def _module(name, **symbols):
    module = ModuleType(f"wakfu_server.{name}")
    module.__dict__.update(symbols)
    return module


def _fields_from_hex(payload):
    data = bytes.fromhex(payload)
    value = shift = offset = 0
    while offset < len(data):
        tag = data[offset]
        offset += 1
        while True:
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if byte < 128:
                break
            shift += 7
        return {tag >> 3: value}


_STUB_MODULES = {
    "wakfu_server.combat_event_replay": _module(
        "combat_event_replay", NativeCloneAuthority=NativeCloneAuthority
    ),
    "wakfu_server.combat_ordinary_events": _module(
        "combat_ordinary_events", OrdinaryHealingEvents=OrdinaryHealingEvents
    ),
    "wakfu_server.combat_summon": _module(
        "combat_summon",
        RegisteredSummonAuthority=RegisteredSummonAuthority,
        ordinary_roster_authority=ordinary_roster_authority,
    ),
    "wakfu_server.combat_state_managers": _module(
        "combat_state_managers",
        state_managers=lambda fight: iter(fight.actors.values()),
    ),
    "wakfu_server.combat_effect_removal": _module(
        "combat_effect_removal", _readonly_hex_identity_fields=_fields_from_hex
    ),
    "wakfu_server.combat_retained_source_provenance": _module(
        "combat_retained_source_provenance", state_source_provenance=lambda fight: {}
    ),
    "wakfu_server.combat_equipment_finish": _module(
        "combat_equipment_finish", _qualified_sources=lambda fight: ()
    ),
}


def _varint(value):
    output = bytearray()
    while value >= 128:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return output


def _wire_source(identity):
    return bytes((0x30, *_varint(identity & ((1 << 64) - 1)))).hex()


@dataclass
class Entry:
    uid: int
    effect_class: int = 400
    owner_uid: int | None = None
    container_kind: str | None = None
    container_type: int | None = None


class Retention:
    def __init__(self, fight, entries):
        self.fight = fight
        self.entries = tuple(entries)

    def view(self):
        return SimpleNamespace(entries=self.entries)


def _metadata(*, summon, player=False):
    return NativeActorAuthority(
        is_player=player,
        is_summon=summon,
        native_actor_type=1,
        native_npc_prototype_ref=5376,
    )


def _fixture(mode="valid", dead_parent=False):
    root, child, uid = -100100, -200100, 900001
    actors = {
        root: SimpleNamespace(
            id=root, controlled=False, state_ledger=SimpleNamespace(entries=())
        ),
        child: SimpleNamespace(
            id=child, controlled=False, state_ledger=SimpleNamespace(entries=())
        ),
    }
    registration = {"actor_id": child, "caster_id": root, "controller_id": child}
    expected = dict(registration)
    facts = {root: _metadata(summon=False), child: _metadata(summon=True)}
    if mode == "player_root":
        actors[root].controlled = True
        facts[root] = _metadata(summon=False, player=True)
    elif mode == "cycle":
        registration["caster_id"] = child
        expected = dict(registration)
    elif mode == "stale_registration":
        registration["controller_id"] = root
    elif mode == "unregistered":
        actors.pop(child)
    if dead_parent:
        actors[root].dead = True

    ordinary = object.__new__(OrdinaryActorAuthority)
    authority = RegisteredSummonAuthority(ordinary)
    fight = SimpleNamespace(
        actors=actors,
        native_summon_registrations={}
        if mode == "unregistered"
        else {child: registration},
        native_owned_group_effects={
            uid: {
                "invocation": {"caster_id": child},
                "payload": _wire_source(child),
            }
        },
        native_effect_areas={},
        native_retired_area_managers={},
        native_owned_equipment_initializations={},
        native_consumable_initializations={},
        state_wire_payloads={},
        expected={child: expected},
        facts=facts,
    )
    retention = Retention(fight, (Entry(uid),))
    lifecycle = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
    lifecycle.adapter = SimpleNamespace(actor_authority=authority)
    lifecycle.preview, lifecycle.retention = fight, retention
    lifecycle.replay = lambda *args, **kwargs: None
    clone = NativeCloneAuthority(lifecycle.executable, lifecycle.conditions)
    dispatcher = SimpleNamespace(
        native_retention=retention,
        native_clone_authority=clone,
        replay_event=lifecycle.replay,
    )
    return dispatcher, uid


class NpcExternalEventAncestryTests(unittest.TestCase):
    def setUp(self):
        self.stubs = patch.dict(sys.modules, _STUB_MODULES)
        self.stubs.start()

    def tearDown(self):
        self.stubs.stop()

    def test_registered_npc_child_with_self_controller_is_admitted(self):
        dispatcher, uid = _fixture()
        self.assertIn(uid, qualified_npc_uids(dispatcher))

    def test_player_root_and_cyclic_caster_ancestry_are_rejected(self):
        for mode in ("player_root", "cycle"):
            with self.subTest(mode=mode):
                dispatcher, uid = _fixture(mode)
                self.assertNotIn(uid, qualified_npc_uids(dispatcher))

    def test_unregistered_and_changed_registration_fail_closed(self):
        dispatcher, uid = _fixture("unregistered")
        self.assertNotIn(uid, qualified_npc_uids(dispatcher))
        dispatcher, _ = _fixture("stale_registration")
        with self.assertRaisesRegex(ValueError, "stale fixture registration"):
            qualified_npc_uids(dispatcher)

    def test_dead_parent_does_not_invalidate_valid_native_ancestry(self):
        dispatcher, uid = _fixture(dead_parent=True)
        self.assertIn(uid, qualified_npc_uids(dispatcher))


if __name__ == "__main__":
    unittest.main(verbosity=2)
