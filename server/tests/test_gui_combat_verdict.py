import unittest, importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "gui_verdict",
    Path(__file__).resolve().parents[2] / "client/tools/gui_combat_verdict.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GuiVerdictTests(unittest.TestCase):
    def evidence(self, **changes):
        expected = dict(actor_id=11, spell_id=5033, target=[1, 0, 0])
        data = dict(
            requests=[dict(expected, opcode=13260)],
            expected=expected,
            server_finished=dict(status="completed", elapsed_ms=20, rejections=[]),
            checks=[dict(passed=True)],
            elapsed_seconds=0.2,
            delivery_seen=True,
        )
        data.update(changes)
        return m.verdict(**data)

    def test_unrelated_spell_or_duplicate_invalidates_even_if_delta_matches(self):
        self.assertEqual(
            self.evidence(
                requests=[
                    dict(actor_id=11, spell_id=5031, target=[1, 0, 0], opcode=13260)
                ]
            ),
            "INVALIDATED_BY_INTERFERENCE",
        )
        request = dict(actor_id=11, spell_id=5033, target=[1, 0, 0], opcode=13260)
        self.assertEqual(
            self.evidence(requests=[request, request]), "INVALIDATED_BY_INTERFERENCE"
        )

    def test_blocked_rejected_no_effect_and_timeout_are_distinct(self):
        for changes, status in (
            (dict(requests=[]), "BLOCKED_CLIENT"),
            (dict(server_finished=None), "TIMEOUT_EXECUTION"),
            (
                dict(server_finished=dict(status="completed", rejections=["LOS"])),
                "REJECTED_SERVER",
            ),
            (dict(checks=[dict(passed=False)]), "NO_EXPECTED_EFFECT"),
            (dict(elapsed_seconds=2.1), "CLIENT_OBSERVATION_TIMEOUT"),
            (dict(delivery_seen=False), "NO_CLIENT_DELIVERY"),
        ):
            self.assertEqual(self.evidence(**changes), status)

    def test_only_expected_stat_delta_counts(self):
        before = {"11": dict(stats={"1": 60, "97": 0})}
        after = {"11": dict(stats={"1": 55, "97": 0})}
        checks = m.expected_changes(
            before, after, [dict(actor_id=11, kind="stat_delta", stat_id=97, value=7)]
        )
        self.assertFalse(checks[0]["passed"])
        self.assertEqual(self.evidence(checks=checks), "NO_EXPECTED_EFFECT")

    def test_pass_requires_matching_native_request_delivery_and_exact_delta(self):
        self.assertEqual(self.evidence(), "PASS")


