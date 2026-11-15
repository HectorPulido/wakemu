"""Frozen PostgreSQL placement duration and a session-local monotonic deadline."""

import math


def duration(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='combat_placement_duration_ms'"
        ).fetchone()
    value = None if row is None else row["value"]
    if type(value) is not int or not 1000 <= value <= 300000:
        raise ValueError("Invalid PostgreSQL placement duration")
    return value


class Deadline:
    def __init__(self):
        self.fight_id = self.until = None

    def start(self, fight_id, duration_ms, now, *, native=False):
        # Captured scripted encounters can publish a ten-minute placement.
        # Ordinary PostgreSQL settings retain their existing five-minute cap.
        maximum = 600000 if native is True else 300000
        if (
            type(fight_id) is not int
            or fight_id <= 0
            or type(duration_ms) is not int
            or type(native) is not bool
            or not 1000 <= duration_ms <= maximum
            or not math.isfinite(now)
        ):
            raise ValueError("Invalid placement deadline")
        self.fight_id = fight_id
        self.until = now + duration_ms / 1000

    def take_expired(self, fight, now):
        if not math.isfinite(now):
            raise ValueError("Invalid placement clock")
        if fight is None or fight.id != self.fight_id or fight.phase != "placement":
            self.fight_id = self.until = None
            return False
        if self.until is None or now < self.until:
            return False
        # Claim once before initialization. A rejected initialization is logged;
        # manual Ready remains available without a retry storm on every packet.
        self.fight_id = self.until = None
        return True
