"""Read weather state for the exact native territory, backed by local policy.

Unknown positions fail closed. Known territories use a durable local baseline
when no native snapshot or per-instance state exists.
"""
import math
import struct
from datetime import datetime, timezone
from functools import lru_cache
from .territory_cells import region_at

WEATHER = ("ABSENT", "LIGHT", "HEAVY", "STORM")
_UNSET = object()


def decode(payload):
    """ctm/Vl: preserve uninterpreted values, reject invalid native state."""
    if type(payload) is not bytes or len(payload) != 37:
        raise ValueError("Invalid native territory weather payload")
    values = struct.unpack(">qb6fi", payload)
    if values[-1] not in range(len(WEATHER)) or not all(
        math.isfinite(value) for value in values[2:8]
    ):
        raise ValueError("Invalid native territory weather state")
    return dict(
        native_identity=values[0],
        native_byte=values[1],
        native_values=values[2:8],
        weather=WEATHER[values[-1]],
        current_temperature=values[1] + values[5],
        current_wind=values[2],
        minimum_temperature=values[3] + values[5],
        maximum_temperature=values[4] + values[5],
    )


def encode_modeled_state(native_identity, state):
    """Encode verified ctm→chl→bRW temperature/wind fields from one model day.

    The signed byte is current base temperature; floats are current wind,
    daily base minimum/maximum, temperature modifier, base wind and wind
    modifier. The installed consumer adds the modifiers before presentation.
    Temperature is in the native degree display scale; wind is a 0..1 ratio.
    """
    low, high = state["temperature_sample_a"], state["temperature_sample_b"]
    base_temperature = (low + high) // 2
    wind = state["wind_strength_u16"] / 65535.0
    return struct.pack(
        ">qb6fi",
        native_identity,
        base_temperature,
        wind,
        low,
        high,
        state["temperature_adjustment_sample"],
        wind,
        state["signed_weather_modifier_i16"] / 32767.0,
        WEATHER.index(state["weather"]),
    )


def save(store, *, map_id, instance_id, region_id, payload):
    """Caller must establish map/territory provenance; packet identity isn't a map."""
    if any(type(value) is not int for value in (map_id, instance_id, region_id)):
        raise ValueError("Invalid territory weather scope")
    _require_known_territory(map_id, region_id)
    weather = decode(payload)["weather"]
    with store.connection() as db:
        row = dict(
            db.execute(
                "INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(map_id,instance_id,region_id) "
                "DO UPDATE SET weather=EXCLUDED.weather,native_payload=EXCLUDED.native_payload, "
                "revision=territory_weather.revision+1,updated_at=clock_timestamp() "
                "RETURNING weather,native_payload,revision",
                (map_id, instance_id, region_id, weather, payload),
            ).fetchone()
        )
        db.execute(
            "INSERT INTO territory_weather_outbox "
            "(map_id,instance_id,region_id,revision,weather,native_payload) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                map_id,
                instance_id,
                region_id,
                row["revision"],
                row["weather"],
                row["native_payload"],
            ),
        )
        from .territory_weather_simulation import explicit_override

        explicit_override(db, map_id, instance_id, region_id)
        return row


def context(store, character, *, x, y, z):
    if type(z) is not int:
        raise ValueError("Invalid native territory height")
    if (
        type(character.get("instance_id")) is not int
        or not 0 <= character["instance_id"] < 2**63
    ):
        raise ValueError("Invalid native territory instance")
    region_id = region_at(character["map_id"], x, y)
    with store.connection() as db:
        row = db.execute(
            "SELECT weather,native_payload,revision FROM territory_weather "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (character["map_id"], character["instance_id"], region_id),
        ).fetchone()
    if row is None:
        row = materialize_local_state(
            store,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            region_id=region_id,
        )
    from .territory_weather_simulation import (
        advance as advance_simulation,
        _TransactionStore,
    )
    from .territory_weather_forecast import packet_for_territory

    advance_simulation(
        store, scope=(character["map_id"], character["instance_id"], region_id), limit=1
    )
    with store.connection() as db:
        row = db.execute(
            "SELECT weather,native_payload,revision FROM territory_weather "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s FOR SHARE",
            (character["map_id"], character["instance_id"], region_id),
        ).fetchone()
        forecast_payload = packet_for_territory(
            _TransactionStore(db),
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            region_id=region_id,
        )
    if decode(row["native_payload"])["weather"] != row["weather"]:
        raise ValueError("Inconsistent authoritative territory weather")
    return dict(row, region_id=region_id, forecast_payload=forecast_payload)


def initialize_local_baselines(
    store,
    *,
    weather=_UNSET,
    native_byte=_UNSET,
    native_values=_UNSET,
    policy_version=_UNSET,
    instance_id=0,
):
    """Initialize all 274 catalog territories from one explicit local policy.

    Existing policy and weather rows are preserved. An existing state seeds
    only its own territory policy and is never copied to another territory. Other
    territories receive the caller's explicit local baseline, defaulting to
    ABSENT and neutral float fields. Call during startup or an admin migration
    task; it does not publish sockets.
    """
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid weather baseline instance")
    from .territory_cells import territories

    keys = territories()
    policies_created = policies_preserved = states_created = states_preserved = 0
    with store.connection() as db:
        candidate = _policy_config(
            db,
            weather=weather,
            native_byte=native_byte,
            native_values=native_values,
            policy_version=policy_version,
        )
        for map_id, region_id in keys:
            existing_policy = db.execute(
                "SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6,"
                "policy_version,source FROM territory_weather_local_policy "
                "WHERE map_id=%s AND region_id=%s",
                (map_id, region_id),
            ).fetchone()
            existing_state = db.execute(
                "SELECT weather,native_payload FROM territory_weather "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (map_id, instance_id, region_id),
            ).fetchone()
            if existing_policy is not None:
                policy = _policy_from_row(existing_policy)
                source = existing_policy["source"]
                policies_preserved += 1
            elif existing_state is not None:
                captured = decode(existing_state["native_payload"])
                if captured["weather"] != existing_state["weather"]:
                    raise ValueError("Inconsistent preserved weather state")
                policy = _validated_baseline(
                    captured["weather"],
                    captured["native_byte"],
                    captured["native_values"],
                )
                source = "PRESERVED_STATE"
                candidate_version = candidate["policy_version"]
            else:
                policy = candidate
                source = "LOCAL_POLICY"
                candidate_version = candidate["policy_version"]
            if existing_policy is None:
                version = (
                    candidate["policy_version"]
                    if source != "PRESERVED_STATE"
                    else candidate_version
                )
                inserted = db.execute(
                    "INSERT INTO territory_weather_local_policy "
                    "(map_id,region_id,source,policy_version,weather,native_byte,"
                    "value_1,value_2,value_3,value_4,value_5,value_6) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(map_id,region_id) DO NOTHING RETURNING map_id",
                    (
                        map_id,
                        region_id,
                        source,
                        version,
                        policy["weather"],
                        policy["native_byte"],
                        *policy["native_values"],
                    ),
                ).fetchone()
                if inserted is None:
                    existing_policy = db.execute(
                        "SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6,"
                        "policy_version,source FROM territory_weather_local_policy "
                        "WHERE map_id=%s AND region_id=%s",
                        (map_id, region_id),
                    ).fetchone()
                    policy = _policy_from_row(existing_policy)
                else:
                    policies_created += 1
            if existing_state is None:
                payload = _baseline_payload(region_id, policy)
                inserted = db.execute(
                    "INSERT INTO territory_weather "
                    "(map_id,instance_id,region_id,weather,native_payload) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING region_id",
                    (map_id, instance_id, region_id, policy["weather"], payload),
                ).fetchone()
                if inserted is None:
                    states_preserved += 1
                else:
                    states_created += 1
            else:
                states_preserved += 1
    return dict(
        territories=len(keys),
        policies_created=policies_created,
        policies_preserved=policies_preserved,
        states_created=states_created,
        states_preserved=states_preserved,
    )


def materialize_local_state(store, *, map_id, instance_id, region_id):
    """Create the exact instance state from its territory policy, idempotently."""
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid territory weather instance")
    _require_known_territory(map_id, region_id)
    with store.connection() as db:
        current = db.execute(
            "SELECT weather,native_payload,revision FROM territory_weather "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region_id),
        ).fetchone()
        if current is not None:
            return dict(current)
        policy = db.execute(
            "SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6,"
            "policy_version,source "
            "FROM territory_weather_local_policy WHERE map_id=%s AND region_id=%s",
            (map_id, region_id),
        ).fetchone()
        if policy is None:
            defaults = _policy_config(db)
            db.execute(
                "INSERT INTO territory_weather_local_policy "
                "(map_id,region_id,source,policy_version,weather,native_byte,"
                "value_1,value_2,value_3,value_4,value_5,value_6) "
                "VALUES(%s,%s,'LOCAL_POLICY',%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(map_id,region_id) DO NOTHING",
                (
                    map_id,
                    region_id,
                    defaults["policy_version"],
                    defaults["weather"],
                    defaults["native_byte"],
                    *defaults["native_values"],
                ),
            )
            policy = db.execute(
                "SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6,"
                "policy_version,source "
                "FROM territory_weather_local_policy WHERE map_id=%s AND region_id=%s",
                (map_id, region_id),
            ).fetchone()
        state = _policy_from_row(policy)
        payload = _baseline_payload(region_id, state)
        row = db.execute(
            "INSERT INTO territory_weather "
            "(map_id,instance_id,region_id,weather,native_payload) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(map_id,instance_id,region_id) "
            "DO UPDATE SET weather=territory_weather.weather "
            "RETURNING weather,native_payload,revision",
            (map_id, instance_id, region_id, state["weather"], payload),
        ).fetchone()
    return dict(row)


def schedule_transition(
    store, *, map_id, instance_id, region_id, transition_at, target_weather
):
    """Persist an explicit local policy transition for a known territory.

    Weather values and their time are operator-authored. This deliberately
    does not invent a forecast, random schedule, or default for other zones.
    """
    _validate_scope(map_id, instance_id, region_id)
    _require_known_territory(map_id, region_id)
    if type(target_weather) is not str or target_weather not in WEATHER:
        raise ValueError("Unknown scheduled weather")
    if not isinstance(transition_at, datetime) or transition_at.tzinfo is None:
        raise ValueError("Weather transition requires an aware timestamp")
    with store.connection() as db:
        if (
            db.execute(
                "SELECT 1 FROM territory_weather WHERE map_id=%s AND instance_id=%s "
                "AND region_id=%s",
                (map_id, instance_id, region_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Authoritative territory weather unavailable")
        if (
            transition_at
            <= db.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        ):
            raise ValueError("Weather transition must be scheduled in the future")
        inserted = db.execute(
            "INSERT INTO territory_weather_transitions "
            "(map_id,instance_id,region_id,transition_at,target_weather) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING target_weather",
            (map_id, instance_id, region_id, transition_at, target_weather),
        ).fetchone()
        if inserted is not None:
            from .territory_weather_simulation import explicit_override

            explicit_override(db, map_id, instance_id, region_id)
            return True
        existing = db.execute(
            "SELECT target_weather FROM territory_weather_transitions "
            "WHERE map_id=%s AND instance_id=%s AND region_id=%s AND transition_at=%s",
            (map_id, instance_id, region_id, transition_at),
        ).fetchone()
        if existing is not None and existing["target_weather"] == target_weather:
            return False
        raise ValueError("Conflicting weather transition at the same time")


def advance_due(store, *, now=None, limit=100):
    """Apply the latest due transition per configured territory atomically.

    Only the weather enum in the current native 13948 payload is changed; the
    identity and six uninterpreted floats are preserved byte-for-byte. If the
    scheduler was offline, intermediate due states are coalesced to the latest
    configured state instead of flashing old weather on clients.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid weather transition batch size")
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Weather clock must be an aware timestamp")
    when = now.astimezone(timezone.utc) if now is not None else None
    pred = (
        "transition_at <= clock_timestamp()" if when is None else "transition_at <= %s"
    )
    params = () if when is None else (when,)
    from .territory_weather_simulation import advance as advance_simulation

    changed = advance_simulation(store, now=now, limit=limit)
    with store.connection() as db:
        rows = db.execute(
            "SELECT t.map_id,t.instance_id,t.region_id,t.transition_at,t.target_weather "
            "FROM territory_weather_transitions t WHERE t." + pred + " AND "
            "t.transition_at=(SELECT max(t2.transition_at) "
            "FROM territory_weather_transitions t2 WHERE t2.map_id=t.map_id "
            "AND t2.instance_id=t.instance_id AND t2.region_id=t.region_id AND t2."
            + pred
            + ") "
            "ORDER BY t.map_id,t.instance_id,t.region_id "
            "LIMIT %s FOR UPDATE OF t SKIP LOCKED",
            (*params, *params, limit),
        ).fetchall()
        for scheduled in rows:
            key = (
                scheduled["map_id"],
                scheduled["instance_id"],
                scheduled["region_id"],
            )
            current = db.execute(
                "SELECT weather,native_payload,revision FROM territory_weather "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s FOR UPDATE",
                key,
            ).fetchone()
            if current is None:
                raise ValueError("Authoritative territory weather unavailable")
            decoded = decode(current["native_payload"])
            if decoded["weather"] != current["weather"]:
                raise ValueError("Inconsistent authoritative territory weather")
            db.execute(
                "DELETE FROM territory_weather_transitions WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s AND transition_at <= %s",
                (*key, scheduled["transition_at"]),
            )
            if current["weather"] == scheduled["target_weather"]:
                continue
            target_id = WEATHER.index(scheduled["target_weather"])
            payload = current["native_payload"][:-4] + struct.pack(">i", target_id)
            revision = db.execute(
                "UPDATE territory_weather SET weather=%s,native_payload=%s, "
                "revision=revision+1,updated_at=clock_timestamp() "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s "
                "RETURNING revision",
                (scheduled["target_weather"], payload, *key),
            ).fetchone()["revision"]
            db.execute(
                "INSERT INTO territory_weather_outbox "
                "(map_id,instance_id,region_id,revision,weather,native_payload) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (*key, revision, scheduled["target_weather"], payload),
            )
            changed.append(
                dict(
                    map_id=key[0],
                    instance_id=key[1],
                    region_id=key[2],
                    revision=revision,
                    weather=scheduled["target_weather"],
                    native_payload=payload,
                )
            )
    return changed


def pending_publications(store, *, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid weather publication batch size")
    with store.connection() as db:
        # A superseded state must never be replayed after the authority moved
        # on. Mark it explicitly instead of leaving an undeliverable outbox row
        # pending forever.
        db.execute(
            "UPDATE territory_weather_outbox o SET superseded_at=clock_timestamp() "
            "FROM territory_weather w WHERE o.map_id=w.map_id "
            "AND o.instance_id=w.instance_id AND o.region_id=w.region_id "
            "AND o.revision<>w.revision AND o.published_at IS NULL "
            "AND o.superseded_at IS NULL"
        )
        return [
            dict(row)
            for row in db.execute(
                "SELECT o.map_id,o.instance_id,o.region_id,o.revision,o.weather,o.native_payload "
                "FROM territory_weather_outbox o JOIN territory_weather w "
                "USING(map_id,instance_id,region_id) "
                "WHERE o.published_at IS NULL AND o.superseded_at IS NULL "
                "AND o.revision=w.revision AND o.weather=w.weather "
                "AND o.native_payload=w.native_payload "
                "ORDER BY created_at,map_id,instance_id,region_id,revision LIMIT %s",
                (limit,),
            ).fetchall()
        ]


def acknowledge_publication(store, event):
    """Mark the exact outbox snapshot attempted; this is not a client ACK."""
    if not isinstance(event, dict):
        raise ValueError("Invalid weather publication event")
    _validate_scope(
        event.get("map_id"), event.get("instance_id"), event.get("region_id")
    )
    if type(event.get("revision")) is not int or event["revision"] < 1:
        raise ValueError("Invalid weather publication revision")
    if type(event.get("native_payload")) is not bytes:
        raise ValueError("Invalid weather publication payload")
    decoded = decode(event["native_payload"])
    if decoded["weather"] != event.get("weather"):
        raise ValueError("Inconsistent weather publication event")
    with store.connection() as db:
        row = db.execute(
            "UPDATE territory_weather_outbox o SET published_at=clock_timestamp() "
            "FROM territory_weather w "
            "WHERE o.map_id=%s AND o.instance_id=%s AND o.region_id=%s AND o.revision=%s "
            "AND o.weather=%s AND o.native_payload=%s AND o.published_at IS NULL "
            "AND o.superseded_at IS NULL AND w.map_id=o.map_id "
            "AND w.instance_id=o.instance_id AND w.region_id=o.region_id "
            "AND w.revision=o.revision AND w.weather=o.weather "
            "AND w.native_payload=o.native_payload RETURNING o.revision",
            (
                event["map_id"],
                event["instance_id"],
                event["region_id"],
                event["revision"],
                event["weather"],
                event["native_payload"],
            ),
        ).fetchone()
    return row is not None


def publish_pending(store, publish, *, limit=100):
    """Publish outbox snapshots at-least-once using a caller-supplied router.

    The router must target only clients in the event's exact territory. It must
    raise on failure; a successful return marks the attempt, not client receipt.
    """
    if not callable(publish):
        raise ValueError("Weather publisher must be callable")
    sent = 0
    for event in pending_publications(store, limit=limit):
        # Recheck authority immediately before handing the snapshot to the
        # router; state may have advanced since the pending list was read.
        with store.connection() as db:
            current = db.execute(
                "SELECT weather,native_payload,revision FROM territory_weather "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (event["map_id"], event["instance_id"], event["region_id"]),
            ).fetchone()
        if current is None or any(
            current[key] != event[key]
            for key in ("weather", "native_payload", "revision")
        ):
            with store.connection() as db:
                db.execute(
                    "UPDATE territory_weather_outbox SET superseded_at=clock_timestamp() "
                    "WHERE map_id=%s AND instance_id=%s AND region_id=%s AND revision=%s "
                    "AND published_at IS NULL AND superseded_at IS NULL",
                    (
                        event["map_id"],
                        event["instance_id"],
                        event["region_id"],
                        event["revision"],
                    ),
                )
            continue
        publish(event)
        if acknowledge_publication(store, event):
            sent += 1
    return sent


def publish_to_world(world, event):
    """Send one 13948 snapshot only to current sessions in its native territory.

    `World` membership is snapshotted first. Position, map and instance are
    revalidated against the current generation before each send; no DB or
    socket operation is performed under the membership lock.
    """
    if not isinstance(event, dict):
        raise ValueError("Invalid weather publication event")
    _validate_scope(
        event.get("map_id"), event.get("instance_id"), event.get("region_id")
    )
    if type(event.get("revision")) is not int or event["revision"] < 1:
        raise ValueError("Invalid weather publication revision")
    payload = event.get("native_payload")
    if type(payload) is not bytes or decode(payload)["weather"] != event.get("weather"):
        raise ValueError("Inconsistent weather publication event")
    _require_known_territory(event["map_id"], event["region_id"])
    delivered = 0
    failed = 0
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
        if world.send_to(current["id"], generation, 13948, payload):
            delivered += 1
        else:
            failed += 1
    if failed:
        # Leave the outbox event pending so the next leased tick can retry.
        # A session that departed during the send will disappear from the next
        # snapshot; reconnecting sessions bootstrap the current DB state.
        raise OSError("Weather update could not be sent to a current session")
    return delivered


def tick_weather(store, world, *, limit=100):
    """Advance configured transitions and retry durable updates to sessions.

    A scheduler may call this under its distributed occurrence lease. State
    changes commit before socket publication; a publication failure leaves its
    outbox row pending for the next occurrence. Sending current state is safe
    to repeat, while client receipt is not claimed by the outbox marker.
    """
    changed = advance_due(store, limit=limit)
    published = publish_pending(
        store, lambda event: publish_to_world(world, event), limit=limit
    )
    from .territory_weather_forecast import (
        publish_pending as publish_forecast_pending,
        publish_to_world as publish_forecast_to_world,
    )

    forecast_published = publish_forecast_pending(
        store,
        lambda event: publish_forecast_to_world(store, world, event),
        limit=limit,
    )
    return {
        "advanced": len(changed),
        "published": published,
        "forecast_published": forecast_published,
    }


def _validate_scope(map_id, instance_id, region_id):
    if any(type(value) is not int for value in (map_id, instance_id, region_id)):
        raise ValueError("Invalid territory weather scope")
    if instance_id < 0 or instance_id >= 2**63:
        raise ValueError("Invalid territory weather instance")


def _validated_baseline(weather, native_byte, native_values):
    if type(weather) is not str or weather not in WEATHER:
        raise ValueError("Invalid local weather policy state")
    if type(native_byte) is not int or not -128 <= native_byte <= 127:
        raise ValueError("Invalid local weather policy byte")
    if (
        not isinstance(native_values, (tuple, list))
        or len(native_values) != 6
        or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in native_values
        )
    ):
        raise ValueError("Invalid local weather policy values")
    try:
        packed = struct.pack(">6f", *native_values)
    except (OverflowError, struct.error):
        raise ValueError("Invalid local weather policy float range") from None
    values = struct.unpack(">6f", packed)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Invalid local weather policy float range")
    return dict(weather=weather, native_byte=native_byte, native_values=values)


def _policy_from_row(row):
    return dict(
        weather=row["weather"],
        native_byte=row["native_byte"],
        native_values=tuple(row[f"value_{n}"] for n in range(1, 7)),
        policy_version=row["policy_version"],
        source=row["source"],
    )


def _policy_config(
    db,
    *,
    weather=_UNSET,
    native_byte=_UNSET,
    native_values=_UNSET,
    policy_version=_UNSET,
):
    row = db.execute(
        "SELECT value FROM settings WHERE name='weather_local_baseline'"
    ).fetchone()
    value = None if row is None else row["value"]
    expected = {"weather", "native_byte", "native_values", "policy_version"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Invalid local weather baseline configuration")
    selected = dict(
        weather=value["weather"] if weather is _UNSET else weather,
        native_byte=value["native_byte"] if native_byte is _UNSET else native_byte,
        native_values=value["native_values"]
        if native_values is _UNSET
        else native_values,
        policy_version=value["policy_version"]
        if policy_version is _UNSET
        else policy_version,
    )
    baseline = _validated_baseline(
        selected["weather"], selected["native_byte"], selected["native_values"]
    )
    if type(selected["policy_version"]) is not int or selected["policy_version"] < 1:
        raise ValueError("Invalid local weather policy version")
    baseline["policy_version"] = selected["policy_version"]
    return baseline


def _baseline_payload(region_id, policy):
    values = _validated_baseline(
        policy["weather"], policy["native_byte"], policy["native_values"]
    )
    return struct.pack(
        ">qb6fi",
        region_id,
        values["native_byte"],
        *values["native_values"],
        WEATHER.index(values["weather"]),
    )


@lru_cache(maxsize=1)
def _known_territories():
    from .territory_cells import territories

    return frozenset(territories())


def _require_known_territory(map_id, region_id):
    if type(map_id) is not int or type(region_id) is not int:
        raise ValueError("Invalid native weather territory")
    if (map_id, region_id) not in _known_territories():
        raise ValueError("Unknown native map region")
