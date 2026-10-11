"""Reproducible local regional days and matching native forecasts.

Wire samples are local policy values, not claimed Celsius or upstream rules.
One shared deterministic model predicts each day's state before it occurs.
Current state, forecast and cursor commit together; restart coalesces missed
days. Native snapshots, explicit forecasts and operator transitions retain
authority over automatically generated local baselines.
"""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .territory_weather import WEATHER, decode, encode_modeled_state

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIELDS = {
    "enabled",
    "seed",
    "day_seconds",
    "forecast_days",
    "weather_weights",
    "season_temperature_samples",
    "temperature_variation",
    "wind_samples",
}


def validate_policy(value):
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("Invalid regional weather simulation policy")
    if type(value["enabled"]) is not bool:
        raise ValueError("Invalid regional weather simulation enabled flag")
    for name, low, high in (
        ("seed", 0, 2**31 - 1),
        ("day_seconds", 10, 604800),
        ("forecast_days", 1, 30),
        ("temperature_variation", 0, 30),
    ):
        if type(value[name]) is not int or not low <= value[name] <= high:
            raise ValueError(f"Invalid regional weather simulation {name}")
    for name, low, high in (
        ("weather_weights", 0, 10000),
        ("season_temperature_samples", -90, 90),
        ("wind_samples", 0, 65535),
    ):
        rows = value[name]
        if (
            type(rows) is not list
            or len(rows) != 4
            or any(type(item) is not int or not low <= item <= high for item in rows)
        ):
            raise ValueError(f"Invalid regional weather simulation {name}")
    if not sum(value["weather_weights"]):
        raise ValueError("Regional weather simulation requires a weather weight")
    return dict(value)


def _sample(policy, map_id, region_id, day, purpose):
    # Instance is deliberately absent: copies of one physical region share its
    # climate, while their durable state and publication remain instance scoped.
    raw = f'{policy["seed"]}:{map_id}:{region_id}:{day}:{purpose}'.encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def day_state(policy, map_id, region_id, day):
    """Return deterministic named wire fields for a synthetic UTC calendar day."""
    if any(type(item) is not int for item in (map_id, region_id, day)):
        raise ValueError("Invalid regional weather simulation scope/day")
    # Gregorian seasons repeat every 400 years, including accelerated clocks.
    calendar = EPOCH + timedelta(days=day % 146097)
    season = (calendar.month % 12) // 3
    weights = policy["weather_weights"]
    # Broad local seasons favor wet winter and dry summer without asserting
    # native probability data. Configured zero weights always remain disabled.
    factors = (
        (75, 110, 125, 110),
        (100, 115, 100, 100),
        (135, 85, 70, 80),
        (90, 110, 120, 110),
    )[season]
    effective = [weight * factor for weight, factor in zip(weights, factors)]
    roll = _sample(policy, map_id, region_id, day, "weather") % sum(effective)
    weather_id = 0
    for weather_id, weight in enumerate(effective):
        if roll < weight:
            break
        roll -= weight
    variation = policy["temperature_variation"]
    delta = (
        _sample(policy, map_id, region_id, day, "temperature") % (2 * variation + 1)
        - variation
    )
    temperature = policy["season_temperature_samples"][season] + delta
    return dict(
        season=season,
        weather=WEATHER[weather_id],
        temperature_sample_a=temperature - 3,
        temperature_sample_b=temperature + 3,
        wind_strength_u16=policy["wind_samples"][weather_id],
        temperature_adjustment_sample=0,
        signed_weather_modifier_i16=0,
    )


def forecast_policy(policy, map_id, region_id, day):
    if not policy["enabled"]:
        return [], []
    days = [
        day_state(policy, map_id, region_id, day + offset)
        for offset in range(1, policy["forecast_days"] + 1)
    ]
    # bRX clamps forecast minimum/maximum to these seasonal bounds.
    # Zero/zero would flatten every displayed forecast range to zero.
    seasons = [
        dict(
            season=season,
            actual_minimum_adjustment=policy["season_temperature_samples"][season]
            - policy["temperature_variation"]
            - 3,
            actual_maximum_adjustment=policy["season_temperature_samples"][season]
            + policy["temperature_variation"]
            + 3,
        )
        for season in sorted({row["season"] for row in days})
    ]
    return days, seasons


class _TransactionStore:
    """Reuse the caller transaction for the existing validated forecast writer."""

    def __init__(self, db):
        self.db = db

    @contextmanager
    def connection(self):
        yield self.db


