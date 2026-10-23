"""DB-scoped reconstructed publisher; original callback routing stays separate."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class EncounterAreaActivationTests(PostgresCase):
    def test_frozen_database_scope_reentrancy_rollback_retry_and_removed_area(self):
        from wakfu_server import combat_encounter_area_activation as policy
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        roles = SimpleNamespace(map_id=1400, monster_references=(5500,))
        other = SimpleNamespace(map_id=545, monster_references=(2430,))
        area = dict(
            uid=50, reference=1839, native_cells_xy=((0, 0),), native_faw_constructor={}
        )
        actors = {
            identity: SimpleNamespace(id=identity, hp=hp, position=cell)
            for identity, hp, cell in (
                (1, 100, (0, 0, 0)),
                (2, 100, (0, 0, 0)),
                (3, 0, (0, 0, 0)),
                (4, 100, (1, 0, 0)),
            )
        }
        fight = SimpleNamespace(
            actors=actors,
            native_effect_areas={50: area},
            executed=[],
            _in_play=lambda actor: actor.hp > 0,
        )
        policy._version.cache_clear()
        self.addCleanup(policy._version.cache_clear)
        with patch.object(policy, "_database", return_value=self.store), patch(
            "wakfu_server.combat_encounter_roles.frozen_roles", return_value=roles
        ), patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=object(),
        ):
            unrelated = deepcopy(fight)
            self.assertIsNone(
                policy.freeze_encounter_area_policy(unrelated, roles=other)
            )
            selected = policy.freeze_encounter_area_policy(fight, roles=roles)
            self.assertEqual(
                (selected.event_id, selected.area_references),
                (10006, (1839, 1840, 1841, 1842)),
            )

            def dispatcher(current, *, fail=False, remove=False):
                result = SimpleNamespace(
                    native_retention=SimpleNamespace(fight=current)
                )
                runtime = SimpleNamespace(
                    _definition=lambda row: dict(entry_masks=[10006])
                )

                def event(event_id, identity, *, area_uid):
                    current.executed.append((event_id, identity, area_uid))
                    if fail:
                        raise ValueError("injected child failure")
                    # Reentrant activation must not dispatch the same UID/actor.
                    if len(current.executed) == 1 and not remove:
                        policy.post_registration_activation(
                            result, current.native_effect_areas[50]
                        )
                    if remove:
                        current.native_effect_areas.pop(area_uid, None)
                    return (True,)

                runtime.event = event
                result.native_area_events = runtime
                return result

            # Native created remains registration-only, even in this opted-in fight.
            native = dispatcher(fight)
            self.assertEqual(
                NativeAreaEventRuntime.created(native.native_area_events, area), ()
            )
            self.assertEqual(fight.executed, [])
            self.assertEqual(
                policy.post_registration_activation(
                    dispatcher(unrelated), unrelated.native_effect_areas[50]
                ),
                (),
            )
            self.assertEqual(unrelated.executed, [])

            failed = deepcopy(fight)
            with self.assertRaisesRegex(ValueError, "injected"):
                policy.post_registration_activation(
                    dispatcher(failed, fail=True), failed.native_effect_areas[50]
                )
            # Production owns this same preview/adopt boundary: failed preview is discarded.
            self.assertEqual(fight.native_encounter_area_activation["delivered"], [])
            self.assertEqual(fight.executed, [])
            retried = deepcopy(fight)
            policy.post_registration_activation(
                dispatcher(retried), retried.native_effect_areas[50]
            )
            self.assertEqual(sorted(retried.executed), [(10006, 1, 50), (10006, 2, 50)])
            policy.post_registration_activation(
                dispatcher(retried), retried.native_effect_areas[50]
            )
            self.assertEqual(len(retried.executed), 2)
            self.assertEqual(
                sorted(retried.native_encounter_area_activation["delivered"]),
                [[50, 1], [50, 2]],
            )

            removed = deepcopy(fight)
            policy.post_registration_activation(
                dispatcher(removed, remove=True), removed.native_effect_areas[50]
            )
            self.assertNotIn(50, removed.native_effect_areas)
            self.assertEqual(len(removed.executed), 1)
            nested = deepcopy(fight)
            nested_dispatcher = dispatcher(nested)
            active, order = [], []

            def reflected_event(event_id, identity, *, area_uid):
                self.assertEqual(active, [])
                active.append(area_uid)
                order.append(("start", area_uid, identity))
                if area_uid == 50 and identity == 1:
                    child = dict(nested.native_effect_areas[50], uid=51)
                    nested.native_effect_areas[51] = child
                    policy.post_registration_activation(nested_dispatcher, child)
                    self.assertFalse(any(uid == 51 for _, uid, _ in order))
                order.append(("end", area_uid, identity))
                active.pop()
                return (True,)

            nested_dispatcher.native_area_events.event = reflected_event
            policy.post_registration_activation(
                nested_dispatcher, nested.native_effect_areas[50]
            )
            self.assertEqual(
                order,
                [
                    (kind, uid, identity)
                    for uid, identity in ((50, 1), (50, 2), (51, 1), (51, 2))
                    for kind in ("start", "end")
                ],
            )
            self.assertEqual(nested.native_encounter_area_activation["pending"], [])
            self.assertFalse(nested.native_encounter_area_activation["draining"])

            # Unique newUIDs cannot defeat the runtime's finite trigger budget.
            cyclic = deepcopy(fight)
            cyclic_dispatcher = dispatcher(cyclic)

            def endless_reflection(event_id, identity, *, area_uid):
                cyclic.executed.append((event_id, identity, area_uid))
                child_uid = max(cyclic.native_effect_areas) + 1
                child = dict(cyclic.native_effect_areas[area_uid], uid=child_uid)
                cyclic.native_effect_areas[child_uid] = child
                policy.post_registration_activation(cyclic_dispatcher, child)
                return (True,)

            cyclic_dispatcher.native_area_events.event = endless_reflection
            with self.assertRaisesRegex(ValueError, "activation budget"):
                policy.post_registration_activation(
                    cyclic_dispatcher, cyclic.native_effect_areas[50]
                )
            self.assertLessEqual(len(cyclic.executed), 128)
            self.assertFalse(cyclic.native_encounter_area_activation["draining"])
            self.assertEqual(fight.native_encounter_area_activation["delivered"], [])
            # An active pointer change cannot alter an already frozen fight.
            with self.store.connection() as db:
                db.execute("DELETE FROM encounter_area_activation_active")
            self.assertEqual(
                policy.post_registration_activation(
                    dispatcher(retried), retried.native_effect_areas[50]
                ),
                (),
            )
            fresh = deepcopy(unrelated)
            del fresh.native_encounter_area_activation
            self.assertIsNone(policy.freeze_encounter_area_policy(fresh, roles=roles))
