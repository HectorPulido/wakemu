"""Save the native missing-terminal endpoint and already-observed Faille proof."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


class ReadNativeTerminalAndFaille(unittest.TestCase):
    def runTest(self):
        m = sys.modules["test_nox_full_party_victory_v5"]
        r = m.retained_components[0]
        c = r["case"]
        f = c.fight
        before = m.verify_retained_component(r)
        from wakfu_server.fight_checkpoint_store import snapshot

        selected = []
        for ns in ("native_owned_group_effects", "native_retained_records"):
            for uid, row in getattr(f, ns, {}).items():
                inv = (
                    row.get("invocation")
                    if isinstance(row, dict)
                    else getattr(row, "invocation", None)
                )
                ref = (
                    row.get("generic_effect", row.get("reference"))
                    if isinstance(row, dict)
                    else getattr(row, "generic_effect", None)
                ) or (
                    inv.get("reference")
                    if isinstance(inv, dict)
                    else getattr(inv, "reference", None)
                )
                if ref in (401563, 402279, 402280, 402281, 402283, 401564):
                    selected.append(dict(namespace=ns, uid=uid, row=row))
        facts = dict(
            phase=f.phase,
            table=f.native_table_turn,
            turn=f.turn_id,
            current=getattr(f.current, "id", None),
            full_checkpoint=snapshot(f, runtime=c.runtime),
            rng_state=c.rng.getstate(),
            events_tail=getattr(f, "events", [])[-250:],
            runtime_last_native_delivery=getattr(
                c.runtime, "last_native_delivery", None
            ),
            retained_terminal_rows=selected,
            boss_states=[
                dict(
                    uid=e.uid,
                    reference=e.reference,
                    level=e.level,
                    caster=getattr(e, "caster_id", None),
                    effect_ids=getattr(e, "effect_ids", None),
                )
                for e in f.actors[-200].state_ledger.entries
            ],
            no_actions=True,
            verification_before=before,
            verification_after=m.verify_retained_component(r),
            rushu_verification=sys.modules[
                "test_rushu_dd230_eleven_slot_opening"
            ].RUSHU_ACTUAL_CHECKPOINT["authorized_service_transition_verifier"](),
        )
        p = Path(
            ".runtime/parallel-readiness-20261021/nox-v5-earned-score-active-after-end11-terminal-source-readonly.json"
        )
        p.write_text(json.dumps(facts, indent=2, default=str) + "\n")
        raw = Path(
            ".runtime/parallel-readiness-20261021/nox-full-party-v5-equipped-protected-paid-three-million.json"
        )
        d = json.loads(raw.read_text())
        ops = d.get("native_faille_operations", [])
        self.assertTrue(
            any(o["reference"] == 402195 and o["after"] < o["before"] for o in ops)
        )
        self.assertTrue(
            any(o["reference"] == 402212 and o["after"] > o["before"] for o in ops)
        )
        proof = dict(
            source=str(raw),
            source_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
            operations=ops,
            native_gain_and_decay_observed_in_same_paid_encounter=True,
            full_native_victory=False,
            original_errors_preserved=True,
            no_new_gameplay_or_scene=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/nox268-actual-v5-native-gain-and-decay-qualified-sidecar.json"
        ).write_text(json.dumps(proof, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadNativeTerminalAndFaille()])
