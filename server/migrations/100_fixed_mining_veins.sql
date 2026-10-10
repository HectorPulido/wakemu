-- Fixed mineral placements are independent of plant growth and reproduction.
INSERT INTO settings(name,value) VALUES
('mining_vein_policy','{"version":1,"respawn_seconds":300,"distribution":{"seed":20261010,"density_basis_points":10000,"max_per_map":0,"minimum_spacing":0,"level_scale":50,"level_power":2,"precious_weight_basis_points":200,"coverage_mode":"all_accessible","minimum_per_species":1,"allow_species_ground_fallback":true},"product_selection":{"mode":"native_candidates_weighted","weights":{}}}'::jsonb);

CREATE TABLE mining_vein_slots (
    resource_uid bigint PRIMARY KEY CHECK (resource_uid > 0),
    map_id integer NOT NULL CHECK (map_id > 0),
    instance_id bigint NOT NULL DEFAULT 0 CHECK (instance_id >= 0),
    x integer NOT NULL,
    y integer NOT NULL,
    z smallint NOT NULL,
    resource_reference integer NOT NULL CHECK (resource_reference > 0),
    stage smallint NOT NULL CHECK (stage > 0 AND stage <> 16),
    respawn_seconds integer CHECK (respawn_seconds BETWEEN 1 AND 2678400),
    enabled boolean NOT NULL DEFAULT TRUE,
    active boolean NOT NULL DEFAULT FALSE,
    available_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object' AND provenance <> '{}'::jsonb),
    UNIQUE(map_id,instance_id,x,y)
);
CREATE INDEX mining_vein_slots_due ON mining_vein_slots(available_at,resource_uid)
    WHERE enabled AND NOT active;
