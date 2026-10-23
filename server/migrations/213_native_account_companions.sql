-- Original bHE activation and eSy account-owned combat companion collection.
-- Reuse the reserved exact-in-Lua actor sequence; identities never alias players.
CREATE TABLE account_companions (
 id bigint PRIMARY KEY DEFAULT nextval('lua_exact_npc_actor_ids'),
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 breed_ref smallint NOT NULL CHECK(breed_ref>0),
 owner_character_id bigint NOT NULL REFERENCES characters(id),
 xp bigint NOT NULL DEFAULT 0 CHECK(xp>=0),
 name text NOT NULL CHECK(octet_length(name) BETWEEN 1 AND 65535),
 unlocked boolean NOT NULL DEFAULT true,
 hp integer NOT NULL CHECK(hp>=0),
 max_hp integer NOT NULL CHECK(max_hp>0 AND hp<=max_hp),
 serialization_version integer NOT NULL DEFAULT 10093002,
 UNIQUE(account_id,breed_ref), UNIQUE(account_id,id),
 FOREIGN KEY(account_id,owner_character_id) REFERENCES characters(account_id,id)
);
CREATE TABLE account_companion_slots (
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 slot smallint NOT NULL CHECK(slot BETWEEN 0 AND 1),
 owner_character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 companion_id bigint NOT NULL,
 PRIMARY KEY(account_id,slot), UNIQUE(companion_id),
 FOREIGN KEY(account_id,companion_id) REFERENCES account_companions(account_id,id) ON DELETE CASCADE,
 FOREIGN KEY(account_id,owner_character_id) REFERENCES characters(account_id,id)
);
CREATE TABLE companion_activation_receipts (
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 source_uid bigint NOT NULL,
 action_id integer NOT NULL,
 character_id bigint NOT NULL REFERENCES characters(id),
 companion_id bigint NOT NULL REFERENCES account_companions(id),
 PRIMARY KEY(account_id,source_uid,action_id)
);
CREATE TABLE combat_fight_companions (
 fight_id bigint NOT NULL REFERENCES combat_fights(id) ON DELETE CASCADE,
 companion_id bigint NOT NULL REFERENCES account_companions(id),
 account_id bigint NOT NULL REFERENCES accounts(id),
 owner_character_id bigint NOT NULL REFERENCES characters(id),
 session_generation text NOT NULL,
 team smallint NOT NULL CHECK(team IN(0,1)),
 health_settled_at timestamptz,
 experience_settled_at timestamptz,
 experience_award bigint CHECK(experience_award>=0),
 owner_experience_award bigint CHECK(owner_experience_award>=0),
 PRIMARY KEY(fight_id,companion_id),
 FOREIGN KEY(account_id,companion_id) REFERENCES account_companions(account_id,id),
 FOREIGN KEY(fight_id,owner_character_id,account_id)
  REFERENCES combat_fight_participants(fight_id,character_id,account_id)
);
