-- Keep historical actor references while rekeying only available world actors.
CREATE TABLE npc_actor_identity_aliases (
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 group_id bigint NOT NULL,
 old_actor_id bigint NOT NULL CHECK(old_actor_id<0),
 new_actor_id bigint NOT NULL CHECK(new_actor_id<0 AND new_actor_id>=-9007199254740992),
 repaired_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(map_id,instance_id,old_actor_id),
 UNIQUE(new_actor_id),
 CHECK(old_actor_id<>new_actor_id)
);

-- Timers retain every cycle/deadline field when their member identity changes.
-- Historical receipts/outboxes deliberately keep their original primary keys.
DO $$
DECLARE item record;
BEGIN
 FOR item IN SELECT conrelid::regclass AS relation, conname
  FROM pg_constraint WHERE contype='f'
   AND confrelid='combat_group_members'::regclass
   AND conrelid IN ('monster_maturation_timers'::regclass,
                   'monster_reproduction_timers'::regclass)
 LOOP
  EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I',item.relation,item.conname);
  EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY(map_id,instance_id,monster_id) REFERENCES combat_group_members(map_id,instance_id,monster_id) ON UPDATE CASCADE ON DELETE CASCADE',item.relation,item.conname);
 END LOOP;
END $$;
