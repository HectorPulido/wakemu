-- Deterministic emulator weather. These are explicit local balancing values,
-- not recovered official probabilities or physical units.
INSERT INTO settings(name,value) VALUES ('weather_simulation',
    '{"enabled":true,"seed":20261011,"day_seconds":86400,"forecast_days":5,"weather_weights":[60,25,12,3],"season_temperature_samples":[2,12,23,12],"temperature_variation":5,"wind_samples":[13107,22937,42598,62258]}'::jsonb
) ON CONFLICT(name) DO NOTHING;

CREATE TABLE territory_weather_simulation (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL CHECK(instance_id >= 0),
    region_id integer NOT NULL,
    simulated_day bigint NOT NULL,
    configuration_hash text NOT NULL,
    forecast_version integer NOT NULL CHECK(forecast_version > 0),
    explicit_override boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(map_id,instance_id,region_id),
    FOREIGN KEY(map_id,instance_id,region_id)
        REFERENCES territory_weather(map_id,instance_id,region_id) ON DELETE CASCADE
);
