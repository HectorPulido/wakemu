"""Shared abort removes lesson grants in the durable abort transaction."""
from unittest.mock import patch

from postgres_case import PostgresCase
import test_combat_shared_full_abandon as shared_fixture
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_shared_abandon import prepare
from wakfu_server.combat_spell_grant import granted_spells


class ElementalSharedAbandonTests(PostgresCase):
    fixture = shared_fixture.SharedFullAbandonTests.fixture

    def test_full_shared_abort_removes_lesson_grants(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        fight = shared.fight
        fight.native_effect_uid_next = 1000
        fight.rii_element_lesson_contract = {
            "owner": requester.character_id,
            "target": -200,
        }
        with patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(rii_lesson_grants.SPELLS),
        ), patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={
                str(i): {"maximum_level": 200} for i in rii_lesson_grants.SPELLS
            },
        ):
            uids = rii_lesson_grants.install(
                fight,
                requester.character_id,
                [],
                action_id=1,
                allocate_uid=fight.allocate_effect_uid,
            )
        fight.rii_element_lesson_contract.update(initialized=True, grant_uids=uids)
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertTrue(result["applied"])
        self.assertEqual([op for op, _ in result["packets"]].count(13560), 4)
        self.assertFalse(granted_spells(shared.fight, requester.character_id))
