ALTER TABLE combat_fight_participants
    ADD COLUMN entry_hp integer,
    ADD COLUMN entry_max_hp integer,
    ADD COLUMN entry_hp_damage integer,
    ADD COLUMN entry_health_dead boolean;

ALTER TABLE combat_fight_participants
    ADD CONSTRAINT combat_fight_participants_health_baseline_complete
    CHECK (
        (entry_hp IS NULL AND entry_max_hp IS NULL
            AND entry_hp_damage IS NULL AND entry_health_dead IS NULL)
        OR
        (entry_hp IS NOT NULL AND entry_max_hp IS NOT NULL
            AND entry_hp_damage IS NOT NULL AND entry_health_dead IS NOT NULL
            AND entry_hp BETWEEN 0 AND entry_max_hp
            AND entry_max_hp > 0 AND entry_hp_damage >= 0)
    );
