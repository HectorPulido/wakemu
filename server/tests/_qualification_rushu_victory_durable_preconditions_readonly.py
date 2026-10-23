"""Read durable prerequisites for the already-earned native Rushu result."""
import json
from pathlib import Path
import sys
import unittest


class ReadRushuDurablePreconditions(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        nr = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        rv, nv = (
            cp["authorized_service_transition_verifier"],
            nr["authorized_scoped_policy_transition_verifier"],
        )
        before = rv()
        nv(nr)
        fight, store = cp["runtime"].fight, cp["store"]
        ids = list(cp["characters"])
        accounts = [cp["characters"][i]["account_id"] for i in ids]
        rng = cp["rng"].getstate()
        with store.connection() as db:
            durable = db.execute(
                "SELECT * FROM combat_fights WHERE id=%s", (fight.id,)
            ).fetchone()
            participants = db.execute(
                "SELECT * FROM combat_fight_participants WHERE fight_id=%s", (fight.id,)
            ).fetchall()
            sessions = db.execute(
                "SELECT account_id,character_id,generation,expires_at FROM sessions WHERE account_id=ANY(%s) ORDER BY account_id",
                (accounts,),
            ).fetchall()
        facts = dict(
            fight_id=fight.id,
            durable_fight=durable,
            durable_participants=participants,
            sessions=sessions,
            checkpoint_keys=list(cp),
            fixture_keys=list(vars(cp["fixture"])),
            generation_fields={k: v for k, v in cp.items() if "generation" in k},
            character_ids=ids,
            account_ids=accounts,
            no_writes=True,
            no_registry_admission=True,
            verification_before=before,
            verification_after=rv(),
        )
        self.assertEqual(cp["rng"].getstate(), rng)
        nv(nr)
        Path(
            ".runtime/parallel-readiness-20261021/rushu-current-store-durable-admission-preconditions-readonly.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadRushuDurablePreconditions()])
