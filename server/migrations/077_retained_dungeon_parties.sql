-- A dissolved live party may still own durable dungeon history.
-- NULL leader marks that retained identity; it has no live memberships.
-- The deferred composite membership FK uses MATCH SIMPLE for this case.
ALTER TABLE player_parties ALTER COLUMN leader_id DROP NOT NULL;
