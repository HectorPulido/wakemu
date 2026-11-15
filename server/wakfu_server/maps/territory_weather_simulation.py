"""World-owned weather policy validation and explicit administrative authority.

The Rust ecology service advances autonomous weather and forecasts. World keeps
only operator override fencing and transaction reuse for authoritative writes.
"""

from contextlib import contextmanager

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


class _TransactionStore:
    """Reuse the caller transaction for the existing validated forecast writer."""

    def __init__(self, db):
        self.db = db

    @contextmanager
    def connection(self):
        yield self.db


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
