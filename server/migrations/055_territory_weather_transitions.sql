-- Explicit local weather schedule. Each row names one supported target state
-- for one known territory; this does not derive forecasts or default weather.
CREATE TABLE territory_weather_transitions (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    region_id integer NOT NULL,
    transition_at timestamptz NOT NULL,
    target_weather text NOT NULL CHECK (
        target_weather IN ('ABSENT','LIGHT','HEAVY','STORM')
    ),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (map_id,instance_id,region_id,transition_at),
    FOREIGN KEY (map_id,instance_id,region_id)
        REFERENCES territory_weather(map_id,instance_id,region_id)
        ON DELETE CASCADE
);

CREATE INDEX territory_weather_transitions_due
    ON territory_weather_transitions(transition_at,map_id,instance_id,region_id);

-- A durable snapshot lets a server retry publication after a crash. A retry
-- sends the same revision/payload; clients treat 13948 as current-state data.
CREATE TABLE territory_weather_outbox (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    region_id integer NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    weather text NOT NULL CHECK (weather IN ('ABSENT','LIGHT','HEAVY','STORM')),
    native_payload bytea NOT NULL CHECK (octet_length(native_payload)=37),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    superseded_at timestamptz,
    PRIMARY KEY (map_id,instance_id,region_id,revision),
    FOREIGN KEY (map_id,instance_id,region_id)
        REFERENCES territory_weather(map_id,instance_id,region_id)
        ON DELETE CASCADE,
    CHECK (published_at IS NULL OR published_at >= created_at),
    CHECK (superseded_at IS NULL OR superseded_at >= created_at),
    CHECK (published_at IS NULL OR superseded_at IS NULL)
);

CREATE INDEX territory_weather_outbox_pending
    ON territory_weather_outbox(created_at,map_id,instance_id,region_id,revision)
    WHERE published_at IS NULL AND superseded_at IS NULL;
