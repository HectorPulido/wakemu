CREATE TABLE monster_maturation_receipts (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    cycle bigint NOT NULL CHECK (cycle>0),
    group_id bigint NOT NULL,
    from_reference integer NOT NULL,
    to_reference integer,
    draw double precision NOT NULL CHECK (draw>=0 AND draw<1),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy)='object'),
    PRIMARY KEY(map_id,instance_id,monster_id,cycle)
);
CREATE TABLE monster_maturation_outbox (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    cycle bigint NOT NULL,
    group_id bigint NOT NULL,
    revision bigint NOT NULL,
    published boolean NOT NULL DEFAULT false,
    PRIMARY KEY(map_id,instance_id,monster_id,cycle),
    FOREIGN KEY(map_id,instance_id,monster_id,cycle)
        REFERENCES monster_maturation_receipts(map_id,instance_id,monster_id,cycle)
);
CREATE INDEX monster_maturation_outbox_pending ON monster_maturation_outbox(map_id,instance_id)
    WHERE NOT published;
