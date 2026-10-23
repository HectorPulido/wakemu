"""Native environmental wire boundaries and post-commit connection fencing."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.objectives import environmental_world as publication
from wakfu_server.objectives import environmental_service


class EnvironmentalWorldPublicationTests(unittest.TestCase):
    def test_historical_result_hydrates_present_completed_context_then_restores_current_instance(
        self,
    ):
        for old_challenge, current_challenge in ((-2311, -2312), (-2311, -2311)):
            with self.subTest(old=old_challenge, current=current_challenge):
                location = dict(map_id=527, instance_id=0, region_id=5)
                store = SimpleNamespace(
                    current_character_session=Mock(return_value=True)
                )
                world = SimpleNamespace(
                    send_batch_to=Mock(return_value=True),
                    scope_presence=Mock(return_value=1),
                )
                current = dict(
                    instance_id=202,
                    active_objectives=[9002],
                    native_scenario_id=current_challenge,
                    protector_id=5,
                    started_at_ms=1000,
                    deadline_ms=9000,
                    now_ms=4000,
                    challenge_value=2,
                    available=True,
                    variables=[dict(variable_index=0, value=2)],
                    native_publication=dict(
                        challenge_id=current_challenge,
                        secondary_id=77,
                        native_time=600,
                        protector_id=5,
                        state_ordinal=1,
                        variable_names=["count"],
                    ),
                )
                old = dict(
                    instance_id=101,
                    active_objectives=[9001],
                    native_scenario_id=old_challenge,
                    protector_id=5,
                    started_at_ms=1000,
                    deadline_ms=3000,
                    now_ms=4000,
                    challenge_value=20,
                    available=False,
                    variables=[dict(variable_index=0, value=20)],
                    native_publication=dict(
                        challenge_id=old_challenge,
                        secondary_id=77,
                        native_time=600,
                        protector_id=5,
                        state_ordinal=2,
                        variable_names=["count"],
                    ),
                )
                result_packet = (
                    13263,
                    struct.pack(">iibihi", old_challenge, 77, 0, 20, 0, 1),
                )
                delivery = dict(
                    delivery_key="completed:101:17",
                    instance_id=101,
                    character_id=17,
                    kind="completed",
                    result_view=old,
                    packets=[result_packet],
                )
                snapshot = dict(instances=[current], deliveries=[])
                original = deepcopy((current, old, delivery))
                connection = publication.SelectedEnvironmentalEvents()
                checkpoint = Mock()
                with patch.object(
                    environmental_service, "refresh", return_value=snapshot
                ), patch.object(environmental_service, "acknowledge") as ack:
                    # The current context is already cached. A historical result
                    # must still restore it, even for another cycle of the same
                    # challenge where the public challenge ID cannot disambiguate.
                    self.assertTrue(
                        connection.refresh(
                            store,
                            world,
                            2,
                            "lease",
                            17,
                            location=location,
                            ready=True,
                            checkpoint=checkpoint,
                        )
                    )
                    world.send_batch_to.reset_mock()
                    ack.assert_not_called()
                    snapshot["deliveries"] = [delivery]
                    world.send_batch_to.return_value = False
                    self.assertFalse(
                        connection.refresh(
                            store,
                            world,
                            2,
                            "lease",
                            17,
                            location=location,
                            ready=True,
                            checkpoint=checkpoint,
                        )
                    )
                    packets = world.send_batch_to.call_args.args[2]
                    self.assertEqual(
                        [opcode for opcode, _ in packets],
                        [12549, 13955, 13263, 12549, 13955],
                    )
                    self.assertEqual(packets[2], result_packet)
                    old_header = struct.unpack(">biiiqiiBi", packets[0][1])
                    current_header = struct.unpack(">biiiqiiBi", packets[3][1])
                    self.assertEqual(
                        old_header, (1, old_challenge, 77, 0, 1000, 5, 20, 1, 9001)
                    )
                    self.assertEqual(
                        current_header,
                        (1, current_challenge, 77, 5000, 1000, 5, 2, 1, 9002),
                    )
                    # Presence stays true for the completed old challenge;
                    # raw gameplay availability=False must not clear its UI.
                    self.assertEqual(packets[0][1][29], 1)
                    ack.assert_not_called()
                    world.send_batch_to.return_value = True
                    self.assertTrue(
                        connection.refresh(
                            store,
                            world,
                            2,
                            "lease",
                            17,
                            location=location,
                            ready=True,
                            checkpoint=checkpoint,
                        )
                    )
                    self.assertEqual(world.send_batch_to.call_args.args[2], packets)
                    ack.assert_called_once_with(
                        store, 2, "lease", 17, ["completed:101:17"]
                    )
                    snapshot["deliveries"] = []
                    world.send_batch_to.reset_mock()
                    self.assertFalse(
                        connection.refresh(
                            store,
                            world,
                            2,
                            "lease",
                            17,
                            location=location,
                            ready=True,
                            checkpoint=checkpoint,
                        )
                    )
                    world.send_batch_to.assert_not_called()
                self.assertEqual((current, old, delivery), original)

    def test_seven_original_packet_layouts_and_signed_bounds(self):
        fields = dict(
            state=1,
            challenge_id=-2311,
            secondary_id=23,
            remaining_ms=999,
            native_time=456,
            protector_id=5,
            challenge_value=7,
            available=True,
            variables=[999],
            objective_ids=[8, -9],
        )
        opcode, body = publication.initial_packet(**fields)
        self.assertEqual((opcode, len(body)), (12549, 38))
        self.assertEqual(
            struct.unpack(">biiiqiiBii", body), (1, -2311, 23, 999, 456, 5, 7, 1, 8, -9)
        )
        self.assertEqual(
            publication.status_packet(
                state=2, secondary_id=23, remaining_ms=0, native_time=456
            ),
            (12276, struct.pack(">biiq", 2, 23, 0, 456)),
        )
        self.assertEqual(
            publication.variable_packet(-2311, 127, 2**40),
            (12124, struct.pack(">ibq", -2311, 127, 2**40)),
        )
        self.assertEqual(
            publication.objective_packet(-2311, 55),
            (13538, struct.pack(">ii", -2311, 55)),
        )
        self.assertEqual(
            publication.notification_packet(-2311), (12175, struct.pack(">i", -2311))
        )
        self.assertEqual(
            publication.challenge_value_packet(-5), (12361, struct.pack(">i", -5))
        )
        packet = publication.challenge_list_packet(
            -2311, [1, -2], [dict(variable_index=127, value=2**40)], optional_value=9
        )
        self.assertEqual(
            packet,
            (
                13955,
                struct.pack(">ibii bii bq", -2311, 2, 1, -2, 1, 9, 1, 127, 2**40),
            ),
        )
        self.assertEqual(
            publication.challenge_list_packet(-1, [], []),
            (13955, struct.pack(">ibbi", -1, 0, 0, 0)),
        )
        for fields in (
            dict(state=-1, secondary_id=0, remaining_ms=0, native_time=0),
            dict(state=1, secondary_id=0, remaining_ms=-1, native_time=0),
        ):
            with self.assertRaises(ValueError):
                publication.status_packet(**fields)
        for count in (128,):
            with self.assertRaises(ValueError):
                publication.challenge_list_packet(1, [0] * count, [])
        with self.assertRaises(ValueError):
            publication.variable_packet(1, True, 0)
        with self.assertRaises(ValueError):
            publication.challenge_list_packet(
                1, [], [dict(variable_index=0, value=1)] * 2
            )

    def test_reconnect_countdown_failed_send_retry_ack_and_scope_checkpoint(self):
        actor = 17
        location = dict(map_id=527, instance_id=0, region_id=5, x=1, y=2, z=0)
        instance = dict(
            instance_id=101,
            active_objectives=[],
            native_scenario_id=-2311,
            protector_id=5,
            started_at_ms=1000,
            deadline_ms=3000,
            now_ms=1000,
            challenge_value=3,
            available=True,
            variables=[dict(variable_index=0, value=2)],
            native_publication=dict(
                challenge_id=-2311,
                secondary_id=77,
                native_time=0,
                protector_id=5,
                state_ordinal=1,
                variable_names=["count"],
            ),
        )
        snapshot = dict(
            instances=[instance],
            entitlements=[],
            deliveries=[
                dict(
                    delivery_key="earned:101:17",
                    packets=[(13873, b"committed absolute state")],
                )
            ],
        )
        store = SimpleNamespace(current_character_session=Mock(return_value=True))
        world = SimpleNamespace(
            send_batch_to=Mock(return_value=False), scope_presence=Mock(return_value=1)
        )
        checkpoint = Mock()
        connection = publication.SelectedEnvironmentalEvents()
        with patch.object(
            environmental_service, "refresh", return_value=snapshot
        ) as refresh, patch.object(environmental_service, "acknowledge") as ack:
            self.assertFalse(
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    actor,
                    location=location,
                    ready=False,
                    checkpoint=checkpoint,
                )
            )
            refresh.assert_not_called()
            self.assertFalse(
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    actor,
                    location=location,
                    ready=True,
                    checkpoint=checkpoint,
                )
            )
            ack.assert_not_called()
            world.send_batch_to.return_value = True
            self.assertTrue(
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    actor,
                    location=location,
                    ready=True,
                    checkpoint=checkpoint,
                )
            )
            self.assertEqual(world.send_batch_to.call_args.args[2][0][0], 12549)
            ack.assert_called_once_with(store, 2, "lease", actor, ["earned:101:17"])
            self.assertEqual(
                checkpoint.call_count, 2
            )  # Retry retains no unpublished cursor.
            snapshot["deliveries"] = []
            instance["now_ms"] = 1500
            world.send_batch_to.reset_mock()
            self.assertFalse(
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    actor,
                    location=dict(location, x=2),
                    ready=True,
                    checkpoint=checkpoint,
                )
            )
            self.assertEqual(checkpoint.call_count, 2)
            world.send_batch_to.assert_not_called()
            # A new connection reconstructs the current remaining duration.
            reconnect = publication.SelectedEnvironmentalEvents()
            reconnect.refresh(
                store,
                world,
                2,
                "new lease",
                actor,
                location=location,
                ready=True,
                checkpoint=checkpoint,
            )
            packet = world.send_batch_to.call_args.args[2][0]
            self.assertEqual(
                (packet[0], struct.unpack_from(">i", packet[1], 9)[0]), (12549, 1500)
            )
            store.current_character_session.side_effect = [True, False]
            ack.reset_mock()
            snapshot["deliveries"] = [
                dict(delivery_key="later", packets=[(13873, b"new")])
            ]
            with self.assertRaisesRegex(ValueError, "changed after"):
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    actor,
                    location=location,
                    ready=True,
                    checkpoint=checkpoint,
                )
            ack.assert_not_called()

    def test_unqualified_profiles_and_ambiguous_display_never_fabricate_a_challenge(
        self,
    ):
        store = SimpleNamespace(current_character_session=Mock(return_value=True))
        world = SimpleNamespace(
            send_batch_to=Mock(return_value=True), scope_presence=Mock(return_value=1)
        )
        location = dict(map_id=527, instance_id=0, region_id=None, x=1, y=2, z=0)
        connection = publication.SelectedEnvironmentalEvents()
        snapshot = dict(
            instances=[dict(native_publication=None)], entitlements=[], deliveries=[]
        )
        with patch.object(
            environmental_service, "refresh", return_value=snapshot
        ), patch.object(environmental_service, "acknowledge"):
            self.assertFalse(
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    17,
                    location=location,
                    ready=True,
                    checkpoint=Mock(),
                )
            )
            world.send_batch_to.assert_not_called()
            instance = dict(
                active_objectives=[],
                native_scenario_id=-2311,
                protector_id=5,
                started_at_ms=1000,
                deadline_ms=3000,
                now_ms=1000,
                challenge_value=3,
                available=True,
                variables=[dict(variable_index=0, value=2)],
                native_publication=dict(
                    challenge_id=-2311,
                    secondary_id=77,
                    native_time=0,
                    protector_id=5,
                    state_ordinal=1,
                    variable_names=["count"],
                ),
            )
            snapshot["instances"] = [instance, deepcopy(instance)]
            with self.assertRaisesRegex(ValueError, "Multiple environmental"):
                connection.refresh(
                    store,
                    world,
                    2,
                    "lease",
                    17,
                    location=location,
                    ready=True,
                    checkpoint=Mock(),
                )
            world.send_batch_to.assert_not_called()

    def test_60_groups_218_monsters_progress_without_replaying_title_or_started_toast(
        self,
    ):
        location = dict(map_id=327, instance_id=0, region_id=56601)
        actor, challenge, secondary = 17, -1329, 77
        instance = dict(
            instance_id=101,
            active_objectives=[9101, 9102],
            native_scenario_id=challenge,
            protector_id=56601,
            started_at_ms=1000,
            deadline_ms=601000,
            now_ms=1000,
            challenge_value=0,
            available=True,
            variables=[
                dict(variable_index=i, value=v) for i, v in enumerate((218, 60, 0, 0))
            ],
            native_publication=dict(
                challenge_id=challenge,
                secondary_id=secondary,
                native_time=600,
                protector_id=56601,
                state_ordinal=1,
                variable_names=[
                    "nbMobSpawned",
                    "nbGroupSpawned",
                    "nbMobGlobal",
                    "nbGroupGlobal",
                ],
            ),
        )
        snapshot = dict(instances=[instance], deliveries=[])
        store = SimpleNamespace(current_character_session=Mock(return_value=True))
        world = SimpleNamespace(
            send_batch_to=Mock(return_value=True), scope_presence=Mock(return_value=1)
        )
        connection = publication.SelectedEnvironmentalEvents()
        checkpoint = Mock()

        def refresh(cursor=connection, generation="lease"):
            return cursor.refresh(
                store,
                world,
                2,
                generation,
                actor,
                location=location,
                ready=True,
                checkpoint=checkpoint,
            )

        def packets():
            return world.send_batch_to.call_args.args[2]

        with patch.object(
            environmental_service, "refresh", return_value=snapshot
        ), patch.object(environmental_service, "acknowledge") as ack:
            self.assertTrue(refresh())
            self.assertEqual([op for op, _ in packets()], [12549, 13955])
            first_header = struct.unpack(">biiiqiiBii", packets()[0][1])
            self.assertEqual(
                first_header,
                (1, challenge, secondary, 600000, 1000, 56601, 0, 1, 9101, 9102),
            )
            self.assertEqual(
                packets()[1],
                publication.challenge_list_packet(
                    challenge,
                    [9101, 9102],
                    [
                        dict(variable_index=i, value=v)
                        for i, v in enumerate((218, 60, 0, 0))
                    ],
                ),
            )
            # Sixty physical groups account for exactly 218 original monsters;
            # three/four members per group gives 22*3 + 38*4 = 218.
            group_ends, total = set(), 0
            for size in [3] * 22 + [4] * 38:
                total += size
                group_ends.add(total)
            defeated_groups = 0
            progress_packets = []
            for killed in range(1, 219):
                previous_groups = defeated_groups
                defeated_groups += killed in group_ends
                instance["variables"][2]["value"] = killed
                instance["variables"][3]["value"] = defeated_groups
                instance["challenge_value"] = killed
                instance["now_ms"] += 1000
                if killed == 17:
                    # A committed durable delivery stays pending when its
                    # write fails; the publication cursor must retry deltas too.
                    snapshot["deliveries"] = [
                        dict(
                            delivery_key="absolute:101:17",
                            packets=[
                                (13873, b"already committed absolute character state")
                            ],
                        )
                    ]
                    world.send_batch_to.return_value = False
                    self.assertFalse(refresh())
                    failed = packets()
                    ack.assert_not_called()
                    world.send_batch_to.return_value = True
                    self.assertTrue(refresh())
                    self.assertEqual(packets(), failed)
                    ack.assert_called_once_with(
                        store, 2, "lease", actor, ["absolute:101:17"]
                    )
                    snapshot["deliveries"] = []
                else:
                    self.assertTrue(refresh())
                batch = packets()
                self.assertNotIn(
                    12549,
                    [op for op, _ in batch],
                    "Per-monster progress must not restart the title",
                )
                self.assertNotIn(
                    12276,
                    [op for op, _ in batch],
                    "ACTIVE refresh must not repeat the started toast",
                )
                deltas = {
                    index: value
                    for op, body in batch
                    if op == 12124
                    for _, index, value in [struct.unpack(">ibq", body)]
                }
                expected = {2: killed}
                if defeated_groups != previous_groups:
                    expected[3] = defeated_groups
                self.assertEqual(deltas, expected)
                self.assertEqual(
                    [struct.unpack(">i", body)[0] for op, body in batch if op == 12361],
                    [killed],
                )
                progress_packets.extend(
                    (op, body) for op, body in batch if op in (12124, 12361)
                )
                world.send_batch_to.reset_mock()
                instance["now_ms"] += 1
                self.assertFalse(
                    refresh(), "The native timer advances locally between state changes"
                )
                world.send_batch_to.assert_not_called()
            self.assertEqual(defeated_groups, 60)
            self.assertEqual(sum(op == 12124 for op, _ in progress_packets), 218 + 60)
            self.assertEqual(sum(op == 12361 for op, _ in progress_packets), 218)
            self.assertEqual(checkpoint.call_count, 1)
            # A genuine durable deadline correction is distinct from a clock
            # tick. The client receives exactly one remaining-time correction.
            instance["deadline_ms"] += 7000
            self.assertTrue(refresh())
            self.assertEqual([op for op, _ in packets()], [12276])
            self.assertEqual(
                struct.unpack(">biiq", packets()[0][1]),
                (1, secondary, instance["deadline_ms"] - instance["now_ms"], 1000),
            )
            instance["now_ms"] += 1
            world.send_batch_to.reset_mock()
            self.assertFalse(refresh())
            world.send_batch_to.assert_not_called()
            # Completion is a real state change, so publish its status once.
            # Native results still flow only from the durable delivery.
            instance["native_publication"]["state_ordinal"] = 2
            result = (13263, struct.pack(">iibihi", challenge, secondary, 0, 218, 0, 1))
            snapshot["deliveries"] = [
                dict(
                    delivery_key="completed:101:17",
                    kind="completed",
                    instance_id=101,
                    character_id=actor,
                    result_view=deepcopy(instance),
                    packets=[result],
                )
            ]
            self.assertTrue(refresh())
            self.assertEqual([op for op, _ in packets()], [13263])
            ack.assert_called_with(store, 2, "lease", actor, ["completed:101:17"])
            completed_view = deepcopy(instance)
            snapshot["deliveries"] = []
            instance["now_ms"] += 500
            world.send_batch_to.reset_mock()
            self.assertFalse(refresh())
            world.send_batch_to.assert_not_called()
            # A reconnect receives one complete context with current remaining
            # time. A fresh active cycle of the same public challenge ID needs
            # a new initialization instead of a countdown/status restart.
            reconnect = publication.SelectedEnvironmentalEvents()
            self.assertTrue(refresh(reconnect, "new-lease"))
            self.assertEqual([op for op, _ in packets()], [12549, 13955])
            self.assertEqual(
                struct.unpack_from(">i", packets()[0][1], 9)[0],
                instance["deadline_ms"] - instance["now_ms"],
            )
            next_cycle = deepcopy(instance)
            next_cycle["instance_id"] = 202
            next_cycle["native_publication"]["state_ordinal"] = 1
            next_cycle["variables"][2]["value"] = 0
            next_cycle["variables"][3]["value"] = 0
            next_cycle["challenge_value"] = 0
            next_cycle["deadline_ms"] = next_cycle["now_ms"] + 600000
            snapshot["instances"] = [next_cycle]
            self.assertTrue(refresh(reconnect, "new-lease"))
            self.assertEqual([op for op, _ in packets()], [12549, 13955])
            world.send_batch_to.reset_mock()
            self.assertFalse(refresh(reconnect, "new-lease"))
            world.send_batch_to.assert_not_called()
            # Even identical visible projections can be distinct durable cycles;
            # public challenge ID and counters are insufficient replay guards.
            identical_cycle = deepcopy(next_cycle)
            identical_cycle["instance_id"] = 203
            snapshot["instances"] = [identical_cycle]
            self.assertTrue(refresh(reconnect, "new-lease"))
            self.assertEqual([op for op, _ in packets()], [12549, 13955])
            # An old result may be redelivered after a newer cycle is active.
            # It must hydrate the old context and then restore the current one.
            snapshot["deliveries"] = [
                dict(
                    delivery_key="completed:101:17:reconnect",
                    kind="completed",
                    instance_id=101,
                    character_id=actor,
                    result_view=completed_view,
                    packets=[result],
                )
            ]
            self.assertTrue(refresh(reconnect, "new-lease"))
            self.assertEqual(
                [op for op, _ in packets()], [12549, 13955, 13263, 12549, 13955]
            )
            ack.assert_called_with(
                store, 2, "new-lease", actor, ["completed:101:17:reconnect"]
            )

    def test_earned_result_closes_success_without_failure_header_and_expiry_keeps_failure(
        self,
    ):
        location = dict(map_id=327, instance_id=0, region_id=56601)
        instance = dict(
            instance_id=101,
            active_objectives=[],
            native_scenario_id=-1331,
            protector_id=56601,
            started_at_ms=1000,
            deadline_ms=601000,
            now_ms=1000,
            challenge_value=5,
            available=True,
            variables=[dict(variable_index=0, value=5)],
            native_publication=dict(
                challenge_id=-1331,
                secondary_id=77,
                native_time=600,
                protector_id=56601,
                state_ordinal=1,
                variable_names=["nbMobPlayer"],
            ),
        )
        snapshot = dict(instances=[instance], deliveries=[])
        store = SimpleNamespace(current_character_session=Mock(return_value=True))
        world = SimpleNamespace(
            send_batch_to=Mock(return_value=True), scope_presence=Mock(return_value=1)
        )
        cursor = publication.SelectedEnvironmentalEvents()

        def refresh(selected=cursor, generation="lease"):
            return selected.refresh(
                store,
                world,
                2,
                generation,
                17,
                location=location,
                ready=True,
                checkpoint=Mock(),
            )

        def sent():
            return world.send_batch_to.call_args.args[2]

        result = (13263, struct.pack(">iibihi", -1331, 77, 0, 5, 0, 1))
        with patch.object(
            environmental_service, "refresh", return_value=snapshot
        ), patch.object(environmental_service, "acknowledge") as ack:
            self.assertTrue(refresh())
            self.assertEqual([op for op, _ in sent()], [12549, 13955])
            instance["native_publication"]["state_ordinal"] = 2
            earned = dict(
                delivery_key="completed:101:17",
                kind="completed",
                character_id=17,
                instance_id=101,
                result_view=deepcopy(instance),
                packets=[result],
            )
            snapshot["deliveries"] = [earned]
            world.send_batch_to.return_value = False
            self.assertFalse(refresh())
            self.assertEqual(sent(), (result,))
            ack.assert_not_called()
            world.send_batch_to.return_value = True
            self.assertTrue(refresh())
            self.assertEqual(sent(), (result,))
            ack.assert_called_once_with(store, 2, "lease", 17, ["completed:101:17"])
            # A fresh connection must hydrate the context as RUNNING, then let
            # 13263 mark earned success before its own terminal close. A
            # terminal12549/12276 here would display native failure first.
            reconnect = publication.SelectedEnvironmentalEvents()
            self.assertTrue(refresh(reconnect, "reconnect"))
            self.assertEqual([op for op, _ in sent()], [12549, 13955, 13263])
            self.assertEqual(struct.unpack_from(">b", sent()[0][1])[0], 1)
            snapshot["deliveries"] = []
            instance["now_ms"] += 1000
            world.send_batch_to.reset_mock()
            self.assertFalse(refresh(reconnect, "reconnect"))
            world.send_batch_to.assert_not_called()
            # Redelivery for an older cycle restores the newer context only
            # after its result. Same challenge ID does not identify a cycle.
            later = deepcopy(instance)
            later["instance_id"] = 202
            later["native_publication"]["state_ordinal"] = 1
            snapshot["instances"] = [later]
            self.assertTrue(refresh(reconnect, "reconnect"))
            snapshot["deliveries"] = [earned]
            self.assertTrue(refresh(reconnect, "reconnect"))
            self.assertEqual(
                [op for op, _ in sent()], [12549, 13955, 13263, 12549, 13955]
            )
            self.assertTrue(all(body[0] == 1 for op, body in sent() if op == 12549))
            # A real expiry without an earned result still needs the native
            # terminal/failure state. Do not suppress terminal states globally.
            snapshot["deliveries"] = []
            later["native_publication"]["state_ordinal"] = 2
            self.assertTrue(refresh(reconnect, "reconnect"))
            self.assertEqual([op for op, _ in sent()], [12276])
            self.assertEqual(struct.unpack(">biiq", sent()[0][1])[0], 2)

    def test_native_epoch_start_drives_elapsed_clock_and_survives_late_join_reconnect_and_proposal(
        self,
    ):
        start, duration = 1792720214182, 600000
        location = dict(map_id=327, instance_id=0, region_id=56601)
        instance = dict(
            instance_id=101,
            active_objectives=[],
            native_scenario_id=-1331,
            protector_id=56601,
            started_at_ms=start,
            deadline_ms=start + duration,
            now_ms=start,
            challenge_value=218,
            available=True,
            variables=[dict(variable_index=0, value=218)],
            native_publication=dict(
                challenge_id=-1331,
                secondary_id=77,
                # Historical normalized metadata has zero here. It is not a
                # GregorianCalendar epoch and must not reach cAH's long field.
                native_time=0,
                protector_id=56601,
                state_ordinal=1,
                variable_names=["nbMobSpawned"],
            ),
        )
        snapshot = dict(instances=[instance], deliveries=[])
        store = SimpleNamespace(current_character_session=Mock(return_value=True))
        world = SimpleNamespace(
            send_batch_to=Mock(return_value=True), scope_presence=Mock(return_value=1)
        )
        cursor = publication.SelectedEnvironmentalEvents()

        def refresh(selected=cursor, generation="lease"):
            return selected.refresh(
                store,
                world,
                2,
                generation,
                17,
                location=location,
                ready=True,
                checkpoint=Mock(),
            )

        def sent():
            return world.send_batch_to.call_args.args[2]

        def header(packet):
            self.assertEqual(packet[0], 12549)
            return struct.unpack_from(">biiiqiiB", packet[1])

        def native_elapsed_seconds(initial_header, client_now):
            # Independent consumer contract recovered from cAH -> TP.fl and
            # bhE.E/dlC: epoch0 is empty and leaves the model's fixed duration;
            # a nonempty start enables elapsed wall-clock subtraction. This is
            # a bounded semantic fixture, not execution of the client/JVM.
            epoch = initial_header[4]
            return (
                duration // 1000
                if epoch == 0
                else max(0, (duration - (client_now - epoch)) // 1000)
            )

        with patch.object(
            environmental_service, "refresh", return_value=snapshot
        ), patch.object(environmental_service, "acknowledge") as ack:
            self.assertTrue(refresh())
            self.assertEqual([op for op, _ in sent()], [12549, 13955])
            initial = header(sent()[0])
            self.assertEqual((initial[0], initial[3], initial[4]), (1, 600000, start))
            self.assertEqual(native_elapsed_seconds(initial, start), 600)
            for elapsed, seconds in ((1000, 599), (10000, 590), (150000, 450)):
                instance["now_ms"] = start + elapsed
                world.send_batch_to.reset_mock()
                self.assertFalse(refresh())
                world.send_batch_to.assert_not_called()
                self.assertEqual(
                    native_elapsed_seconds(initial, instance["now_ms"]), seconds
                )
            late = publication.SelectedEnvironmentalEvents()
            self.assertTrue(refresh(late, "late-lease"))
            joined = header(sent()[0])
            self.assertEqual((joined[3], joined[4]), (450000, start))
            self.assertEqual(native_elapsed_seconds(joined, start + 151000), 449)
            instance["now_ms"] = start + 151000
            reconnect = publication.SelectedEnvironmentalEvents()
            self.assertTrue(refresh(reconnect, "reconnect-lease"))
            rejoined = header(sent()[0])
            self.assertEqual((rejoined[3], rejoined[4]), (449000, start))
            self.assertEqual(native_elapsed_seconds(rejoined, start + 200000), 400)
            ack.assert_not_called()
            # A proposed event is bound to its planned durable start, even
            # before RUNNING. The actual transition starts it exactly once.
            planned = start + 220000
            proposed = deepcopy(instance)
            proposed.update(
                instance_id=202,
                started_at_ms=planned,
                deadline_ms=planned + duration,
                countdown_deadline_ms=planned,
                now_ms=planned - 20000,
            )
            proposed["native_publication"]["state_ordinal"] = 0
            snapshot["instances"] = [proposed]
            proposal_cursor = publication.SelectedEnvironmentalEvents()
            self.assertTrue(refresh(proposal_cursor, "proposal-lease"))
            proposal = header(sent()[0])
            self.assertEqual(
                (proposal[0], proposal[3], proposal[4]), (0, 20000, planned)
            )
            proposed["now_ms"] = planned
            proposed["countdown_deadline_ms"] = proposed["deadline_ms"]
            proposed["native_publication"]["state_ordinal"] = 1
            self.assertTrue(refresh(proposal_cursor, "proposal-lease"))
            self.assertEqual([op for op, _ in sent()], [12276])
            self.assertEqual(
                struct.unpack(">biiq", sent()[0][1]), (1, 77, 600000, planned)
            )
            proposed["now_ms"] += 1000
            world.send_batch_to.reset_mock()
            self.assertFalse(refresh(proposal_cursor, "proposal-lease"))
            world.send_batch_to.assert_not_called()
            for invalid in (None, 0, -1, True):
                malformed = deepcopy(instance)
                malformed["started_at_ms"] = invalid
                with self.subTest(started_at_ms=invalid), self.assertRaisesRegex(
                    ValueError, "durable start"
                ):
                    publication._projection(malformed)
