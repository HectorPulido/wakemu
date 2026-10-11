-- Local initial NPC placements. Native appearance/name/dialogue, local placement
-- and root selection; this does not claim official spawn points or quest trees.
CREATE TABLE IF NOT EXISTS world_dialogue_npcs (
    actor_id bigint PRIMARY KEY CHECK (actor_id BETWEEN -4503599627370495 AND -2251799813685248),
    reference_id smallint NOT NULL CHECK (reference_id > 0),
    map_id integer NOT NULL CHECK (map_id > 0),
    instance_id bigint NOT NULL DEFAULT 0 CHECK (instance_id >= 0),
    x integer NOT NULL,
    y integer NOT NULL,
    z smallint NOT NULL,
    direction smallint NOT NULL DEFAULT 3 CHECK (direction BETWEEN 0 AND 7),
    dialogue_root integer NOT NULL CHECK (dialogue_root > 0),
    action_ids jsonb NOT NULL CHECK (jsonb_typeof(action_ids) = 'array'),
    interaction_range smallint NOT NULL DEFAULT 4 CHECK (interaction_range BETWEEN 1 AND 12),
    enabled boolean NOT NULL DEFAULT true,
    provenance text NOT NULL,
    UNIQUE (map_id, instance_id, x, y, z)
);
CREATE INDEX IF NOT EXISTS world_dialogue_npcs_scene ON world_dialogue_npcs(map_id,instance_id) WHERE enabled;
INSERT INTO world_dialogue_npcs(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,provenance)
VALUES (-2251799813685248,2986,1134,0,-10,-8,-1,3,6274,'[515]'::jsonb,
'Local Wakemu initial placement near default character start; native aMb2986 START_DIALOG515; aKO6274 portrait npc2986 and localized speaker Arh Kayuh. Initial dialogue only, no official decision tree or quest grants.'),
(-2251799813685249,3814,1134,0,-12,-10,-1,3,6554,'[698]'::jsonb,
'Local Wakemu initial placement near default character start; native aMb3814 START_DIALOG698; aKO6554 portrait npc3814 and localized speaker Laura Craft. Initial dialogue only, no official decision tree or quest grants.'),
(-2251799813685250,4687,1134,0,-14,-8,-1,3,7122,'[968]'::jsonb,
'Local Wakemu initial placement near default character start; native aMb4687 START_DIALOG968; aKO7122 portrait npc4687 and localized speaker Tristepin. Initial dialogue only, no official decision tree or quest grants.'),
(-2251799813685251,3580,1134,0,-12,-6,-1,3,7279,'[673]'::jsonb,
'Local Wakemu initial placement near default character start; native aMb3580 START_DIALOG673; aKO7279 portrait npc3580 and localized speaker Kabrok. Initial dialogue only, no official decision tree or quest grants.')
ON CONFLICT(actor_id) DO NOTHING;
