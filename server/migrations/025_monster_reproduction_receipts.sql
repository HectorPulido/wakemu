CREATE TABLE monster_reproduction_timers (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    reference integer NOT NULL,
    remaining_ms bigint NOT NULL CHECK (remaining_ms>=0),
    last_active_ms bigint,
    observer_generation text,
    due boolean NOT NULL DEFAULT false,
    cycle bigint NOT NULL DEFAULT 0 CHECK (cycle>=0),
    PRIMARY KEY(map_id,instance_id,monster_id),
    FOREIGN KEY(map_id,instance_id,monster_id)
        REFERENCES combat_group_members(map_id,instance_id,monster_id) ON DELETE CASCADE
);
CREATE TABLE monster_reproduction_receipts (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    cycle bigint NOT NULL CHECK (cycle>0),
    parent_group_id bigint NOT NULL,
    parent_reference integer NOT NULL,
    child_id bigint CHECK (child_id<0),
    child_group_id bigint CHECK (child_group_id>0),
    child jsonb CHECK (jsonb_typeof(child)='object'),
    draw double precision NOT NULL CHECK (draw>=0 AND draw<1),
    probability double precision NOT NULL CHECK (probability>=0 AND probability<=1),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy)='object'),
    PRIMARY KEY(map_id,instance_id,monster_id,cycle),
    CHECK ((child_id IS NULL)=(child_group_id IS NULL)),
    CHECK ((child_id IS NULL)=(child IS NULL))
);
CREATE TABLE monster_reproduction_outbox (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    cycle bigint NOT NULL,
    group_id bigint NOT NULL,
    revision bigint NOT NULL,
    new_group boolean NOT NULL,
    published boolean NOT NULL DEFAULT false,
    PRIMARY KEY(map_id,instance_id,monster_id,cycle,group_id),
    FOREIGN KEY(map_id,instance_id,monster_id,cycle)
        REFERENCES monster_reproduction_receipts(map_id,instance_id,monster_id,cycle)
);
CREATE INDEX monster_reproduction_outbox_pending
    ON monster_reproduction_outbox(map_id,instance_id) WHERE NOT published;
