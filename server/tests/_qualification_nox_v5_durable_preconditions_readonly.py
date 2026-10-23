"""Inspect durable admission prerequisites without registering or writing a fight."""
import json
from pathlib import Path
import sys
import unittest


class ReadDurablePreconditions(unittest.TestCase):
    def runTest(self):
        m = sys.modules["test_nox_full_party_victory_v5"]
        r = m.retained_components[0]
        nv = r["authorized_scoped_policy_transition_verifier"]
        before = nv(r)
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rb = cp["authorized_service_transition_verifier"]()
        c = r["case"]
        store = r["fixture"].store
        ids = list(c.characters)
        accounts = [c.characters[i]["account_id"] for i in ids]
        with store.connection() as db:
            fight = db.execute(
                "SELECT * FROM combat_fights WHERE id=%s", (c.fight.id,)
            ).fetchone()
            participants = db.execute(
                "SELECT * FROM combat_fight_participants WHERE fight_id=%s",
                (c.fight.id,),
            ).fetchall()
            sessions = db.execute(
                "SELECT account_id,character_id,generation,expires_at FROM sessions WHERE account_id=ANY(%s) ORDER BY account_id",
                (accounts,),
            ).fetchall()
        facts = dict(
            fight_id=c.fight.id,
            durable_fight=fight,
            durable_participants=participants,
            sessions=sessions,
            case_keys=list(vars(c)),
            record_keys=list(r),
            construction=c.construction,
            character_ids=ids,
            account_ids=accounts,
            case_generation_fields={
                key: value for key, value in vars(c).items() if "generation" in key
            },
            no_writes=True,
            no_registry_admission=True,
            verification_before=before,
            verification_after=nv(r),
            rushu_verification_before=rb,
            rushu_verification_after=cp["authorized_service_transition_verifier"](),
        )
        Path(
            ".runtime/parallel-readiness-20261021/nox-v5-current-store-durable-admission-preconditions-readonly.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadDurablePreconditions()])
