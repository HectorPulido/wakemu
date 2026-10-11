-- Authoritative chat nation membership; missing membership means neutral.
-- Membership must come from trusted nation enrollment, never a chat packet or map.
CREATE TABLE character_chat_nations (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    nation_id integer NOT NULL CHECK (nation_id > 0)
);
CREATE INDEX character_chat_nations_nation ON character_chat_nations(nation_id, character_id);
