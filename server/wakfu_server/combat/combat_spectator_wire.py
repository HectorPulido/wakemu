"""Native cva/12044 spectator bootstrap envelope.

The inherited portion is the exact cvb/12847 fight bootstrap. The trailing
phase byte is native `fbZ`, and the final length-prefixed bytes restore the
client timeline (`feM.dT`). The timeline bytes must be a snapshot from the
current live fight, not its initial state or an event replay.
"""
import struct
from collections.abc import Mapping

from protocol_codec import Reader
from .combat_wire import bootstrap, _blob, _read_blob


def decode_spectator_request(body):
    """Decode coL/13413 and cpg/12154: a single signed i32 fight ID."""
    reader = Reader(body)
    fight_id = reader.number("i")
    reader.finish()
    if fight_id <= 0:
        raise ValueError("Invalid spectator fight ID")
    return fight_id


def timeline_snapshot(period, *, actor_entries=(), fYZ_entries=None, fZb_entries=None):
    """Encode the current `feN` timeline snapshot consumed by `feM.dT`.

    The section names mirror native getters. Each actor tuple is `(actor_id,
    counter, rK_flag)`; event lists carry native `eVn.aZE()` integer IDs. This
    is a state snapshot, not a sequence of combat events.
    """
    if type(period) is not int or not 0 < period < 2**31:
        raise ValueError("Invalid native timeline period")
    actor_entries = tuple(actor_entries)
    if len(actor_entries) > 127:
        raise ValueError("Too many timeline actor entries")
    out = bytearray(struct.pack(">iB", period, len(actor_entries)))
    seen_actors = set()
    for entry in actor_entries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 3:
            raise ValueError("Invalid timeline actor entry")
        actor_id, counter, rK_flag = entry
        if (
            type(actor_id) is not int
            or actor_id == 0
            or not -(2**63) <= actor_id < 2**63
            or type(counter) is not int
            or not -(2**31) <= counter < 2**31
            or type(rK_flag) is not bool
            or actor_id in seen_actors
        ):
            raise ValueError("Invalid or duplicate timeline actor entry")
        seen_actors.add(actor_id)
        out.extend(struct.pack(">qiB", actor_id, counter, int(rK_flag)))

    def append_map(entries):
        if entries is None:
            entries = {}
        if not isinstance(entries, Mapping) or len(entries) > 127:
            raise ValueError("Invalid timeline event map")
        if any(
            type(key) is not int or not -(2**31) <= key < 2**31 for key in entries
        ):
            raise ValueError("Invalid timeline event map key")
        out.append(len(entries))
        for key, values in sorted(entries.items()):
            values = tuple(values)
            if len(values) > 127 or any(
                type(value) is not int or not -(2**31) <= value < 2**31
                for value in values
            ):
                raise ValueError("Invalid native timeline event list")
            out.extend(struct.pack(">iB", key, len(values)))
            for value in values:
                out.extend(struct.pack(">i", value))

    append_map(fYZ_entries)
    append_map(fZb_entries)
    return bytes(out)


def decode_timeline_snapshot(body):
    reader = Reader(body)
    value = {"period": reader.number("i")}
    if value["period"] <= 0:
        raise ValueError("Invalid native timeline period")
    count = reader.number("B")
    value["actor_entries"] = []
    seen = set()
    for _ in range(count):
        actor_id, counter, flag = (reader.number(fmt) for fmt in ("q", "i", "B"))
        if actor_id == 0 or flag not in (0, 1) or actor_id in seen:
            raise ValueError("Invalid timeline actor entry")
        seen.add(actor_id)
        value["actor_entries"].append((actor_id, counter, bool(flag)))

    def read_map():
        count = reader.number("B")
        entries = {}
        for _ in range(count):
            key = reader.number("i")
            length = reader.number("B")
            if key in entries:
                raise ValueError("Duplicate timeline event map key")
            entries[key] = [reader.number("i") for _ in range(length)]
        return entries

    value["fYZ_entries"] = read_map()
    value["fZb_entries"] = read_map()
    reader.finish()
    return value


def spectator_bootstrap(value, *, phase_code, timeline_snapshot):
    if type(phase_code) is not int or phase_code not in range(6):
        raise ValueError("Unknown native fbZ spectator phase")
    if not isinstance(timeline_snapshot, bytes) or not timeline_snapshot:
        raise ValueError("Current native timeline snapshot is required")
    decode_timeline_snapshot(timeline_snapshot)
    body = bootstrap(value) + struct.pack(">b", phase_code)
    body += _blob(timeline_snapshot, "i")
    return 12044, body


def _decode_bootstrap_prefix(reader):
    value = {
        key: reader.number(fmt)
        for key, fmt in (
            ("fight_id", "i"),
            ("kind", "b"),
            ("bqh", "q"),
            ("myo", "q"),
            ("myp", "q"),
        )
    }
    value.update(myD=_read_blob(reader, "i"), myG=_read_blob(reader, "h"))
    value["myI"] = reader.number("q")
    value["myJ"] = reader.number("q")
    compact = reader.number("B")
    if compact not in (0, 1):
        raise ValueError("Invalid compact flag")
    value["compact"] = bool(compact)
    count = reader.number("b")
    if count < 0:
        raise ValueError("Negative participant count")
    actors = []
    for _ in range(count):
        actor = {
            key: reader.number(fmt)
            for key, fmt in (
                ("actor_id", "q"),
                ("myB", "b"),
                ("myn", "b"),
                ("myC", "b"),
            )
        }
        if not value["compact"]:
            actor["myE"] = _read_blob(reader, "h")
            actor["myF"] = _read_blob(reader, "h")
        actors.append(actor)
    value["participants"] = actors
    for key in ("myH", "myM", "myN"):
        count = reader.number("b")
        if count < 0:
            raise ValueError("Negative fight list count")
        value[key] = [
            (reader.number("b"), reader.number("q"))
            if key == "myH"
            else reader.number("b")
            for _ in range(count)
        ]
    count = reader.number("i")
    if count < 0 or count > len(reader.data) // 4:
        raise ValueError("Invalid fight section count")
    value["myK"] = [_read_blob(reader, "i") for _ in range(count)]
    return value


def decode_spectator_bootstrap(body):
    reader = Reader(body)
    value = _decode_bootstrap_prefix(reader)
    value["phase_code"] = reader.number("b")
    if value["phase_code"] not in range(6):
        raise ValueError("Unknown native fbZ spectator phase")
    value["timeline_snapshot"] = _read_blob(reader, "i")
    if not value["timeline_snapshot"]:
        raise ValueError("Missing native timeline snapshot")
    value["timeline"] = decode_timeline_snapshot(value["timeline_snapshot"])
    reader.finish()
    return value
