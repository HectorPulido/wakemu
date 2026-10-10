-- Explicit local DEV balance, not official Wakfu rift drop rates.
UPDATE settings SET value='{
 "kind":"local_dev_items_v1","version":1,"minimum_completed_waves":1,
 "minimum_defeated_monsters":1,"losses":"none","max_rolls_per_pool":64,
 "pools":[
  {"name":"equipment","category":"item","references":[2021,2022,2023],"every_waves":2,"chance_bp":7500,"quantity_min":1,"quantity_max":1},
  {"name":"enchantment_shards","category":"enchantment","references":[27083],"every_waves":1,"chance_bp":10000,"quantity_min":2,"quantity_max":5},
  {"name":"sublimations","category":"enchantment","references":[27111,27112,27113,27114],"every_waves":4,"chance_bp":2500,"quantity_min":1,"quantity_max":1},
  {"name":"learnable_costumes","category":"appearance","references":[9727,10632,12176],"every_waves":5,"chance_bp":2000,"quantity_min":1,"quantity_max":1}
 ]
}'::jsonb WHERE name='rift_reward_policy';

CREATE TABLE rift_item_reward_receipts (
 instance_id bigint NOT NULL REFERENCES rift_instances(instance_id),
 character_id bigint NOT NULL REFERENCES characters(id),
 fight_id integer NOT NULL,
 policy_snapshot jsonb NOT NULL,
 eligibility_snapshot jsonb NOT NULL,
 PRIMARY KEY(instance_id,character_id),
 FOREIGN KEY(fight_id,character_id) REFERENCES fight_drop_awards(fight_id,character_id)
);
