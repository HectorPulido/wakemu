"""Database policy and authentic retained UID selection, without a scene loop."""
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxCubeTableListenerTests(PostgresCase):
    def fixture(self):
        from wakfu_server import combat_encounter_table_listeners as listeners

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        with patch.object(listeners, "_database", return_value=self.store):
            frozen = listeners.freeze_table_listener_policy(1435, (5664,))
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority

        owner = SimpleNamespace(
            id=-20,
            controlled=False,
            hp=100,
            native_controller_id=-7,
            owner_id=10,
            native_summon_source=dict(
                ref=5786,
                level=200,
                caster_id=-7,
                controller_id=-7,
                native_relation_source="big.new_bje.fdt_initial_registration",
            ),
            state_ledger=SimpleNamespace(
                entries=(SimpleNamespace(uid=101, reference=8974, target_id=-20),)
            ),
        )
        fight = SimpleNamespace(
            actors={-20: owner, -7: SimpleNamespace(controlled=False, owner_id=10)},
            native_summon_registrations={
                -20: dict(
                    actor_id=-20,
                    caster_id=-7,
                    controller_id=-7,
                    authority=vars(
                        NativeActorAuthority(
                            {},
                            False,
                            frozenset(),
                            frozenset(),
                            False,
                            5786,
                            0,
                            {},
                            True,
                            is_summon=True,
                            native_real_level=200,
                            native_controller_id=-7,
                            native_npc_prototype_ref=5786,
                        )
                    ),
                )
            },
            boss_score_profile=dict(table_listener_policy=frozen),
            native_npc_initialization_receipts={
                -7: dict(
                    ref=5664, initialized=True, resolved_states=[dict(state_id=8969)]
                )
            },
            native_owned_group_effects={31: dict(invocation=dict(state_uid=101))},
        )
        self.assertFalse(hasattr(owner, "native_npc_prototype_ref"))
        calls = []

        def replay(source, **kwargs):
            calls.append((source, kwargs))
            return ("cube",)

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_clone_authority=object(),
            replay_event=replay,
        )
        snapshot = (
            SimpleNamespace(uid=31, generic_effect=401548, manager_id=-20),
            SimpleNamespace(uid=32, generic_effect=401548, manager_id=9),
            SimpleNamespace(uid=33, generic_effect=401534, manager_id=-20),
        )
        return listeners, fight, dispatcher, snapshot, calls

    def test_database_freeze_selects_only_original_owned_cube_listener(self):
        listeners, fight, dispatcher, snapshot, calls = self.fixture()
        with patch.object(listeners, "_database", return_value=self.store):
            outcomes, records = listeners.deliver_owned_table_listeners(
                dispatcher,
                boss_id=-7,
                snapshot=snapshot,
            )
            self.assertEqual(outcomes, ("cube",))
            self.assertEqual(records[0]["eligible_uids"], [31])
            source, arguments = calls[0]
            self.assertEqual(
                (source.manager_actor_id, source.event_ids, source.channel),
                (-20, (1003,), 61),
            )
            self.assertEqual(arguments["eligible_uids"], frozenset((31,)))
            self.assertIs(arguments["authority"], dispatcher.native_clone_authority)
            # Admission is frozen; deleting only the mutable active pointer
            # cannot change an already pinned fight's original listener.
            with self.store.connection() as db:
                db.execute("DELETE FROM encounter_table_listener_active")
            listeners.deliver_owned_table_listeners(
                dispatcher, boss_id=-7, snapshot=snapshot
            )
            self.assertEqual(len(calls), 2)

    def test_forged_owner_changed_policy_and_unowned_uid_fail_before_replay(self):
        listeners, fight, dispatcher, snapshot, calls = self.fixture()
        owner = fight.actors[-20]
        with patch.object(listeners, "_database", return_value=self.store):
            owner.native_summon_source["caster_id"] = 99
            with self.assertRaisesRegex(ValueError, "authentic native birth"):
                listeners.deliver_owned_table_listeners(
                    dispatcher, boss_id=-7, snapshot=snapshot
                )
            owner.native_summon_source["caster_id"] = -7
            authority = fight.native_summon_registrations[-20]["authority"]
            authority["native_npc_prototype_ref"] = 999
            with self.assertRaisesRegex(ValueError, "authentic native birth"):
                listeners.deliver_owned_table_listeners(
                    dispatcher, boss_id=-7, snapshot=snapshot
                )
            authority["native_npc_prototype_ref"] = 5786
            fight.native_owned_group_effects[31]["invocation"]["state_uid"] = 999
            with self.assertRaisesRegex(ValueError, "does not belong"):
                listeners.deliver_owned_table_listeners(
                    dispatcher, boss_id=-7, snapshot=snapshot
                )
            fight.native_owned_group_effects[31]["invocation"]["state_uid"] = 101
            fight.boss_score_profile["table_listener_policy"][
                "effect_reference"
            ] = 401534
            with self.assertRaisesRegex(ValueError, "policy changed"):
                listeners.deliver_owned_table_listeners(
                    dispatcher, boss_id=-7, snapshot=snapshot
                )
            self.assertEqual(calls, [])
