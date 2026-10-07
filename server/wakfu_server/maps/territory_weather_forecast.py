"""Structured local policy and native codec for forecast packet 13895.

The installed client parser's wire domains are preserved explicitly. Their
units are not documented as upstream physical units, so this module does not
label them Celsius or invent a forecast model. A policy is absent until a
trusted operator configures its day and seasonal rows.
"""
import struct

from .territory_cells import region_at, territories
from .territory_weather import WEATHER

SEASONS = ("WINTER", "SPRING", "SUMMER", "FALL")
MAX_DAYS = 255
_POLICY_FIELDS = {
    "temperature_sample_a",
    "temperature_sample_b",
    "wind_strength_u16",
    "weather",
    "temperature_adjustment_sample",
    "signed_weather_modifier_i16",
    "season",
}
_SEASON_FIELDS = {
    "season",
    "actual_minimum_adjustment",
    "actual_maximum_adjustment",
}


def normalize_policy(days, season_adjustments):
    """Validate named native fields and return canonical ordered records."""
    if type(days) is not list or len(days) > MAX_DAYS:
        raise ValueError("Invalid local weather forecast day list")
    if type(season_adjustments) is not list or len(season_adjustments) > 4:
        raise ValueError("Invalid local weather forecast seasons")

    normalized_days = []
    for offset, row in enumerate(days, 1):
        if type(row) is not dict or set(row) not in (
            _POLICY_FIELDS,
            _POLICY_FIELDS | {"day_offset"},
        ):
            raise ValueError("Invalid local weather forecast day fields")
        if "day_offset" in row and (
            type(row["day_offset"]) is not int or row["day_offset"] != offset
        ):
            raise ValueError("Forecast day offsets must be contiguous")
        season = row["season"]
        if type(season) is not int or not 0 <= season < len(SEASONS):
            raise ValueError("Invalid local weather forecast season")
        a = _i8(row["temperature_sample_a"])
        b = _i8(row["temperature_sample_b"])
        strength = row["wind_strength_u16"]
        if type(strength) is not int or not 0 <= strength <= 65535:
            raise ValueError("Invalid forecast wind-strength wire value")
        weather = row["weather"]
        if type(weather) is not str or weather not in WEATHER:
            raise ValueError("Invalid forecast weather enum")
        adjustment = _i8(row["temperature_adjustment_sample"])
        modifier = row["signed_weather_modifier_i16"]
        if type(modifier) is not int or not -32768 <= modifier <= 32767:
            raise ValueError("Invalid forecast signed modifier wire value")
        normalized_days.append(
            dict(
                day_offset=offset,
                season=season,
                temperature_sample_a=a,
                temperature_sample_b=b,
                wind_strength_u16=strength,
                weather=weather,
                temperature_adjustment_sample=adjustment,
                signed_weather_modifier_i16=modifier,
            )
        )

    normalized_seasons = []
    used = {row["season"] for row in normalized_days}
    seen = set()
    for row in season_adjustments:
        if type(row) is not dict or set(row) != _SEASON_FIELDS:
            raise ValueError("Invalid forecast seasonal adjustment fields")
        season = row["season"]
        if type(season) is not int or not 0 <= season < len(SEASONS):
            raise ValueError("Invalid forecast seasonal adjustment season")
        if season in seen:
            raise ValueError("Duplicate forecast seasonal adjustment")
        seen.add(season)
        normalized_seasons.append(
            dict(
                season=season,
                actual_minimum_adjustment=_i8(row["actual_minimum_adjustment"]),
                actual_maximum_adjustment=_i8(row["actual_maximum_adjustment"]),
            )
        )
    if not used.issubset(seen):
        raise ValueError("Forecast day is missing seasonal adjustment values")
    normalized_seasons.sort(key=lambda row: row["season"])
    return normalized_days, normalized_seasons


