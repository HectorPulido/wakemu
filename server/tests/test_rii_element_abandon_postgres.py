"""Real local abort commits removal of an owned lesson's temporary spells."""
from unittest.mock import patch

from postgres_case import PostgresCase
from test_combat_abandon import setup_abandon_state
from wakfu_server import combat_abandon, rii_lesson_grants
from wakfu_server.combat_spell_grant import granted_spells


class ElementalAbandonPostgresTests(PostgresCase):
    def test_active_abandon_removes_four_grants_after_durable_commit(self):
        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        fight.ready(account)
        fight.native_effect_uid_next = 1000
        fight.rii_element_lesson_contract = {"owner": character["id"], "target": -200}
        packets = []
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
                character["id"],
                packets,
                action_id=1,
                allocate_uid=fight.allocate_effect_uid,
            )
        fight.rii_element_lesson_contract.update(initialized=True, grant_uids=uids)
        result = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        self.assertTrue(result["applied"])
        self.assertEqual([op for op, _ in result["packets"]].count(13560), 4)
        self.assertFalse(granted_spells(fight, character["id"]))
        self.assertEqual(fight.phase, "finished")
