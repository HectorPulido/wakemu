-- Optional reviewed client Lua action, executed for the interacting owner.
ALTER TABLE quest_interactive_bindings
    ADD COLUMN script_id integer NOT NULL DEFAULT 0 CHECK (script_id >= 0);
