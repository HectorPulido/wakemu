-- Explicit Wakemu developer policy for original reusable item30532/bIk.
CREATE TABLE developer_item_test_groups (
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 group_id bigint NOT NULL,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 source_uid bigint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP + interval '10 minutes',
 ended_at timestamptz,
 PRIMARY KEY(map_id,instance_id,group_id),
 FOREIGN KEY(map_id,instance_id,group_id) REFERENCES combat_groups(map_id,instance_id,group_id),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE UNIQUE INDEX developer_item_test_groups_one_live_owner
 ON developer_item_test_groups(character_id) WHERE ended_at IS NULL;
CREATE TABLE developer_item_test_fights (
 fight_id bigint PRIMARY KEY REFERENCES combat_fights(id),
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 group_id bigint NOT NULL,
 FOREIGN KEY(map_id,instance_id,group_id)
  REFERENCES developer_item_test_groups(map_id,instance_id,group_id)
);
