"""Area-lesson grants use all native terminal and withdrawal paths."""
from unittest.mock import patch

import test_combat_maximum_resource as maximum_fixture
import test_combat_pve_withdraw as withdrawal_fixture
from test_rii_lesson_terminal_grants import RiiLessonTerminalGrantTests
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_spell_grant import granted_spells


class RiiAreaTerminalGrantTests(RiiLessonTerminalGrantTests):
    grant_count = 3

    def grants(self):
        # This subclass inherits terminal-path tests for the other lessons;
        # keep their server-owned grants in the same isolated spell fixture.
        spells = tuple(
            sorted(
                {
                    spell
                    for _, lesson_spells in rii_lesson_grants.LESSONS.values()
                    for spell in lesson_spells
                }
            )
        )
        refs = patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(spells),
        )
        casts = patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={str(spell): {"maximum_level": 200} for spell in spells},
        )
        refs.start()
        casts.start()
        self.addCleanup(refs.stop)
        self.addCleanup(casts.stop)

    def install(self, fight, owner):
        self.grants()
        contract = {"owner": owner, "targets": [-1, -2, -3, -4]}
        fight.rii_area_lesson_contract = contract
        uid = iter(range(1001, 1004))
        contract["grant_uids"] = rii_lesson_grants.install(
            fight, owner, [], action_id=1, allocate_uid=lambda: next(uid), lesson="area"
        )
        contract["initialized"] = True

    def make_fight(self):
        fixture = maximum_fixture.MaximumResourceTests()
        fixture.setUp()
        self.install(fixture.fight, 7)
        return fixture.fight

    def test_shared_individual_withdrawal_removes_departing_owner_grants(self):
        from wakfu_server.combat_pve_withdraw import plan

        helper = withdrawal_fixture.WithdrawalPlanTests()
        helper.setUp()
        fight, runtime, session = helper.fight, helper.runtime, helper.session
        self.install(fight, 10)
        fight.phase = "placement"
        with patch("wakfu_server.combat_pve_departure.retire_pve_actor"), patch(
            "wakfu_server.combat_death.death_messages", return_value=[]
        ):
            result = plan(session, fight, runtime)
        self.assertEqual([op for op, _ in result.public_packets].count(13560), 3)
        self.assertNotIn("rii_area_lesson_contract", result.fight.__dict__)
        self.assertFalse(granted_spells(result.fight, 10))
        self.assertNotIn(
            "rii_area_lesson_contract", result.private_runtime.fight.__dict__
        )
