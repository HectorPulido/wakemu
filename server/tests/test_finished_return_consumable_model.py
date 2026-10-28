"""Terminal checkpoint recovery preserves the native consumable event context."""
from contextlib import nullcontext
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class FinishedReturnConsumableModelTests(unittest.TestCase):
    def test_checkpoint_native_model_reaches_owned_consumable_return_events(self):
        from wakfu_server import combat_health, consumable_buffs, fight_store
        from wakfu_server.combat_consumable_lifecycle import return_participant
        from wakfu_server.combat_state_ledger import RunningState

        carrier = RunningState(
            uid=901,
            reference=732,
            level=50,
            caster_id=46,
            target_id=46,
            duration=-1,
            clock_actor="target",
            tick_at_turn_end=False,
            effect_ids=(),
            realtime_duration=0,
            retained=True,
            timer=None,
        )
        checkpoint = {
            "phase": "finished",
            "native_fight_model": 2,
            "actors": {
                "46": {
                    "controlled": True,
                    "owner_id": 23,
                    "hp": 376,
                    "max_hp": 537,
                    "state_ledger": {"actor_id": 46, "entries": [asdict(carrier)]},
                },
            },
            "native_consumable_initializations": {
                "46": [
                    {
                        "world_uid": 701,
                        "combat_uid": 901,
                        "state_id": 732,
                        "clock": "event",
                    }
                ],
            },
        }
        db = Mock()
        db.execute.side_effect = [
            SimpleNamespace(
                fetchone=lambda: {
                    "status": "finished",
                    "fight_kind": "pve",
                    "session_generation": "old-generation",
                    "checkpoint_status": "ended",
                    "checkpoint_revision": 3,
                    "checkpoint_snapshot": checkpoint,
                }
            ),
            SimpleNamespace(fetchone=lambda: None),
        ]
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            lock_character=Mock(),
            clock=lambda: 1000,
        )
        character = {"id": 46, "account_id": 23}

        def persist_owned(store, account, generation, character, fight, **kwargs):
            self.assertEqual(
                (account, generation, kwargs["reason"]),
                (23, "new-generation", "return"),
            )
            return_participant(store, db, character["id"], fight, generation=generation)
            return {"applied": True, "character": character}

        with patch.object(
            fight_store, "_takeover_account_memberships"
        ) as takeover, patch.object(
            combat_health, "persist_owned", side_effect=persist_owned
        ), patch.object(
            consumable_buffs, "active_states", return_value=({"combat_id": 434},)
        ), patch.object(
            consumable_buffs, "return_from_combat"
        ) as returned, patch.object(
            consumable_buffs, "emit_events", return_value=()
        ) as events:
            result = fight_store.recover_finished_return(
                store,
                23,
                "new-generation",
                46,
                None,
                character,
                previous_generation="old-generation",
                fight_id=434,
            )

        self.assertTrue(result["recovered_from_checkpoint"])
        self.assertEqual(result["fight"].native_fight_model, 2)
        self.assertEqual(result["fight"].actors[46].state_ledger.entries, (carrier,))
        takeover.assert_called_once_with(
            db, 434, 23, "new-generation", "old-generation"
        )
        returned.assert_called_once_with(
            store,
            db,
            46,
            434,
            (
                {
                    "uid": 701,
                    "state_id": 732,
                    "removed": False,
                    "level": 50,
                    "clock": "event",
                    "remaining_ms": 0,
                },
            ),
            generation="new-generation",
            now_ms=1_000_000,
        )
        events.assert_called_once_with(
            store,
            db,
            46,
            (1030, 1043),
            generation="new-generation",
            now_ms=1_000_000,
            fight_model=2,
        )
