"""Actual shared entry points batch verified cache fills across one operation."""
import unittest
from unittest.mock import patch

import test_combat_shared as shared_fixtures
import test_retained_replay_metadata_batch as catalog_fixtures
from wakfu_server.native_cache_fill_batch import verified_cache_fill_scope, _ACTIVE


class SharedCacheFillScopeTests(unittest.TestCase):
    def test_player_and_server_success_error_and_nested_scopes(self):
        for server in (False, True):
            for fail in (False, True):
                with self.subTest(server=server, fail=fail):
                    case = shared_fixtures.SharedCombatTests()
                    case.setUp()
                    case.fight.ready(1)
                    if server:
                        case.fight.end_turn(1, 10, case.fight.turn_id)
                        self.assertEqual(case.fight.current.id, -200)
                    data = catalog_fixtures.RetainedReplayMetadataBatchTests().fixture(
                        size=3
                    )
                    redis = data.reader.backend.redis_provider()
                    original_fight = case.shared.fight
                    original_publication = case.registry._prepare_publication
                    publications = []
                    with patch.object(redis, "execute", wraps=redis.execute) as writes:

                        def operation(candidate, runtime):
                            data.reader["1"]
                            with verified_cache_fill_scope():
                                data.reader["2"]
                            self.assertEqual(writes.call_count, 0)
                            candidate.actors[10].hp = 55
                            if fail:
                                raise ValueError("action rejected")
                            return ((12873, b"accepted"),)

                        def publication(*args, **kwargs):
                            data.reader["3"]
                            publications.append(True)
                            self.assertEqual(writes.call_count, 0)
                            return original_publication(*args, **kwargs)

                        def execute():
                            if server:
                                return case.registry.execute_server(
                                    99,
                                    -200,
                                    operation,
                                    expected_sequence=case.shared.sequence,
                                )
                            return case.registry.execute(99, case.one, 10, operation)

                        with patch.object(
                            case.registry,
                            "_prepare_publication",
                            side_effect=publication,
                        ):
                            if fail:
                                with self.assertRaisesRegex(
                                    ValueError, "action rejected"
                                ):
                                    execute()
                            else:
                                execute()
                        self.assertEqual(writes.call_count, 1)
                    self.assertIsNone(_ACTIVE.get())
                    if fail:
                        self.assertIs(case.shared.fight, original_fight)
                        self.assertEqual(case.shared.fight.actors[10].hp, 60)
                        self.assertFalse(publications)
                        self.assertFalse(case.shared.outboxes[1])
                    else:
                        self.assertIsNot(case.shared.fight, original_fight)
                        self.assertEqual(case.shared.fight.actors[10].hp, 55)
                        self.assertEqual(publications, [True])
                        self.assertEqual(
                            case.registry.drain(99, case.one)[0].packets,
                            ((12873, b"accepted"),),
                        )
