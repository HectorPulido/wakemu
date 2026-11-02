"""Focused external-participant trust-boundary checks in an isolated QA image."""
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import wakfu_server

from wakfu_server.combat_encounter_scene_external_participant import (
    native_participant_source_digest,
    validate_external_participants,
    declared_external_participant,
)


class RegisteredSummonAuthority:
    def __call__(self, fight, actor):
        return fight.test_facts[actor.id]


def _module(name, **attrs):
    result = ModuleType(f"wakfu_server.{name}")
    result.__dict__.update(attrs)
    return result


def _rule():
    path = Path(
        os.environ.get(
            "POHL_RULE_FILE",
            str(
                Path(__file__).resolve().parents[1]
                / "wakfu_server/combat/native_encounter_scene_compatibility.json"
            ),
        )
    )
    document = json.loads(path.read_text())
    for record in document["records"]:
        for room in record["rooms"]:
            rules = room["encounter_scene"].get("external_event_participants")
            if rules:
                return rules[0]
    raise AssertionError("reviewed external participant source rule missing")


def _fixture(rule, **changes):
    controller_id, child_id, state_uid = -100207, 91, 700001
    controller = SimpleNamespace(id=controller_id, controlled=False)
    child = SimpleNamespace(id=child_id, controlled=False)
    registration = {"caster_id": controller_id, "controller_id": controller_id}
    facts = {
        controller_id: SimpleNamespace(is_player=False, is_summon=False),
        child_id: SimpleNamespace(is_player=False, is_summon=True, native_actor_type=1),
    }
    receipt = {
        "initialized": True,
        "ref": 5376,
        "resolved_states": ({"state_id": rule["controller_state"]},),
    }
    invocation = SimpleNamespace(
        reference=rule["listener_reference"],
        target_id=child_id,
        state_uid=state_uid,
        native_turn_boundary_context={
            "event_id": rule["event_id"],
            "phase": rule["phase"],
        },
        native_trigger_context=None,
    )
    fight = SimpleNamespace(
        actors={controller_id: controller, child_id: child},
        native_summon_registrations={child_id: dict(registration)},
        native_npc_initialization_receipts={controller_id: receipt},
        test_facts=facts,
        native_encounter_scene={"descriptor": {"external_event_participants": [rule]}},
        test_participant=controller,
    )
    values = dict(
        rule=rule,
        controller=controller,
        child=child,
        registration=registration,
        facts=facts,
        receipt=receipt,
        invocation=invocation,
        fight=fight,
        state_uid=state_uid,
        controller_id=controller_id,
        child_id=child_id,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def _dependency_stubs(ctx):
    def frozen_scene(fight):
        return {
            "external_event_participants": fight.native_encounter_scene["descriptor"][
                "external_event_participants"
            ]
        }

    def qualified_boundary_actor(fight, *, turn_context):
        return fight.test_participant

    def state_managers(fight):
        return (
            SimpleNamespace(
                id=ctx.child_id,
                state_ledger=SimpleNamespace(
                    entries=(
                        SimpleNamespace(
                            uid=ctx.state_uid, reference=ctx.rule["receiver_state"]
                        ),
                    )
                ),
            ),
        )

    return {
        "wakfu_server.combat_encounter_scene_policy": _module(
            "combat_encounter_scene_policy", frozen_scene=frozen_scene
        ),
        "wakfu_server.combat_external_turn_recipient": _module(
            "combat_external_turn_recipient",
            qualified_boundary_actor=qualified_boundary_actor,
        ),
        "wakfu_server.combat_summon": _module(
            "combat_summon", RegisteredSummonAuthority=RegisteredSummonAuthority
        ),
        "wakfu_server.combat_state_managers": _module(
            "combat_state_managers",
            state_managers=state_managers,
            state_manager=lambda fight, identity: next(
                row for row in state_managers(fight) if row.id == identity
            ),
        ),
    }


class ExternalParticipantGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rule = _rule()
        # Load and verify the native source closure before scoped dependency
        # stubs are installed by the boundary-only cases below.
        validate_external_participants([cls.rule])

    def test_real_source_digest_validates_and_mutated_digest_rejects(self):
        self.assertEqual(
            native_participant_source_digest(self.rule), self.rule["source_sha256"]
        )
        validated = validate_external_participants([self.rule])
        self.assertEqual(len(validated), 1)
        changed = dict(self.rule, source_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "source changed"):
            validate_external_participants([changed])

    def test_phase_actor_chain_and_noninteger_mutations_reject(self):
        for key, value in (
            ("phase", "start"),
            ("listener_reference", 341737),
            ("controller_references", [5376.0]),
        ):
            with self.subTest(key=key):
                changed = dict(self.rule)
                changed[key] = value
                with self.assertRaises(ValueError):
                    native_participant_source_digest(changed)

    def test_legacy_native_null_trigger_and_nonmatching_participant_stay_unmodified(
        self,
    ):
        ctx = _fixture(self.rule)
        modules = _dependency_stubs(ctx)
        with patch.dict(sys.modules, modules):
            self.assertEqual(
                declared_external_participant(
                    ctx.fight,
                    ctx.invocation,
                    actor_authority=RegisteredSummonAuthority(),
                ),
                ctx.controller_id,
            )
            ctx.invocation.native_trigger_context = {"uid": 123}
            self.assertIsNone(
                declared_external_participant(
                    ctx.fight,
                    ctx.invocation,
                    actor_authority=RegisteredSummonAuthority(),
                )
            )
            ctx.invocation.native_trigger_context = None
            ctx.fight.test_participant = SimpleNamespace(id=-999)
            self.assertIsNone(
                declared_external_participant(
                    ctx.fight,
                    ctx.invocation,
                    actor_authority=RegisteredSummonAuthority(),
                )
            )

    def test_forged_actor_constructor_and_carrier_scope_fail_closed(self):
        cases = (
            (
                "wrong_phase",
                lambda c: setattr(
                    c.invocation,
                    "native_turn_boundary_context",
                    {"event_id": 1002, "phase": "start"},
                ),
            ),
            (
                "unregistered_child",
                lambda c: c.fight.native_summon_registrations.clear(),
            ),
            (
                "wrong_caster",
                lambda c: c.fight.native_summon_registrations[c.child_id].update(
                    caster_id=123
                ),
            ),
            ("player_child", lambda c: setattr(c.child, "controlled", True)),
            ("wrong_constructor", lambda c: c.receipt.update(ref=9999)),
            ("wrong_carrier_uid", lambda c: setattr(c.invocation, "state_uid", 900002)),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                ctx = _fixture(self.rule)
                mutate(ctx)
                with patch.dict(sys.modules, _dependency_stubs(ctx)):
                    if label == "wrong_phase":
                        self.assertIsNone(
                            declared_external_participant(
                                ctx.fight,
                                ctx.invocation,
                                actor_authority=RegisteredSummonAuthority(),
                            )
                        )
                    else:
                        with self.assertRaises(ValueError):
                            declared_external_participant(
                                ctx.fight,
                                ctx.invocation,
                                actor_authority=RegisteredSummonAuthority(),
                            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
