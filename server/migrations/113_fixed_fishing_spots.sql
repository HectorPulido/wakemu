-- Native fishing spots have fixed identities and an independent depletion timer.
INSERT INTO settings(name,value) VALUES
    ('fishing_spot_policy', '{"version":1,"respawn_seconds":300}'::jsonb);

CREATE TABLE fishing_spot_slots (
    resource_uid bigint PRIMARY KEY CHECK (resource_uid > 0),
    map_id integer NOT NULL CHECK (map_id > 0),
    instance_id integer NOT NULL DEFAULT 0 CHECK (instance_id = 0),
    x integer NOT NULL,
    y integer NOT NULL,
    z integer NOT NULL,
    resource_reference integer NOT NULL CHECK (resource_reference > 0),
    stage integer NOT NULL CHECK (stage IN (2,3)),
    respawn_seconds integer CHECK (respawn_seconds BETWEEN 1 AND 2678400),
    enabled boolean NOT NULL DEFAULT true,
    active boolean NOT NULL DEFAULT false,
    available_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provenance jsonb NOT NULL CHECK (
        jsonb_typeof(provenance)='object' AND provenance<>'{}'::jsonb
    ),
    UNIQUE (map_id,instance_id,x,y)
);

CREATE INDEX fishing_spot_due
    ON fishing_spot_slots(available_at,resource_uid)
    WHERE enabled AND NOT active;