class GuiDeliveryTests(unittest.TestCase):
    def module(self, name):
        path = Path(__file__).resolve().parents[2] / "client/tools" / name
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_delivery_requires_exact_fight_action_and_actor(self):
        from wakfu_server.combat_effects import direct_damage

        capture = self.module("gui_capture_tail.py")
        row = dict(
            direction="in",
            opcode=12613,
            body=direct_damage(
                78,
                4,
                uid=9,
                generic_effect=361119,
                element=3,
                caster_id=-7,
                target_id=11,
                damage=5,
            ),
        )
        self.assertTrue(
            capture.owned_delivery(row, fight_id=78, action_id=4, actor_ids={11})
        )
        for values in (
            dict(fight_id=79, action_id=4, actor_ids={11}),
            dict(fight_id=78, action_id=5, actor_ids={11}),
            dict(fight_id=78, action_id=4, actor_ids={12}),
        ):
            self.assertFalse(capture.owned_delivery(row, **values))

    def test_incremental_reader_reassembles_split_frame_without_rescanning(self):
        import tempfile, json, base64, struct

        capture = self.module("gui_capture_tail.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("")
            tail = capture.CaptureTail(path)
            packet = struct.pack(">IH", 9, 12613) + b"abc"

            def write(data):
                with path.open("a") as stream:
                    stream.write(
                        json.dumps(
                            dict(
                                direction="in",
                                stage="aCl#0",
                                remote="127.0.0.1:15556",
                                channel="one",
                                time="2026-10-04T00:00:00Z",
                                payload_base64=base64.b64encode(data).decode(),
                            )
                        )
                        + "\n"
                    )

            write(packet[:4])
            self.assertEqual(tail.read(), [])
            write(packet[4:])
            rows = tail.read()
            self.assertEqual(rows[0]["body"], b"abc")
            self.assertEqual(tail.read(), [])

    def test_empty_expectation_configuration_saves_error_report(self):
        import tempfile, json, sys
        from types import SimpleNamespace

        tools = Path(__file__).resolve().parents[2] / "client/tools"
        sys.path.insert(0, str(tools))
        runner = self.module("check-combat-gui.py")
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / "case.json"
            case.write_text(json.dumps({"expectations": []}))
            output = Path(directory) / "output.json"
            self.assertEqual(
                runner.run(
                    SimpleNamespace(
                        case=case,
                        output=output,
                        timeout=1,
                        execution_limit=2,
                        profile="unused",
                    )
                ),
                1,
            )
            self.assertEqual(
                json.loads(output.read_text())["verdict"], "OBSERVATION_ERROR"
            )


class GuiCriticalTests(GuiDeliveryTests):
    def packets(self, critical=True):
        import struct

        header = struct.pack(">iiiq", 78, 4, -1, 11)
        spell = struct.pack(">qih", 5033, 5033, 20)
        cell = struct.pack(">iih", 1, 0, 0)
        return [
            (12588, header + spell + struct.pack(">iBB", 0, 0, critical) + cell),
            (12678, header + struct.pack(">iBB", 5033, critical, 0) + spell + cell),
        ]

    def test_native_flags_match_identity_and_both_packets(self):
        capture = self.module("gui_capture_tail.py")
        for opcode, body in self.packets():
            row = dict(direction="in", opcode=opcode, body=body)
            context = dict(
                fight_id=78, action_id=4, actor_id=11, spell_id=5033, target=[1, 0, 0]
            )
            parsed = capture.native_cast_branch(row, **context)
            self.assertTrue(parsed["critical"])
            self.assertFalse(parsed["failed"])
            for key, value in (
                ("fight_id", 79),
                ("action_id", 5),
                ("actor_id", 12),
                ("spell_id", 5031),
                ("target", [2, 0, 0]),
            ):
                self.assertIsNone(
                    capture.native_cast_branch(row, **dict(context, **{key: value}))
                )
            self.assertIsNone(
                capture.native_cast_branch(dict(row, body=body[:-1]), **context)
            )

    def test_natural_normal_roll_matches_normal_wire_branch(self):
        capture = self.module("gui_capture_tail.py")
        decision = dict(
            critical=False,
            critical_mode="auto",
            critical_chance=3,
            critical_threshold=3,
            critical_roll=75,
        )
        checks = []
        for opcode, body in self.packets(critical=False):
            branch = capture.native_cast_branch(
                dict(direction="in", opcode=opcode, body=body),
                fight_id=78,
                action_id=4,
                actor_id=11,
                spell_id=5033,
                target=[1, 0, 0],
            )
            checks.append(
                dict(
                    passed=branch["critical"] is decision["critical"]
                    and not branch["failed"]
                )
            )
        expected = dict(actor_id=11, spell_id=5033, target=[1, 0, 0])
        self.assertEqual(
            m.verdict(
                requests=[dict(expected, opcode=13260)],
                expected=expected,
                server_finished=dict(status="completed", elapsed_ms=140, rejections=[]),
                checks=[dict(passed=True)],
                elapsed_seconds=1.3,
                delivery_seen=True,
                critical_checks=checks,
            ),
            "PASS",
        )

    def test_critical_text_or_flag_without_expected_damage_never_passes(self):
        expected = dict(actor_id=11, spell_id=5033, target=[1, 0, 0])
        evidence = dict(
            requests=[dict(expected, opcode=13260)],
            expected=expected,
            server_finished=dict(status="completed", elapsed_ms=20, rejections=[]),
            checks=[dict(passed=True)],
            elapsed_seconds=0.2,
            delivery_seen=True,
        )
        self.assertEqual(
            m.verdict(**evidence, critical_checks=[]), "NO_CRITICAL_EVIDENCE"
        )
        self.assertEqual(
            m.verdict(
                **evidence, critical_checks=[dict(passed=True), dict(passed=False)]
            ),
            "WRONG_CRITICAL_BRANCH",
        )
        self.assertEqual(
            m.verdict(
                **dict(evidence, checks=[dict(passed=False)]),
                critical_checks=[dict(passed=True)] * 2
            ),
            "NO_EXPECTED_EFFECT",
        )
        self.assertEqual(
            m.verdict(**evidence, critical_checks=[dict(passed=True)] * 2), "PASS"
        )


class GuiUnarmedTests(GuiDeliveryTests):
    def test_common_unarmed_animation_and_effect_share_correlated_action(self):
        from wakfu_server.combat_melee import animation
        from wakfu_server.combat_effects import direct_damage

        capture = self.module("gui_capture_tail.py")
        animation_row = dict(
            direction="in", opcode=13509, body=animation(78, 4, 11, 20, (1, 0, 0))
        )
        damage_row = dict(
            direction="in",
            opcode=12613,
            body=direct_damage(
                78,
                4,
                uid=9,
                generic_effect=3597,
                element=3,
                caster_id=11,
                target_id=-7,
                damage=4,
            ),
        )
        self.assertIsNotNone(
            capture.native_item_branch(
                animation_row,
                fight_id=78,
                action_id=4,
                actor_id=11,
                item_reference=2145,
                target=[1, 0, 0],
            )
        )
        self.assertTrue(
            capture.owned_delivery(
                damage_row, fight_id=78, action_id=4, actor_ids={11, -7}
            )
        )
        self.assertFalse(
            capture.owned_delivery(
                damage_row, fight_id=78, action_id=5, actor_ids={11, -7}
            )
        )

    def test_unarmed_request_and_native_item_branch_are_exact(self):
        from wakfu_server.combat_melee import animation

        capture = self.module("gui_capture_tail.py")
        row = dict(
            direction="in", opcode=13509, body=animation(78, 4, 11, 20, (1, 0, 0))
        )
        context = dict(
            fight_id=78, action_id=4, actor_id=11, item_reference=2145, target=[1, 0, 0]
        )
        self.assertFalse(capture.native_item_branch(row, **context)["critical"])
        self.assertIsNone(
            capture.native_item_branch(row, **dict(context, item_reference=2027))
        )
        expected = dict(
            request_opcode=12889, actor_id=11, item_uid=-1, target=[1, 0, 0]
        )
        data = dict(
            requests=[dict(expected, opcode=12889)],
            expected=expected,
            server_finished=dict(status="completed", elapsed_ms=20, rejections=[]),
            checks=[dict(passed=True)],
            elapsed_seconds=0.2,
            delivery_seen=True,
            critical_checks=[dict(passed=True)],
        )
        self.assertEqual(m.verdict(**data), "PASS")
        self.assertEqual(
            m.verdict(
                **dict(data, requests=[dict(expected, opcode=12889, item_uid=1000)])
            ),
            "INVALIDATED_BY_INTERFERENCE",
        )


class GuiFieldEvidenceTests(unittest.TestCase):
    def test_optional_getter_failure_does_not_discard_proven_characteristic(self):
        before = {"11": dict(id=11, stats={"1": 84}, error="optional max getter")}
        after = {"11": dict(id=11, stats={"1": 80}, error="optional max getter")}
        checks = m.expected_changes(
            before,
            after,
            [
                dict(
                    actor_id=11, kind="stat_delta_one_of", stat_id=1, value=[-5, -4, -3]
                )
            ],
        )
        self.assertTrue(checks[0]["passed"])
        checks = m.expected_changes(
            before, after, [dict(actor_id=11, kind="stat_delta", stat_id=97, value=7)]
        )
        self.assertFalse(checks[0]["passed"])


class GuiTimingBudgetsTests(unittest.TestCase):
    def test_fast_server_and_slow_client_are_separate(self):
        expected = dict(actor_id=11, spell_id=5033, target=[1, 0, 0])
        data = dict(
            requests=[dict(expected, opcode=13260)],
            expected=expected,
            server_finished=dict(status="completed", elapsed_ms=223, rejections=[]),
            checks=[dict(passed=True)],
            elapsed_seconds=2.1,
            delivery_seen=True,
        )
        self.assertEqual(m.verdict(**data), "CLIENT_OBSERVATION_TIMEOUT")
        self.assertEqual(m.verdict(**data, client_observation_limit_seconds=6), "PASS")
        data["server_finished"]["elapsed_ms"] = 2100
        self.assertEqual(
            m.verdict(**data, client_observation_limit_seconds=6), "TIMEOUT_EXECUTION"
        )


class GuiPreconditionTests(unittest.TestCase):
    def test_actor_identity_life_and_cell_must_remain_verified(self):
        actor = dict(id=-7, position=[1, 0, 0], stats={"1": 84})
        self.assertTrue(m.target_precondition(actor, -7, [1, 0, 0]))
        for changed in (
            dict(id=-8),
            dict(position=[2, 0, 0]),
            dict(stats={"1": 0}),
            dict(stats={}),
        ):
            self.assertFalse(
                m.target_precondition(dict(actor, **changed), -7, [1, 0, 0])
            )

    def test_stable_owned_action_and_changed_turn_are_distinct(self):
        self.assertTrue(
            m.owned_action_precondition(dict(actor_owned=True, fight_phase="ACTION"))
        )
        self.assertFalse(
            m.owned_action_precondition(dict(actor_owned=False, fight_phase="ACTION"))
        )
        self.assertFalse(
            m.owned_action_precondition(dict(actor_owned=True, fight_phase="PLACEMENT"))
        )
