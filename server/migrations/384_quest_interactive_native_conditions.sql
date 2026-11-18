ALTER TABLE quest_interactive_bindings
    ADD COLUMN native_criterion text NOT NULL DEFAULT '',
    ADD COLUMN native_effect_reference integer NOT NULL DEFAULT 0
        CHECK (native_effect_reference >= 0);