def encode_body(days, season_adjustments):
    """Encode bRV.fe body. Uses no opaque or prebuilt payload fields."""
    days, season_adjustments = normalize_policy(days, season_adjustments)
    body = bytearray((len(days),))
    for row in days:
        body.extend(
            struct.pack(
                ">BbbHibh",
                row["season"],
                row["temperature_sample_a"],
                row["temperature_sample_b"],
                row["wind_strength_u16"],
                WEATHER.index(row["weather"]),
                row["temperature_adjustment_sample"],
                row["signed_weather_modifier_i16"],
            )
        )
    body.append(len(season_adjustments))
    for row in season_adjustments:
        body.extend(
            struct.pack(
                ">Bbb",
                row["season"],
                row["actual_minimum_adjustment"],
                row["actual_maximum_adjustment"],
            )
        )
    # bRV.fe consumes two three-byte placeholders when fewer than two season
    # entries are supplied. Zero padding is structural, not forecast content.
    for _ in range(max(0, 2 - len(season_adjustments))):
        body.extend(b"\x00\x00\x00")
    return bytes(body)


def encode_packet(days, season_adjustments):
    """Return cBl envelope (u16 body length plus a bRV.fe body)."""
    body = encode_body(days, season_adjustments)
    if len(body) > 65535:
        raise ValueError("Weather forecast exceeds native envelope capacity")
    return struct.pack(">H", len(body)) + body


def decode_packet(packet):
    """Strictly decode the native cBl envelope and bRV.fe structured body."""
    if type(packet) is not bytes or len(packet) < 3:
        raise ValueError("Invalid native weather forecast envelope")
    declared = struct.unpack_from(">H", packet)[0]
    if declared != len(packet) - 2:
        raise ValueError("Invalid native weather forecast envelope length")
    body = memoryview(packet)[2:]
    count = body[0]
    offset = 1
    days = []
    for day_offset in range(1, count + 1):
        if offset + 12 > len(body):
            raise ValueError("Truncated native weather forecast row")
        season, a, b, wind, weather_id, adjustment, modifier = struct.unpack_from(
            ">BbbHibh", body, offset
        )
        offset += 12
        if season >= len(SEASONS) or weather_id < 0 or weather_id >= len(WEATHER):
            raise ValueError("Unknown native weather forecast enum")
        days.append(
            dict(
                day_offset=day_offset,
                season=season,
                temperature_sample_a=a,
                temperature_sample_b=b,
                wind_strength_u16=wind,
                weather=WEATHER[weather_id],
                temperature_adjustment_sample=adjustment,
                signed_weather_modifier_i16=modifier,
            )
        )
    if offset >= len(body):
        raise ValueError("Missing native forecast seasonal adjustment count")
    season_count = body[offset]
    offset += 1
    if season_count > len(SEASONS) or offset + season_count * 3 > len(body):
        raise ValueError("Invalid native forecast seasonal adjustment count")
    seasons = []
    seen = set()
    for _ in range(season_count):
        season, low, high = struct.unpack_from(">Bbb", body, offset)
        offset += 3
        if season >= len(SEASONS) or season in seen:
            raise ValueError("Invalid native forecast seasonal adjustment")
        seen.add(season)
        seasons.append(
            dict(
                season=season,
                actual_minimum_adjustment=low,
                actual_maximum_adjustment=high,
            )
        )
    offset += max(0, 2 - season_count) * 3
    if offset != len(body):
        raise ValueError("Unexpected bytes after native weather forecast")
    days, seasons = normalize_policy(days, seasons)
    return {"days": days, "season_adjustments": seasons}


