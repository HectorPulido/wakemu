"""Thin native2706/2707 actions for the existing sole-owner StoryProbe.

Never connects a peer or assigns a quest/item. Ordinary outcomes use the
user-authorized administrative helper and are recorded as administrative.
"""
import struct
import time

from tools.candidate_friendly_duel_socket_smoke import placement
from tools.line3_fields_native_tls_probe import play_administrative
from tools.line4_dialogue_actions import hand_in
from tools.line4_owned_actions import capture, interact, win_room


def _wait(probe, predicate, label, *, mark=0, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe.ack_loads(mark, timeout=0.6)
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(label)


def _generic_transition(probe, source, wire, position, target_map):
    """Send the original action once; server owns the native3000ms ticket."""
    probe.walk(position)
    mark = probe.peer.mark()
    before = probe.current()
    try:
        probe.peer.send(12870, struct.pack(">qHH", source, wire, 0))
        _wait(
            probe,
            lambda: probe.current()["map_id"] == target_map
            and probe.current()["instance_id"] != before["instance_id"],
            ("Native timed transition did not commit", source, wire),
            mark=mark,
        )
        probe.note(
            "actual native timed generic transition",
            source_id=source,
            wire_action=wire,
            native_occupation_ms=3000,
            destination_map=target_map,
        )
    finally:
        capture(probe, mark)


def wet_mission(probe):
    if 5340 in probe.progress()["objectives"]:
        return
    if 2706 not in probe.progress()["running"]:
        raise ValueError("Genuinely earned2706 must be running")
    if probe.current()["instance_id"]:
        raise ValueError("The original well is a public1134 source")
    probe.move_to(1134, (144, 8, 4))
    mark = probe.peer.mark()
    try:
        probe.peer.send(12870, struct.pack(">qHH", 25457, 1, 0))
        fight_id, _ = placement(probe.peer.matching(13652, mark, timeout=45))
        probe.note(
            "actual native well encounter admitted",
            source_id=25457,
            wire_action=1,
            scenario_id=2040,
            fight_id=fight_id,
        )
        play_administrative(probe, fight_id, mark, scope="line4")
        _wait(
            probe,
            lambda: 5340 in probe.progress()["objectives"],
            "Actual well outcome did not earn5340",
            mark=mark,
        )
        probe.note(
            "wet mission earned",
            objective_id=5340,
            fight_id=fight_id,
            administrative_outcome=True,
        )
    finally:
        capture(probe, mark)


def night_mission(probe):
    state = probe.progress()
    if 5341 not in state["objectives"]:
        if 2706 not in state["running"]:
            raise ValueError("Genuinely earned2706 must be running")
        if probe.current()["instance_id"] == 0:
            probe.move_to(1134, (35, 84, 0))
            _generic_transition(probe, 25480, 0, (35, 84, 0), 1004)
        if probe.current()["map_id"] != 1004:
            raise ValueError("Expected the real owned night1004 context")
        current = probe.current()
        event = f"owned-story:astrub-night-1004:{current['instance_id']}:night-watch"
        with probe.store.connection() as db:
            watched = db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (probe.character["id"], event),
            ).fetchone()
        if not watched:
            interact(
                probe,
                25482,
                (1, 1, 0),
                controller_id="astrub-night-1004",
                step="night-watch",
            )
        win_room(probe, 1)
        _wait(
            probe,
            lambda: 5341 in probe.progress()["objectives"],
            "Actual night outcome did not earn5341",
        )
    if probe.current()["map_id"] == 1004 and probe.current()["instance_id"]:
        _generic_transition(probe, 25482, 1, (1, 1, 0), 1134)


def run_wet_night(probe):
    """Resume only remaining real producers, then the separate Magnum report."""
    if 2706 not in probe.progress()["completed"]:
        # A resumed night visit may finish/return before the missing public well.
        if probe.current()["map_id"] == 1004 and probe.current()["instance_id"]:
            night_mission(probe)
        wet_mission(probe)
        night_mission(probe)
    if 2706 not in probe.progress()["completed"]:
        raise AssertionError("Both real2706 producers did not settle completion")
    if probe.current()["map_id"] == 1004 and probe.current()["instance_id"]:
        night_mission(probe)
    hand_in(probe, 2707)
