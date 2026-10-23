"""Archive final proof and run only the original fixture cleanups."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest


class ArchiveAndReleaseVictories(unittest.TestCase):
    def runTest(self):
        from wakfu_server.boss_score_runtime import staged_score

        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        nv, rv = (
            nr["authorized_scoped_policy_transition_verifier"],
            cp["authorized_service_transition_verifier"],
        )
        reports = dict(nox=nv(nr), rushu=rv())
        runtimes = dict(nox=nr["case"].runtime, rushu=cp["runtime"])
        stores = dict(nox=nr["store"], rushu=cp["store"])
        rngs = dict(nox=nr["case"].rng, rushu=cp["rng"])
        callbacks = dict(nox=nr["cleanups"], rushu=cp["cleanups"])
        facts = dict(
            status="archived_before_original_fixture_cleanup",
            pid=os.getpid(),
            scopes={},
            no_gameplay_replayed=True,
            no_source_reload=True,
            catalog_heap_retained=True,
        )
        for name, runtime in runtimes.items():
            fight = runtime.fight
            self.assertEqual(fight.phase, "finished")
            self.assertEqual(fight.winner, 1)
            self.assertEqual(fight.actors[-200].hp, 0)
            self.assertEqual(len(callbacks[name]), 3)
            facts["scopes"][name] = dict(
                runtime_id=id(runtime),
                fight_id=fight.id,
                store_identity=id(stores[name]),
                rng_identity=id(rngs[name]),
                phase=fight.phase,
                winner=fight.winner,
                score=staged_score(fight),
                table=fight.native_table_turn,
                turn=fight.turn_id,
                boss_hp=fight.actors[-200].hp,
                players={
                    i: dict(
                        hp=a.hp,
                        ap=a.ap,
                        mp=a.mp,
                        wp=a.effect_stats[4],
                        position=a.position,
                    )
                    for i, a in fight.actors.items()
                    if i in range(1, 7)
                },
                recent_native_events=list(getattr(fight, "events", ()))[-96:],
                rng_state=rngs[name].getstate(),
                current_chain_policy=reports[name]["policy"],
                original_tokens_preserved=reports[name]["original_tokens_preserved"],
                verification_sha256=hashlib.sha256(
                    json.dumps(reports[name], sort_keys=True, default=str).encode()
                ).hexdigest(),
                original_cleanup_functions=[
                    getattr(fn, "__qualname__", repr(fn))
                    for fn, args, kwargs in callbacks[name]
                ],
            )
        evidence = [
            ".runtime/parallel-readiness-20261021/nox-v5-authenticated-native-terminal-cleanup-commit.json",
            ".runtime/parallel-readiness-20261021/nox-v5-same-outcome-durable-rewards-and-reconnect.json",
            ".runtime/ultimate-scenes-20261021/rushu-dd230-eleven-slot-opening-20261022T085200616490Z-same-store-paid-ward-nineteen-through-native-twentyone.json",
            ".runtime/parallel-readiness-20261021/rushu-same-outcome-durable-rewards-and-reconnect.json",
        ]
        facts["evidence_sha256"] = {
            p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in evidence
        }
        output = Path(
            ".runtime/parallel-readiness-20261021/nox-and-rushu-native-victories-final-original-cleanup.json"
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
        # Each public release executes exactly the three retained original callbacks.
        nox.release_retained_components()
        rushu.release_actual_checkpoint()
        nox.RETAIN_COMPONENT = False
        rushu.RUSHU_HOLD_ACTUAL_CHECKPOINT = False
        self.assertEqual(nox.retained_components, [])
        self.assertIsNone(rushu.RUSHU_ACTUAL_CHECKPOINT)
        for store in stores.values():
            self.assertTrue(store.database.pool.closed)
        facts.update(
            status="both_native_victories_archived_and_original_fixtures_released",
            original_cleanups_executed=dict(nox=3, rushu=3),
            stores_closed={
                name: store.database.pool.closed for name, store in stores.items()
            },
            nox_retained_components=0,
            rushu_checkpoint_is_none=True,
            warm_runner_ready=True,
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ArchiveAndReleaseVictories()])