def save_policy(
    store, *, map_id, region_id, policy_version, days, season_adjustments, instance_id
):
    """Persist a trusted, instance-scoped policy and outbox version atomically."""
    if type(map_id) is not int or type(region_id) is not int:
        raise ValueError("Invalid local forecast territory")
    if (map_id, region_id) not in set(territories()):
        raise ValueError("Unknown local forecast territory")
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid local forecast instance")
    if type(policy_version) is not int or not 1 <= policy_version <= 2**31 - 1:
        raise ValueError("Invalid local forecast policy version")
    day_rows, season_rows = normalize_policy(days, season_adjustments)
    with store.connection() as db:
        # The conditional upsert serializes even the first concurrent insert.
        # SELECT ... FOR UPDATE cannot lock a row that does not exist, so two
        # first writers could otherwise install versions out of order.
        accepted = db.execute(
            "INSERT INTO territory_weather_forecast_policy "
            "(map_id,instance_id,region_id,policy_version,source) "
            "VALUES(%s,%s,%s,%s,'LOCAL_POLICY') "
            "ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET "
            "policy_version=EXCLUDED.policy_version,source='LOCAL_POLICY',"
            "updated_at=clock_timestamp() "
            "WHERE territory_weather_forecast_policy.policy_version "
            "< EXCLUDED.policy_version RETURNING policy_version",
            (map_id, instance_id, region_id, policy_version),
        ).fetchone()
        if accepted is None:
            raise ValueError("Forecast policy version must increase")
        db.execute(
            "DELETE FROM territory_weather_forecast_days "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region_id),
        )
        db.execute(
            "DELETE FROM territory_weather_forecast_season_adjustments "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region_id),
        )
        for row in day_rows:
            db.execute(
                "INSERT INTO territory_weather_forecast_days "
                "(map_id,instance_id,region_id,day_offset,season,temperature_sample_a,"
                "temperature_sample_b,wind_strength_u16,weather,"
                "temperature_adjustment_sample,signed_weather_modifier_i16) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    map_id,
                    instance_id,
                    region_id,
                    row["day_offset"],
                    row["season"],
                    row["temperature_sample_a"],
                    row["temperature_sample_b"],
                    row["wind_strength_u16"],
                    row["weather"],
                    row["temperature_adjustment_sample"],
                    row["signed_weather_modifier_i16"],
                ),
            )
        for row in season_rows:
            db.execute(
                "INSERT INTO territory_weather_forecast_season_adjustments "
                "(map_id,instance_id,region_id,season,actual_minimum_adjustment,"
                "actual_maximum_adjustment) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    map_id,
                    instance_id,
                    region_id,
                    row["season"],
                    row["actual_minimum_adjustment"],
                    row["actual_maximum_adjustment"],
                ),
            )
        db.execute(
            "INSERT INTO territory_weather_forecast_outbox "
            "(map_id,instance_id,region_id,policy_version) VALUES(%s,%s,%s,%s)",
            (map_id, instance_id, region_id, policy_version),
        )
    return dict(
        map_id=map_id,
        instance_id=instance_id,
        region_id=region_id,
        policy_version=policy_version,
        days=len(day_rows),
        seasons=len(season_rows),
    )


def packet_for_territory(store, *, map_id, instance_id, region_id, policy_version=None):
    """Build 13895 for exact map/instance/region; no policy means clear packet."""
    if type(map_id) is not int or type(region_id) is not int:
        raise ValueError("Invalid forecast territory")
    if (map_id, region_id) not in set(territories()):
        raise ValueError("Unknown local forecast territory")
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid local forecast instance")
    with store.connection() as db:
        policy = db.execute(
            "SELECT policy_version FROM territory_weather_forecast_policy "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s FOR SHARE",
            (map_id, instance_id, region_id),
        ).fetchone()
        if policy is None:
            return encode_packet([], [])
        if policy_version is not None and policy["policy_version"] != policy_version:
            raise ValueError("Weather forecast policy was superseded")
        rows = db.execute(
            "SELECT day_offset,season,temperature_sample_a,temperature_sample_b,"
            "wind_strength_u16,weather,temperature_adjustment_sample,"
            "signed_weather_modifier_i16 FROM territory_weather_forecast_days "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s ORDER BY day_offset",
            (map_id, instance_id, region_id),
        ).fetchall()
        seasons = db.execute(
            "SELECT season,actual_minimum_adjustment,actual_maximum_adjustment "
            "FROM territory_weather_forecast_season_adjustments "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s ORDER BY season",
            (map_id, instance_id, region_id),
        ).fetchall()
    day_rows = [dict(row) for row in rows]
    if [row["day_offset"] for row in day_rows] != list(range(1, len(day_rows) + 1)):
        raise ValueError("Non-contiguous local forecast day offsets")
    day_policy = [{key: row[key] for key in _POLICY_FIELDS} for row in day_rows]
    season_policy = [dict(row) for row in seasons]
    return encode_packet(day_policy, season_policy)


