"""Pre-initialization selection of a genuine durable published NPC."""
from contextlib import contextmanager
from unittest.mock import patch
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_actor_snapshot import native_npc_creation_values

NPC_REFERENCE = 4168
NPC_LEVEL = 190


def assert_native_enemy(case, fight, monster):
    record = native_catalog.record(
        DATA_ROOT / "monsters.json", "monsters", str(NPC_REFERENCE)
    )
    case.assertEqual((record["min_level"], record["max_level"]), (190, 190))
    case.assertEqual(monster["ref"], NPC_REFERENCE)
    case.assertEqual(fight.actors[-7].effective_level, NPC_LEVEL)
    values = native_npc_creation_values(NPC_REFERENCE, NPC_LEVEL)
    case.assertEqual((values[1]["current"], values[1]["maximum"]), (8784, 8784))
    case.assertEqual(
        (fight.actors[-7].hp, fight.actors[-7].max_hp),
        (values[1]["current"], values[1]["maximum"]),
    )


@contextmanager
def hupper_constructor():
    from test_combat_spell_transaction import SpellTransactionTests

    original = SpellTransactionTests.native_server_fixture

    def construct(instance, *args, **kwargs):
        kwargs.pop("target_hp", None)
        kwargs.update(target_ref=NPC_REFERENCE, target_level=NPC_LEVEL)
        return original(instance, *args, **kwargs)

    with patch.object(SpellTransactionTests, "native_server_fixture", construct):
        yield


@contextmanager
def xelor_constructor(module):
    original = module.fixture

    def construct(*args, **kwargs):
        kwargs.update(monster_reference=NPC_REFERENCE, monster_level=NPC_LEVEL)
        return original(*args, **kwargs)

    with patch.object(module, "fixture", construct):
        yield
