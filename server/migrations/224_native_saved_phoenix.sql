-- Original rC/fyl saved RespawnPoint identity; zero means not linked.
ALTER TABLE characters ADD COLUMN saved_phoenix_id integer NOT NULL DEFAULT 0
    CHECK (saved_phoenix_id >= 0);
