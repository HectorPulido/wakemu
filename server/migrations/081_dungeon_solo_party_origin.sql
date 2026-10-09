-- Only dungeon entry may create a temporary singleton party.
-- Existing social identities are deliberately not inferred from roster size.
ALTER TABLE player_parties ADD COLUMN dungeon_solo boolean NOT NULL DEFAULT false;