def advance(store, *, now=None, limit=100, scope=None):
    """Advance a bounded set of local baseline scopes with atomic forecasts."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid regional weather simulation batch size")
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Regional weather simulation requires an aware clock")
    if scope is not None and (
        type(scope) is not tuple
        or len(scope) != 3
        or any(type(item) is not int for item in scope)
        or not 0 <= scope[1] < 2**63
    ):
        raise ValueError("Invalid regional weather simulation scope")
    from .territory_weather_forecast import save_policy

    changed = []
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='weather_simulation'"
        ).fetchone()
        # Old schemas remain usable until the complete migration is installed.
        if row is None:
            return changed
        policy = validate_policy(row["value"])
        when = (
            now
            if now is not None
            else db.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        )
        day = int(
            (when.astimezone(timezone.utc) - EPOCH).total_seconds()
            // policy["day_seconds"]
        )
        fingerprint = hashlib.sha256(
            json.dumps(policy, sort_keys=True).encode()
        ).hexdigest()
        scope_filter = (
            ""
            if scope is None
            else "AND w.map_id=%s AND w.instance_id=%s AND w.region_id=%s "
        )
        row_lock = "FOR UPDATE OF w SKIP LOCKED" if scope is None else "FOR UPDATE OF w"
        due_filter = (
            "AND (s.simulated_day IS NULL OR s.simulated_day<>%s OR s.configuration_hash<>%s) "
            if policy["enabled"]
            else "AND s.simulated_day IS NOT NULL AND s.configuration_hash<>%s "
        )
        due_params = (day, fingerprint) if policy["enabled"] else (fingerprint,)
        rows = db.execute(
            "SELECT w.*,s.forecast_version AS generated_forecast_version,"
            "f.policy_version AS current_forecast_version FROM territory_weather w "
            "JOIN territory_weather_local_policy p USING(map_id,region_id) "
            "LEFT JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) "
            "LEFT JOIN territory_weather_forecast_policy f USING(map_id,instance_id,region_id) "
            "WHERE p.source='LOCAL_POLICY' "
            "AND (s.explicit_override IS NULL OR NOT s.explicit_override) "
            + due_filter
            + "AND (f.policy_version IS NULL OR f.policy_version=s.forecast_version) "
            "AND NOT EXISTS (SELECT 1 FROM territory_weather_transitions t "
            "WHERE t.map_id=w.map_id AND t.instance_id=w.instance_id AND t.region_id=w.region_id) "
            + scope_filter
            + "ORDER BY s.updated_at NULLS FIRST,w.map_id,w.instance_id,w.region_id "
            "LIMIT %s " + row_lock,
            (*due_params, *(scope or ()), limit),
        ).fetchall()
        for current in rows:
            key = (current["map_id"], current["instance_id"], current["region_id"])
            # Re-read after acquiring the weather row lock: a scoped bootstrap
            # may have waited for another worker whose joined cursor/forecast
            # was not visible to the original SELECT snapshot.
            authority = db.execute(
                "SELECT s.simulated_day,s.configuration_hash,s.explicit_override,"
                "s.forecast_version,f.policy_version FROM territory_weather w "
                "LEFT JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) "
                "LEFT JOIN territory_weather_forecast_policy f USING(map_id,instance_id,region_id) "
                "WHERE w.map_id=%s AND w.instance_id=%s AND w.region_id=%s",
                key,
            ).fetchone()
            if authority["explicit_override"] or (
                authority["policy_version"] is not None
                and authority["policy_version"] != authority["forecast_version"]
            ):
                continue
            if authority["configuration_hash"] == fingerprint and (
                not policy["enabled"] or authority["simulated_day"] == day
            ):
                continue
            decoded = decode(current["native_payload"])
            if decoded["weather"] != current["weather"]:
                raise ValueError("Inconsistent authoritative territory weather")
            state = day_state(policy, key[0], key[2], day)
            payload = encode_modeled_state(decoded["native_identity"], state)
            if policy["enabled"] and current["native_payload"] != payload:
                revision = db.execute(
                    "UPDATE territory_weather SET weather=%s,native_payload=%s,revision=revision+1,"
                    "updated_at=clock_timestamp() WHERE map_id=%s AND instance_id=%s AND region_id=%s RETURNING revision",
                    (state["weather"], payload, *key),
                ).fetchone()["revision"]
                db.execute(
                    "INSERT INTO territory_weather_outbox(map_id,instance_id,region_id,revision,weather,native_payload) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (*key, revision, state["weather"], payload),
                )
                changed.append(
                    dict(
                        map_id=key[0],
                        instance_id=key[1],
                        region_id=key[2],
                        revision=revision,
                        weather=state["weather"],
                        native_payload=payload,
                    )
                )
            version = (authority["policy_version"] or 0) + 1
            days, seasons = forecast_policy(policy, key[0], key[2], day)
            save_policy(
                _TransactionStore(db),
                map_id=key[0],
                instance_id=key[1],
                region_id=key[2],
                policy_version=version,
                days=days,
                season_adjustments=seasons,
            )
            db.execute(
                "INSERT INTO territory_weather_simulation(map_id,instance_id,region_id,simulated_day,configuration_hash,forecast_version) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET "
                "simulated_day=EXCLUDED.simulated_day,configuration_hash=EXCLUDED.configuration_hash,"
                "forecast_version=EXCLUDED.forecast_version,updated_at=clock_timestamp()",
                (*key, day, fingerprint, version),
            )
    return changed


def explicit_override(db, map_id, instance_id, region_id):
    """Keep operator-authored snapshots/transitions authoritative until reset."""
    if (
        db.execute("SELECT 1 FROM settings WHERE name='weather_simulation'").fetchone()
        is None
    ):
        return
    owned = db.execute(
        "SELECT f.policy_version FROM territory_weather_forecast_policy f "
        "JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) "
        "WHERE f.map_id=%s AND f.instance_id=%s AND f.region_id=%s "
        "AND f.policy_version=s.forecast_version AND NOT s.explicit_override",
        (map_id, instance_id, region_id),
    ).fetchone()
    if owned is not None:
        # An operator's new snapshot invalidates our old predictions. Publish
        # an explicit clear rather than displaying a stale automatic forecast.
        from .territory_weather_forecast import save_policy

        save_policy(
            _TransactionStore(db),
            map_id=map_id,
            instance_id=instance_id,
            region_id=region_id,
            policy_version=owned["policy_version"] + 1,
            days=[],
            season_adjustments=[],
        )
    db.execute(
        "INSERT INTO territory_weather_simulation(map_id,instance_id,region_id,simulated_day,configuration_hash,forecast_version,explicit_override) "
        "VALUES(%s,%s,%s,0,'',1,true) ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET explicit_override=true",
        (map_id, instance_id, region_id),
    )
