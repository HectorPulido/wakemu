"""Incremental private capture reader and strict running-effect delivery matching."""
import base64, json, struct


class CaptureTail:
    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.pending = b""
        self.buffers = {}
        self.metadata = {}
        self.frame = 0

    def read(self):
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            chunk = stream.read()
            self.offset = stream.tell()
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        rows = []
        for line in lines:
            if not line:
                continue
            r = json.loads(line)
            direction = r.get("direction")
            stage = r.get("stage", "")
            if "payload_base64" not in r or r.get("remote", "").rsplit(":", 1)[
                -1
            ] not in ("5556", "5558", "15556", "15558"):
                continue
            if not (
                (direction == "in" and stage == "aCl#0")
                or (direction == "out" and stage == "SslHandler#0")
            ):
                continue
            key = (r["channel"], direction)
            buffer = self.buffers.setdefault(key, bytearray())
            if not buffer:
                self.metadata[key] = r
            buffer.extend(base64.b64decode(r["payload_base64"]))
            while len(buffer) >= 4:
                length = struct.unpack_from(">I", buffer)[0]
                if not 6 <= length <= 327670:
                    raise ValueError("Invalid native capture frame")
                if len(buffer) < length:
                    break
                frame = bytes(buffer[:length])
                del buffer[:length]
                self.frame += 1
                header = 6 if direction == "in" else 7
                origin = self.metadata[key]
                rows.append(
                    dict(
                        frame=self.frame,
                        direction=direction,
                        channel=r["channel"],
                        time=origin["time"],
                        opcode=struct.unpack_from(
                            ">H", frame, 4 if direction == "in" else 5
                        )[0],
                        body=frame[header:],
                    )
                )
                self.metadata[key] = r
        return rows


def integer_fields(data):
    i = 0
    out = {}

    def varint():
        nonlocal i
        value = shift = 0
        while i < len(data) and shift < 70:
            byte = data[i]
            i += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
            shift += 7
        raise ValueError("Truncated protobuf varint")

    while i < len(data):
        tag = varint()
        key, wire = tag >> 3, tag & 7
        if wire == 0:
            out[key] = varint()
        elif wire == 2:
            length = varint()
            i += length
        elif wire == 1:
            i += 8
        elif wire == 5:
            i += 4
        else:
            raise ValueError("Unsupported protobuf wire type")
        if i > len(data):
            raise ValueError("Truncated protobuf message")
    return out


def owned_delivery(row, *, fight_id, action_id, actor_ids):
    if row["direction"] != "in" or row["opcode"] not in (12613, 13497, 13560):
        return False
    body = row["body"]
    if len(body) < 19 or struct.unpack_from(">ii", body) != (fight_id, action_id):
        return False
    if row["opcode"] == 12613:
        size = struct.unpack_from(">h", body, 17)[0]
        payload = body[19 : 19 + size]
    else:
        size = struct.unpack_from(">h", body, 16)[0]
        payload = body[18 : 18 + size]
    values = integer_fields(payload)
    actors = {
        v - (1 << 64) if v >= (1 << 63) else v for k, v in values.items() if k in (6, 7)
    }
    return bool(actors & set(actor_ids))


def native_cast_branch(row, *, fight_id, action_id, actor_id, spell_id, target):
    """Original cwa12588/cwb12678 layouts; match identity before reading flags."""
    if row["direction"] != "in" or row["opcode"] not in (12588, 12678):
        return None
    body = row["body"]
    opcode = row["opcode"]
    if len(body) < 20 or struct.unpack_from(">ii", body) != (fight_id, action_id):
        return None
    if struct.unpack_from(">q", body, 12)[0] != actor_id:
        return None
    if opcode == 12588:
        if len(body) < 49:
            return None
        reference = struct.unpack_from(">i", body, 28)[0]
        failed = body[38]
        if failed not in (0, 1) or len(body) != (49 if failed else 50):
            return None
        critical = None if failed else body[39]
        coords = struct.unpack_from(">iih", body, 39 if failed else 40)
    else:
        if len(body) != 50:
            return None
        critical, failed = body[24:26]
        reference = struct.unpack_from(">i", body, 34)[0]
        coords = struct.unpack_from(">iih", body, 40)
    if reference != spell_id or list(coords) != list(target):
        return None
    if failed not in (0, 1) or critical not in (None, 0, 1):
        return None
    return dict(
        opcode=opcode,
        critical=None if critical is None else bool(critical),
        failed=bool(failed),
        frame=row.get("frame"),
        time=row.get("time"),
    )


def native_item_branch(row, *, fight_id, action_id, actor_id, item_reference, target):
    """cvO13509 owned item animation, including normal/critical branch."""
    if row["direction"] != "in" or row["opcode"] != 13509:
        return None
    body = row["body"]
    if len(body) != 39 or struct.unpack_from(">ii", body) != (fight_id, action_id):
        return None
    if (
        struct.unpack_from(">q", body, 12)[0] != actor_id
        or struct.unpack_from(">i", body, 20)[0] != item_reference
    ):
        return None
    is_spell, failed, critical = body[26:29]
    if is_spell != 0 or failed not in (0, 1) or critical not in (0, 1):
        return None
    if list(struct.unpack_from(">iih", body, 29)) != list(target):
        return None
    return dict(
        opcode=13509,
        critical=bool(critical),
        failed=bool(failed),
        frame=row.get("frame"),
        time=row.get("time"),
    )
