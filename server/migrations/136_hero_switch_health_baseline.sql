-- Protect live selected-actor changes before the next idle health tick.
-- Normal login selection retains its existing explicit initialization path.
CREATE OR REPLACE FUNCTION ensure_switched_actor_health_baseline()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.character_id IS NOT NULL
       AND NEW.character_id IS NOT NULL
       AND OLD.character_id IS DISTINCT FROM NEW.character_id THEN
        INSERT INTO character_regeneration
            (character_id, initial_hp, started_at, coefficient, last_at)
        SELECT c.id, c.hp, statement_timestamp(),
               CASE WHEN c.health_dead THEN 0 ELSE 1 END,
               statement_timestamp()
        FROM characters c
        WHERE c.id = NEW.character_id AND c.account_id = NEW.account_id
        ON CONFLICT (character_id) DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS switched_actor_health_baseline ON sessions;
CREATE TRIGGER switched_actor_health_baseline
AFTER UPDATE OF character_id ON sessions
FOR EACH ROW EXECUTE FUNCTION ensure_switched_actor_health_baseline();
