-- Native rE/aAS world orientation, separate from fight action sequencing.
ALTER TABLE characters ADD COLUMN direction smallint NOT NULL DEFAULT 3
    CHECK (direction BETWEEN 0 AND 7);
