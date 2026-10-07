-- Structured, explicit local policy for the native 13895 weather forecast.
-- Values are kept as named wire-domain fields; no captured byte blob is stored.
CREATE TABLE territory_weather_forecast_policy (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL CHECK (instance_id >= 0),
    region_id integer NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    source text NOT NULL CHECK (source = 'LOCAL_POLICY'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (map_id,instance_id,region_id)
);

CREATE TABLE territory_weather_forecast_days (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL CHECK (instance_id >= 0),
    region_id integer NOT NULL,
    day_offset smallint NOT NULL CHECK (day_offset BETWEEN 1 AND 255),
    season smallint NOT NULL CHECK (season BETWEEN 0 AND 3),
    temperature_sample_a smallint NOT NULL CHECK (temperature_sample_a BETWEEN -128 AND 127),
    temperature_sample_b smallint NOT NULL CHECK (temperature_sample_b BETWEEN -128 AND 127),
    wind_strength_u16 integer NOT NULL CHECK (wind_strength_u16 BETWEEN 0 AND 65535),
    weather text NOT NULL CHECK (weather IN ('ABSENT','LIGHT','HEAVY','STORM')),
    temperature_adjustment_sample smallint NOT NULL CHECK (temperature_adjustment_sample BETWEEN -128 AND 127),
    signed_weather_modifier_i16 integer NOT NULL CHECK (signed_weather_modifier_i16 BETWEEN -32768 AND 32767),
    PRIMARY KEY (map_id,instance_id,region_id,day_offset),
    FOREIGN KEY (map_id,instance_id,region_id)
        REFERENCES territory_weather_forecast_policy(map_id,instance_id,region_id) ON DELETE CASCADE
);

CREATE TABLE territory_weather_forecast_season_adjustments (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL CHECK (instance_id >= 0),
    region_id integer NOT NULL,
    season smallint NOT NULL CHECK (season BETWEEN 0 AND 3),
    actual_minimum_adjustment smallint NOT NULL CHECK (actual_minimum_adjustment BETWEEN -128 AND 127),
    actual_maximum_adjustment smallint NOT NULL CHECK (actual_maximum_adjustment BETWEEN -128 AND 127),
    PRIMARY KEY (map_id,instance_id,region_id,season),
    FOREIGN KEY (map_id,instance_id,region_id)
        REFERENCES territory_weather_forecast_policy(map_id,instance_id,region_id) ON DELETE CASCADE
);

CREATE INDEX territory_weather_forecast_days_scope
    ON territory_weather_forecast_days(map_id,instance_id,region_id,day_offset);

CREATE TABLE territory_weather_forecast_outbox (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL CHECK (instance_id >= 0),
    region_id integer NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    superseded_at timestamptz,
    PRIMARY KEY (map_id,instance_id,region_id,policy_version),
    FOREIGN KEY (map_id,instance_id,region_id)
        REFERENCES territory_weather_forecast_policy(map_id,instance_id,region_id) ON DELETE CASCADE,
    CHECK (published_at IS NULL OR superseded_at IS NULL)
);

CREATE INDEX territory_weather_forecast_outbox_pending
    ON territory_weather_forecast_outbox(created_at,map_id,instance_id,region_id,policy_version)
    WHERE published_at IS NULL AND superseded_at IS NULL;