def pending_publications(store, *, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid forecast publication batch size")
    with store.connection() as db:
        db.execute(
            "UPDATE territory_weather_forecast_outbox o "
            "SET superseded_at=clock_timestamp() "
            "FROM territory_weather_forecast_policy p "
            "WHERE o.map_id=p.map_id AND o.instance_id=p.instance_id "
            "AND o.region_id=p.region_id AND o.policy_version<>p.policy_version "
            "AND o.published_at IS NULL AND o.superseded_at IS NULL"
        )
        return [
            dict(row)
            for row in db.execute(
                "SELECT o.map_id,o.instance_id,o.region_id,o.policy_version "
                "FROM territory_weather_forecast_outbox o "
                "JOIN territory_weather_forecast_policy p USING(map_id,instance_id,region_id) "
                "WHERE o.published_at IS NULL AND o.superseded_at IS NULL "
                "AND o.policy_version=p.policy_version "
                "ORDER BY o.created_at,o.map_id,o.instance_id,o.region_id "
                "LIMIT %s",
                (limit,),
            ).fetchall()
        ]


def acknowledge_publication(store, event):
    _validate_event(event)
    with store.connection() as db:
        row = db.execute(
            "UPDATE territory_weather_forecast_outbox o "
            "SET published_at=clock_timestamp() FROM territory_weather_forecast_policy p "
            "WHERE o.map_id=%s AND o.instance_id=%s AND o.region_id=%s "
            "AND o.policy_version=%s AND o.published_at IS NULL AND o.superseded_at IS NULL "
            "AND p.map_id=o.map_id AND p.instance_id=o.instance_id "
            "AND p.region_id=o.region_id AND p.policy_version=o.policy_version "
            "RETURNING o.policy_version",
            (
                event["map_id"],
                event["instance_id"],
                event["region_id"],
                event["policy_version"],
            ),
        ).fetchone()
    return row is not None


def publish_pending(store, publish, *, limit=100):
    if not callable(publish):
        raise ValueError("Forecast publisher must be callable")
    sent = 0
    for event in pending_publications(store, limit=limit):
        with store.connection() as db:
            current = db.execute(
                "SELECT policy_version FROM territory_weather_forecast_policy "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (event["map_id"], event["instance_id"], event["region_id"]),
            ).fetchone()
        if current is None or current["policy_version"] != event["policy_version"]:
            with store.connection() as db:
                db.execute(
                    "UPDATE territory_weather_forecast_outbox "
                    "SET superseded_at=clock_timestamp() "
                    "WHERE map_id=%s AND instance_id=%s AND region_id=%s "
                    "AND policy_version=%s AND published_at IS NULL AND superseded_at IS NULL",
                    (
                        event["map_id"],
                        event["instance_id"],
                        event["region_id"],
                        event["policy_version"],
                    ),
                )
            continue
        publish(event)
        if acknowledge_publication(store, event):
            sent += 1
    return sent


def publish_to_world(store, world, event):
    _validate_event(event)
    payload = packet_for_territory(
        store,
        map_id=event["map_id"],
        instance_id=event["instance_id"],
        region_id=event["region_id"],
        policy_version=event["policy_version"],
    )
    delivered = failed = 0
    for snapshot in world.snapshot():
        if (
            snapshot.get("map_id") != event["map_id"]
            or snapshot.get("instance_id") != event["instance_id"]
            or type(snapshot.get("id")) is not int
        ):
            continue
        identity = world.live_identity(character_id=snapshot["id"])
        if identity is None:
            continue
        generation, current = identity
        if (
            current.get("map_id") != event["map_id"]
            or current.get("instance_id") != event["instance_id"]
        ):
            continue
        try:
            recipient_region = region_at(event["map_id"], current["x"], current["y"])
        except (KeyError, ValueError):
            continue
        if recipient_region != event["region_id"]:
            continue
        if world.send_to(current["id"], generation, 13895, payload):
            delivered += 1
        else:
            failed += 1
    if failed:
        raise OSError("Weather forecast could not be sent to a current session")
    return delivered


def _validate_event(event):
    if type(event) is not dict:
        raise ValueError("Invalid forecast publication event")
    if type(event.get("map_id")) is not int or type(event.get("region_id")) is not int:
        raise ValueError("Invalid forecast publication territory")
    if (
        type(event.get("instance_id")) is not int
        or not 0 <= event["instance_id"] < 2**63
    ):
        raise ValueError("Invalid forecast publication instance")
    if type(event.get("policy_version")) is not int or event["policy_version"] < 1:
        raise ValueError("Invalid forecast policy version")
    if (event["map_id"], event["region_id"]) not in set(territories()):
        raise ValueError("Unknown forecast publication territory")


def _i8(value):
    if type(value) is not int or not -128 <= value <= 127:
        raise ValueError("Invalid signed-byte weather forecast field")
    return value
