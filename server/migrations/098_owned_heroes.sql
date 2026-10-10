-- Native company UI exposes one main character and two hero slots.
CREATE TABLE account_hero_rosters (
 account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
 leader_id bigint NOT NULL,
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 FOREIGN KEY(account_id,leader_id) REFERENCES characters(account_id,id)
);
CREATE TABLE account_hero_slots (
 account_id bigint NOT NULL REFERENCES account_hero_rosters(account_id) ON DELETE CASCADE,
 slot smallint NOT NULL CHECK(slot BETWEEN 0 AND 1),
 character_id bigint NOT NULL,
 PRIMARY KEY(account_id,slot),
 UNIQUE(account_id,character_id),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
