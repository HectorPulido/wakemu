-- Keep identity sets and native selection order separate from actor/species pairs.
-- Legacy arrays are deliberately not zipped/backfilled: accepted checkpoint
-- sources must establish their actual association in the reward transaction.
CREATE TABLE rift_wave_actor_bindings (
    instance_id bigint NOT NULL,
    wave integer NOT NULL CHECK (wave > 0),
    ordinal integer NOT NULL CHECK (ordinal >= 0 AND ordinal < 128),
    actor_id bigint NOT NULL CHECK (actor_id < 0),
    species_reference integer NOT NULL CHECK (species_reference > 0),
    binding_source text NOT NULL CHECK (
        binding_source IN ('native_spawn', 'checkpoint_recovery')
    ),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (instance_id, wave, actor_id),
    UNIQUE (instance_id, wave, ordinal),
    UNIQUE (instance_id, actor_id),
    FOREIGN KEY (instance_id, wave) REFERENCES rift_wave_rosters(instance_id, wave)
);

CREATE FUNCTION rift_wave_actor_binding_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Rift actor/species bindings are immutable';
END;
$$;

CREATE TRIGGER rift_wave_actor_binding_immutable
BEFORE UPDATE OR DELETE ON rift_wave_actor_bindings
FOR EACH ROW EXECUTE FUNCTION rift_wave_actor_binding_immutable();
