-- Native release retains the original instance and immutable acquisition ledger.
ALTER TABLE account_ranch_creatures
 ADD COLUMN released_at timestamptz,
 ADD COLUMN released_by_character_id bigint REFERENCES characters(id),
 ADD CONSTRAINT account_ranch_creatures_release_actor
 CHECK ((released_at IS NULL) = (released_by_character_id IS NULL));
