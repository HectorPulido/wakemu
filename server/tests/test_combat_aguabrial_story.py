"""Source-backed reconstruction guards; actual native kill runner and storage API."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from wakfu_server.combat_aguabrial_scene import (
    authorize_aguabrial_scene,
    bind_aguabrial_start,
    earned_story_continuation,
)
from wakfu_server.combat_aguabrial_story import settle_aguabrial_story
from wakfu_server.combat_quest_scene_authority import AuthenticatedQuestFact

SCENE = "wakfu_server.combat_aguabrial_scene"
STORY = "wakfu_server.combat_aguabrial_story"


class Database:
    def __init__(self):
        self.result = None

    def execute(self, sql, args):
        if "SELECT map_id" in sql:
            self.result = dict(map_id=529)
        elif "combat_fight_participants" in sql:
            self.result = dict(team=0, status="finished", fight_kind="pve")
        else:
            self.result = None
        return self

    def fetchone(self):
        return self.result


class AguabrialStoryTests(unittest.TestCase):
    def fixture(self):
        from test_combat_forced_retirement import ForcedRetirementTests
        from test_combat_kill import NativeKillTests

        fight, player, boss, _, _, _, _ = ForcedRetirementTests().fixture()
        # Borrow characteristic shape from an existing real native kill fixture.
        _, stats, _, _, _, _, _ = NativeKillTests().fixture(1)
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_base_minima",
            "effect_base_maxima",
            "effect_percentages",
            "effect_frozen",
        ):
            setattr(player, name, deepcopy(getattr(stats, name)))
        player.hp, player.owner_id = 80, 7
        player.team = 0
        boss.team = 1
        fact = AuthenticatedQuestFact(
            7, player.id, "A", 3797, 7835, (7834,), 9, "b" * 64, 1, ""
        )
        admission = SimpleNamespace(id=fight.id, phase="placement", actors=fight.actors)
        with patch(SCENE + ".authenticated_quest_fact", return_value=fact), patch(
            "wakfu_server.native_catalog.release", return_value="a" * 64
        ), patch(
            "wakfu_server.combat_encounter_source_revision.source_revision_matches",
            return_value=True,
        ):
            authorize_aguabrial_scene(
                None,
                Database(),
                admission,
                account_id=7,
                generation="A",
                character_id=player.id,
                monster_references=(1723,),
            )
        fight.native_encounter_actor_contract = (
            admission.native_encounter_actor_contract
        )
        fight.native_aguabrial_story_admission = (
            admission.native_aguabrial_story_admission
        )
        fight.native_npc_initialization_receipts = {
            boss.id: dict(
                ref=1723,
                descriptor_level=boss.effective_level,
                raw_triples=[],
                resolved_states=[dict(state_id=1128), dict(state_id=1137)],
                applications=[],
                initialized=True,
            ),
        }
        bind_aguabrial_start(fight)
        return fight, player, boss, fact

    def kill(self, fight, player, boss):
        from wakfu_server.combat_kill import NativeKillHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext

        handler = NativeKillHandler(
            fight,
            [],
            action_id=5,
            allocate_uid=lambda: 1001,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            authority=SimpleNamespace(property_counts=lambda p, a: {}),
        )
        effect = dict(
            effect_class=28,
            parameter_count=1,
            parameters=[1, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(240347, 215, boss.id, player.id, player.position)
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        death = next(
            row
            for row in reversed(fight.events)
            if row["kind"] == "death" and row["actor_id"] == player.id
        )
        # Death-boundary production is qualified independently by its real suite.
        fight.native_death_event_deliveries = {
            str(death["sequence"]): dict(
                actor_id=player.id,
                event_id=1013,
                channel=6,
                policy="wakemu.owned-ko-and-death-v3",
            ),
        }

    def test_ordinary_fights_and_unearned_quest_do_not_admit(self):
        fight = SimpleNamespace(id=1, phase="placement", actors={})
        self.assertIsNone(
            authorize_aguabrial_scene(
                None,
                None,
                fight,
                account_id=7,
                generation="A",
                character_id=19,
                monster_references=(5165,),
            )
        )
        with patch(SCENE + ".authenticated_quest_fact", return_value=None):
            self.assertIsNone(
                authorize_aguabrial_scene(
                    None,
                    None,
                    fight,
                    account_id=7,
                    generation="A",
                    character_id=19,
                    monster_references=(1723,),
                )
            )
        self.assertFalse(bind_aguabrial_start(fight))
        self.assertFalse(hasattr(fight, "native_encounter_actor_contract"))

    def test_real_native_kill_earns_continuation_not_combat_victory(self):
        fight, player, boss, _ = self.fixture()
        self.assertIsNone(earned_story_continuation(fight))
        self.kill(fight, player, boss)
        receipt = earned_story_continuation(fight)
        self.assertEqual(receipt["generic_effect"], 240347)
        self.assertEqual(receipt["story_exit_event"], 19123)
        self.assertFalse(receipt["combat_victory"])
        self.assertEqual(fight.winner, boss.team)
        self.assertGreater(boss.hp, 0)

    def test_wrong_cause_missing_death_delivery_and_withdrawal_cannot_earn(self):
        fight, player, boss, _ = self.fixture()
        self.kill(fight, player, boss)
        index = next(
            i
            for i, row in enumerate(fight.events)
            if row["kind"] == "kill_hp_minimum_update"
        )
        for field, value in (("generic_effect", 112822), ("source_id", player.id)):
            other = deepcopy(fight)
            other.events[index][field] = value
            self.assertIsNone(earned_story_continuation(other))
        other = deepcopy(fight)
        other.native_death_event_deliveries = {}
        self.assertIsNone(earned_story_continuation(other))
        player.pve_withdrawn = True
        self.assertIsNone(earned_story_continuation(fight))

    def test_durable_losing_participant_advances_only_original_objective_once(self):
        fight, player, boss, fact = self.fixture()
        self.kill(fight, player, boss)
        self.assertEqual((fight.phase, fight.winner), ("finished", boss.team))
        before = dict(
            variables={},
            objectives=[7834],
            running=[3797],
            completed=[],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        members = [dict(account_id=7, character_id=player.id, session_generation="A")]
        now = datetime(2026, 10, 25, tzinfo=timezone.utc)
        with patch(
            STORY + ".authenticated_quest_fact", return_value=fact
        ) as auth, patch(
            "wakfu_server.achievements.storage.load_locked", return_value=before
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as reserve, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.storage.enqueue_notifications"
        ) as outbox:
            packets = settle_aguabrial_story(
                SimpleNamespace(now=lambda: now), Database(), fight, members
            )
            self.assertEqual(list(packets), [7])
            self.assertEqual([op for op, _ in packets[7]], [13832])
            saved = persist.call_args.args[2]
            self.assertEqual(saved["objectives"], [7834, 7835])
            self.assertEqual(saved["completed"], [])
            self.assertEqual(saved["variables"], {})
            self.assertEqual(saved["running"], [3797])
            outbox.assert_called_once()
            auth.assert_called_once()
            reserve.return_value = False
            self.assertEqual(
                settle_aguabrial_story(
                    SimpleNamespace(now=lambda: now), Database(), fight, members
                ),
                {},
            )
            self.assertEqual(persist.call_count, 1)
        self.assertEqual(fight.winner, boss.team)


if __name__ == "__main__":
    unittest.main()
