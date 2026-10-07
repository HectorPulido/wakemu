"""End-to-end weather transition smoke for a disposable candidate world.

Run inside a candidate `world` container after the candidate has applied its
migrations. The DB-name guard prevents connecting this script to a runtime DB.
It creates two TLS sessions in different native territories, advances one
explicit transition through the authenticated scheduler API, verifies regional
delivery and reconnection bootstrap, and checks the real planting probability
resolver against the updated authoritative weather row.
"""
from datetime import datetime, timedelta, timezone
import json
import math
import os
import secrets
import socket
import ssl
import struct
import string
import time
import urllib.request

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.ecology_context import packet as ecology_packet
from wakfu_server.planting_probability import resolver
from wakfu_server.store import Store
from wakfu_server.territory_weather import save, schedule_transition
from wakfu_server.territory_weather_forecast import (
    encode_packet as encode_forecast,
    packet_for_territory,
    save_policy as save_forecast_policy,
)


MAP_ID = 1134
INSTANCE_ID = secrets.randbelow(2**31 - 1) + 1
REGION_A = 79201
REGION_B = 79001
POSITION_A = (-15, -140, 50)  # Native plantable surface, resource 263 climate.
POSITION_B = (54, 36, 17)  # Native planting surface inside REGION_B.


def _text(value):
    raw = value.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        raw = socket.create_connection(("127.0.0.1", 15556), timeout=10)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        self.socket.settimeout(20)
        self.history = []

    def send(self, opcode, body=b""):
        self.socket.sendall(_frame(opcode, body))

    def exact(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                raise AssertionError("Candidate weather TLS socket closed")
            data.extend(chunk)
        return bytes(data)

    def receive(self, *, timeout=10):
        self.socket.settimeout(timeout)
        size = struct.unpack(">I", self.exact(4))[0]
        if not 6 <= size <= 327670:
            raise AssertionError("Malformed candidate server frame")
        frame = self.exact(size - 4)
        packet = struct.unpack_from(">H", frame)[0], frame[2:]
        self.history.append(packet)
        return packet

    def until(self, opcode, *, timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            packet = self.receive(timeout=max(0.1, deadline - time.monotonic()))
            if packet[0] == opcode:
                return packet[1]
        raise AssertionError(f"Missing native packet {opcode}")

    def weather_since(self, start, expected, *, timeout=15):
        self.packet_since(start, 13948, expected, timeout=timeout)

    def packet_since(self, start, packet_opcode, expected, *, timeout=15):
        deadline = time.monotonic() + timeout
        cursor = start
        while time.monotonic() < deadline:
            for opcode, body in self.history[cursor:]:
                if opcode == packet_opcode and body == expected:
                    return
            cursor = len(self.history)
            self.receive(timeout=max(0.1, deadline - time.monotonic()))
        raise AssertionError(f"Expected native packet {packet_opcode} was not received")

    def assert_no_packet_change(self, start, packet_opcode, expected, *, seconds=2):
        deadline = time.monotonic() + seconds
        cursor = start
        while time.monotonic() < deadline:
            for opcode, body in self.history[cursor:]:
                if opcode == packet_opcode and body != expected:
                    raise AssertionError(
                        f"A different region's packet {packet_opcode} was broadcast"
                    )
            cursor = len(self.history)
            try:
                self.receive(timeout=min(0.2, max(0.05, deadline - time.monotonic())))
            except (TimeoutError, socket.timeout):
                pass
        for opcode, body in self.history[start:]:
            if opcode == packet_opcode and body != expected:
                raise AssertionError(
                    f"A different region's packet {packet_opcode} was broadcast"
                )

    def assert_no_weather_change(self, start, expected, *, seconds=2):
        deadline = time.monotonic() + seconds
        cursor = start
        while time.monotonic() < deadline:
            for opcode, body in self.history[cursor:]:
                if opcode == 13948 and body != expected:
                    raise AssertionError("A different territory's update was broadcast")
            cursor = len(self.history)
            try:
                self.receive(timeout=min(0.2, max(0.05, deadline - time.monotonic())))
            except (TimeoutError, socket.timeout):
                pass
        for opcode, body in self.history[start:]:
            if opcode == 13948 and body != expected:
                raise AssertionError("A different territory's update was broadcast")

    def close(self):
        try:
            self.socket.close()
        except OSError:
            pass


def _payload(region_id, weather_id):
    return struct.pack(
        ">qb6fi", region_id, 0, 12.5, 13.5, 0.25, 0.5, 1.0, 2.0, weather_id
    )


def _forecast_policy(sample, weather):
    return (
        [
            dict(
                season=1,
                temperature_sample_a=sample,
                temperature_sample_b=sample + 1,
                wind_strength_u16=120,
                weather=weather,
                temperature_adjustment_sample=2,
                signed_weather_modifier_i16=-3,
            )
        ],
        [
            dict(
                season=1,
                actual_minimum_adjustment=-2,
                actual_maximum_adjustment=3,
            )
        ],
    )


def _login(store, account_id, character, client_label):
    generation = store.begin_session(account_id)
    ticket = store.issue_token(account_id, "ticket", generation=generation, realm_id=10)
    peer = Peer()
    mark = len(peer.history)
    peer.send(426, _text(ticket) + _text(client_label))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    peer.send(12449)
    peer.until(12436)
    return peer, generation, mark


def _tick_through_api(token, occurrence):
    request = urllib.request.Request(
        "http://127.0.0.1:18081/test/tasks/territory_weather_tick",
        data=json.dumps({"request_id": occurrence}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.load(response)
    if result.get("status") != "completed":
        raise AssertionError("Weather scheduler callback did not complete")


def main():
    database_url = os.environ["WAKFU_DATABASE_URL"]
    database_name = conninfo_to_dict(database_url).get("dbname", "")
    if not database_name.startswith("wakemu_candidate_"):
        raise ValueError("Weather smoke requires a disposable candidate database")
    store = Store(
        database_url,
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    peers = []
    forecast_baseline_only = os.environ.get("WAKEMU_FORECAST_BASELINE_ONLY") == "1"
    try:
        initial_a = _payload(REGION_A, 1)  # LIGHT
        initial_b = _payload(REGION_B, 2)  # HEAVY
        clear_forecast = encode_forecast([], [])
        forecast_days_v1, forecast_seasons_v1 = _forecast_policy(12, "LIGHT")
        save_forecast_policy(
            store,
            map_id=MAP_ID,
            instance_id=INSTANCE_ID,
            region_id=REGION_A,
            policy_version=1,
            days=forecast_days_v1,
            season_adjustments=forecast_seasons_v1,
        )
        forecast_a_v1 = packet_for_territory(
            store, map_id=MAP_ID, instance_id=INSTANCE_ID, region_id=REGION_A
        )
        save(
            store,
            map_id=MAP_ID,
            instance_id=INSTANCE_ID,
            region_id=REGION_A,
            payload=initial_a,
        )
        save(
            store,
            map_id=MAP_ID,
            instance_id=INSTANCE_ID,
            region_id=REGION_B,
            payload=initial_b,
        )

        account_a = store.register(
            "weather_a_" + secrets.token_hex(4), secrets.token_urlsafe(24)
        )["id"]
        account_b = store.register(
            "weather_b_" + secrets.token_hex(4), secrets.token_urlsafe(24)
        )["id"]
        character_a = store.create_character(
            account_a,
            "WxA" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(6)),
            breed=8,
        )
        character_b = store.create_character(
            account_b,
            "WxB" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(6)),
            breed=8,
        )
        with store.connection() as db:
            for character, position in (
                (character_a, POSITION_A),
                (character_b, POSITION_B),
            ):
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (MAP_ID, INSTANCE_ID, *position, character["id"]),
                )

        peer_a, generation_a, mark_a = _login(
            store, account_a, character_a, "weather-territory-a"
        )
        peer_b, _, mark_b = _login(store, account_b, character_b, "weather-territory-b")
        peers.extend((peer_a, peer_b))
        peer_a.weather_since(mark_a, initial_a)
        peer_b.weather_since(mark_b, initial_b)
        peer_a.packet_since(mark_a, 13895, forecast_a_v1)
        peer_b.packet_since(mark_b, 13895, clear_forecast)
        if not forecast_baseline_only:
            ecology_a = ecology_packet(
                store,
                {
                    **character_a,
                    "map_id": MAP_ID,
                    "instance_id": INSTANCE_ID,
                    "x": POSITION_A[0],
                    "y": POSITION_A[1],
                    "z": POSITION_A[2],
                },
                open_test_policy=os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1",
            )[1]
            ecology_b = ecology_packet(
                store,
                {
                    **character_b,
                    "map_id": MAP_ID,
                    "instance_id": INSTANCE_ID,
                    "x": POSITION_B[0],
                    "y": POSITION_B[1],
                    "z": POSITION_B[2],
                },
                open_test_policy=os.environ.get("WAKFU_OPEN_PLANTING", "1") == "1",
            )[1]
            peer_a.packet_since(mark_a, 12789, ecology_a)
            peer_b.packet_since(mark_b, 12789, ecology_b)
        peer_a.assert_no_weather_change(0, initial_a, seconds=0.5)
        peer_b.assert_no_weather_change(0, initial_b, seconds=0.5)
        peer_b.assert_no_packet_change(0, 13895, clear_forecast, seconds=0.5)

        # The actual planting resolver reads the exact DB territory row. A
        # heavy-climate resource on this surface has 56% under LIGHT and 70%
        # under STORM with zero bonus, matching the local configured formula.
        planting_resolver = resolver(store, profession_bonus=lambda _prepared: 0)
        prepared = {
            "character": {"map_id": MAP_ID, "instance_id": INSTANCE_ID},
            "request": {"x": POSITION_A[0], "y": POSITION_A[1]},
            "z": POSITION_A[2],
            "definition": {"resource_reference": 263, "family_id": 1},
        }
        before = planting_resolver(prepared)
        if not math.isclose(before, 0.56, rel_tol=0, abs_tol=1e-9):
            raise AssertionError("Planting did not read the initial territory climate")

        scheduler_token = store.issue_token(account_a, "scheduler")
        update_mark_a = len(peer_a.history)
        update_mark_b = len(peer_b.history)
        forecast_days_v2, forecast_seasons_v2 = _forecast_policy(18, "STORM")
        save_forecast_policy(
            store,
            map_id=MAP_ID,
            instance_id=INSTANCE_ID,
            region_id=REGION_A,
            policy_version=2,
            days=forecast_days_v2,
            season_adjustments=forecast_seasons_v2,
        )
        forecast_a_v2 = packet_for_territory(
            store, map_id=MAP_ID, instance_id=INSTANCE_ID, region_id=REGION_A
        )
        transition_at = datetime.now(timezone.utc) + timedelta(seconds=2)
        schedule_transition(
            store,
            map_id=MAP_ID,
            instance_id=INSTANCE_ID,
            region_id=REGION_A,
            transition_at=transition_at,
            target_weather="STORM",
        )
        while datetime.now(timezone.utc) <= transition_at:
            time.sleep(0.05)
        _tick_through_api(
            scheduler_token,
            "territory_weather_tick:weather-smoke-" + secrets.token_hex(4),
        )
        changed_a = _payload(REGION_A, 3)
        peer_a.weather_since(update_mark_a, changed_a)
        peer_a.packet_since(update_mark_a, 13895, forecast_a_v2)
        peer_b.assert_no_weather_change(update_mark_b, initial_b, seconds=1.5)
        peer_b.assert_no_packet_change(
            update_mark_b, 13895, clear_forecast, seconds=1.5
        )
        after = planting_resolver(prepared)
        if not math.isclose(after, 0.70, rel_tol=0, abs_tol=1e-9):
            raise AssertionError(
                "Planting probability did not follow the updated territory weather"
            )

        peer_a.close()
        peers.remove(peer_a)
        peer_a, generation_a, reconnect_mark = _login(
            store, account_a, character_a, "weather-territory-a-reconnect"
        )
        peers.append(peer_a)
        peer_a.weather_since(reconnect_mark, changed_a)
        peer_a.packet_since(reconnect_mark, 13895, forecast_a_v2)
        if not forecast_baseline_only:
            peer_a.packet_since(reconnect_mark, 12789, ecology_a)
        with store.connection() as db:
            rows = db.execute(
                "SELECT region_id,weather,revision FROM territory_weather "
                "WHERE map_id=%s AND instance_id=%s ORDER BY region_id",
                (MAP_ID, INSTANCE_ID),
            ).fetchall()
            outbox = db.execute(
                "SELECT published_at,superseded_at FROM territory_weather_outbox "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s AND revision=2",
                (MAP_ID, INSTANCE_ID, REGION_A),
            ).fetchone()
            forecast_outbox = db.execute(
                "SELECT published_at,superseded_at FROM territory_weather_forecast_outbox "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s AND policy_version=2",
                (MAP_ID, INSTANCE_ID, REGION_A),
            ).fetchone()
        state = {row["region_id"]: (row["weather"], row["revision"]) for row in rows}
        if state.get(REGION_A) != ("STORM", 2) or state.get(REGION_B) != ("HEAVY", 1):
            raise AssertionError("Weather transition escaped its territory scope")
        if outbox is None or outbox["published_at"] is None:
            raise AssertionError(
                "The transitioned weather snapshot was not acknowledged"
            )
        if forecast_outbox is None or forecast_outbox["published_at"] is None:
            raise AssertionError("The updated forecast snapshot was not acknowledged")
        scope = "12789/13948/13895" if not forecast_baseline_only else "13948/13895"
        print(
            f"PASS: two-region TLS bootstrap {scope}, forecast clear, "
            "scoped updates, reconnect and planting resolver"
        )
        if forecast_baseline_only:
            print(
                "NOTE: 12789 ecology assertions skipped for pre-region_context baseline"
            )
    finally:
        for peer in peers:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
