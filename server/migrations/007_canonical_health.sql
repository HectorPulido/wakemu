-- Canonical wounds survive temporary reductions of effective maximum HP.
ALTER TABLE characters ADD COLUMN hp_damage bigint NOT NULL DEFAULT 0
    CHECK (hp_damage >= 0);
ALTER TABLE characters ADD COLUMN health_dead boolean NOT NULL DEFAULT false;
UPDATE characters SET hp_damage=max_hp-hp,health_dead=(hp=0);
ALTER TABLE characters ADD CONSTRAINT characters_death_health
    CHECK (health_dead = (hp=0));
ALTER TABLE character_regeneration ADD COLUMN initial_damage bigint NOT NULL DEFAULT 0
    CHECK (initial_damage >= 0);
UPDATE character_regeneration r SET initial_damage=c.hp_damage
    FROM characters c WHERE c.id=r.character_id;

-- A baseline reset snapshots its canonical wound, not just the clamped HUD HP.
-- last_at-only ticks preserve that baseline and its fractional clock.
CREATE FUNCTION regeneration_wound_baseline() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    SELECT hp_damage INTO NEW.initial_damage FROM characters WHERE id=NEW.character_id;
    RETURN NEW;
END;
$$;
CREATE TRIGGER regeneration_wound_baseline BEFORE INSERT OR UPDATE OF initial_hp,started_at,coefficient ON character_regeneration
    FOR EACH ROW EXECUTE FUNCTION regeneration_wound_baseline();
