-- Explicit server-owned territory state. No invented weather for unknown maps.
CREATE TABLE territory_weather (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    region_id integer NOT NULL,
    weather text NOT NULL CHECK (weather IN ('ABSENT','LIGHT','HEAVY','STORM')),
    native_payload bytea NOT NULL CHECK (octet_length(native_payload)=37),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision>0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (map_id,instance_id,region_id)
);

-- Initial local state for this exact territory only, from the verified
-- 2026-10-03 capture: 13948 identity79301 and following12789 region79301,
-- native ecology metadata map1134. Vl enum1=LIGHT in the matching client JAR.
-- This is an initialization snapshot, not a weather simulation or forecast.
INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload)
VALUES (1134,0,79301,'LIGHT',
    decode('00000000000135c5003f2ef5f4c12000003f800000000000003f112e810000000000000001','hex'));
