-- Explicit local defaults for every territory in the checked native cell
-- catalog. These rows describe Wakemu policy, not upstream weather data.
CREATE TABLE territory_weather_local_policy (
    map_id integer NOT NULL,
    region_id integer NOT NULL,
    source text NOT NULL CHECK (source IN ('LOCAL_POLICY','PRESERVED_STATE')),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    weather text NOT NULL CHECK (weather IN ('ABSENT','LIGHT','HEAVY','STORM')),
    native_byte smallint NOT NULL CHECK (native_byte BETWEEN -128 AND 127),
    value_1 real NOT NULL,
    value_2 real NOT NULL,
    value_3 real NOT NULL,
    value_4 real NOT NULL,
    value_5 real NOT NULL,
    value_6 real NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (map_id,region_id),
    CHECK (value_1 > '-Infinity'::real AND value_1 < 'Infinity'::real),
    CHECK (value_2 > '-Infinity'::real AND value_2 < 'Infinity'::real),
    CHECK (value_3 > '-Infinity'::real AND value_3 < 'Infinity'::real),
    CHECK (value_4 > '-Infinity'::real AND value_4 < 'Infinity'::real),
    CHECK (value_5 > '-Infinity'::real AND value_5 < 'Infinity'::real),
    CHECK (value_6 > '-Infinity'::real AND value_6 < 'Infinity'::real)
);

CREATE INDEX territory_weather_local_policy_source
    ON territory_weather_local_policy(source,map_id,region_id);

ALTER TABLE territory_weather
    ADD CONSTRAINT territory_weather_nonnegative_instance CHECK (instance_id >= 0);
ALTER TABLE territory_weather_transitions
    ADD CONSTRAINT territory_weather_transitions_nonnegative_instance CHECK (instance_id >= 0);
ALTER TABLE territory_weather_outbox
    ADD CONSTRAINT territory_weather_outbox_nonnegative_instance CHECK (instance_id >= 0);

INSERT INTO settings(name,value) VALUES (
    'weather_local_baseline',
    '{"weather":"ABSENT","native_byte":0,"native_values":[0,0,0,0,0,0],"policy_version":1}'::jsonb
) ON CONFLICT(name) DO NOTHING;
