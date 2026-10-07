-- Food effects are exported per model from the installed native fwr data.
-- YH/YJ rows classify healing foods and their heal amount; YI=true rows are
-- XP foods. The composite key preserves the native model-specific contract.
CREATE TABLE mount_feeding_food_policy (
    model_id integer NOT NULL REFERENCES mount_models(model_id) ON DELETE CASCADE,
    item_reference integer NOT NULL CHECK (item_reference > 0),
    effect_kind text NOT NULL CHECK (effect_kind IN ('xp','heal')),
    health_per_item integer NOT NULL DEFAULT 0 CHECK (health_per_item >= 0),
    -- Local duplicate-suppression window, not a native pet feeding cooldown.
    replay_window_ms integer NOT NULL DEFAULT 3000 CHECK (replay_window_ms BETWEEN 0 AND 10000),
    -- This is local policy. Native pet clock effects are not represented by
    -- these food flags; false leaves last_hungry_date untouched by default.
    reset_hungry_clock boolean NOT NULL DEFAULT false,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id,item_reference),
    CHECK (
        (effect_kind='xp' AND health_per_item=0)
        OR (effect_kind='heal' AND health_per_item>0)
    )
);

-- Exact installed-client records: aMp -> YH/YJ and aMr -> YI. Generated for
-- all 40 mount models; non-feed references with YI=false are omitted.
-- The generator/source and complete raw export are kept under .runtime/local.
WITH native_foods(model_id,heals,xp_refs) AS (
    VALUES
        (149,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (116,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (117,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (118,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (119,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (88,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (123,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (124,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (125,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,2734,18378,20785,26399,26416]::integer[]),
        (139,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1846,1851,2355,5407,11479,18378,20785]::integer[]),
        (141,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1846,1851,2355,5407,11479,18378,20785]::integer[]),
        (140,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1846,1851,2355,5407,11479,18378,20785]::integer[]),
        (138,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1846,1851,2355,5407,11479,18378,20785]::integer[]),
        (137,'{}'::jsonb,ARRAY[18378,20785]::integer[]),
        (136,'{}'::jsonb,ARRAY[18378,20785]::integer[]),
        (135,'{}'::jsonb,ARRAY[18378,20785]::integer[]),
        (76,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (82,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (83,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (81,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (146,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (150,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (148,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (104,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,4275,18378,20785]::integer[]),
        (105,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,4275,18378,20785]::integer[]),
        (106,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,4275,18378,20785]::integer[]),
        (107,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,4275,18378,20785]::integer[]),
        (85,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (87,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (84,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (153,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (183,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2254,2698,2702,8104,18378,20785]::integer[]),
        (197,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1851,8414,18378,20595,20785,26399]::integer[]),
        (182,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,5407,18378,20785]::integer[]),
        (155,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (154,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (152,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (209,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1848,11482,18378,20785]::integer[]),
        (86,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[1752,18378,20785]::integer[]),
        (184,'{"12284":1,"13358":1,"18377":20}'::jsonb,ARRAY[2731,6257,8105,9268,18378,20651,20785]::integer[])
), effects AS (
    SELECT model_id,key::integer AS item_reference,'heal'::text AS effect_kind,value::integer AS health_per_item
      FROM native_foods CROSS JOIN LATERAL jsonb_each_text(heals)
    UNION ALL
    SELECT model_id,x.item_reference,'xp'::text,0
      FROM native_foods CROSS JOIN LATERAL unnest(xp_refs) AS x(item_reference)
)
INSERT INTO mount_feeding_food_policy(model_id,item_reference,effect_kind,health_per_item)
SELECT model_id,item_reference,effect_kind,health_per_item FROM effects;

CREATE TABLE mount_feeding_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    character_id bigint NOT NULL,
    generation text NOT NULL CHECK (length(generation)>0),
    pet_uid bigint NOT NULL CHECK (pet_uid > 0),
    food_uid bigint NOT NULL CHECK (food_uid > 0),
    quantity smallint NOT NULL CHECK (quantity BETWEEN 1 AND 32767),
    replay_window_ms integer NOT NULL CHECK (replay_window_ms BETWEEN 0 AND 10000),
    request_sha256 bytea NOT NULL CHECK (octet_length(request_sha256)=32),
    before_revision bigint NOT NULL CHECK (before_revision >= 0),
    after_revision bigint NOT NULL CHECK (after_revision = before_revision + 1),
    applied_at_ms bigint NOT NULL CHECK (applied_at_ms > 0 AND applied_at_ms % 1000=0),
    effect_kind text NOT NULL CHECK (effect_kind IN ('xp','heal')),
    xp_delta integer NOT NULL CHECK (xp_delta >= 0),
    health_delta integer NOT NULL CHECK (health_delta >= 0),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id,character_id)
        REFERENCES characters(account_id,id) ON DELETE CASCADE,
    UNIQUE (pet_uid,after_revision)
);
CREATE INDEX mount_feeding_replay_lookup
    ON mount_feeding_receipts(pet_uid,request_sha256,after_revision DESC);
