INSERT INTO settings(name,value) VALUES
 ('player_party_policy','{"version":1,"max_members":6,"invitation_seconds":60}');

CREATE TABLE player_parties (
 id bigint GENERATED ALWAYS AS IDENTITY
 (START WITH 72057594037927937 MAXVALUE 144115188075855871) PRIMARY KEY,
 leader_id bigint NOT NULL REFERENCES characters(id) ON DELETE RESTRICT,
 revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0)
);
CREATE TABLE player_party_members (
 character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE RESTRICT,
 party_id bigint NOT NULL REFERENCES player_parties(id) ON DELETE CASCADE,
 joined_order bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 UNIQUE(party_id,character_id)
);
ALTER TABLE player_parties ADD CONSTRAINT player_party_leader_membership
 FOREIGN KEY(id,leader_id) REFERENCES player_party_members(party_id,character_id)
 DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE player_party_invitations (
 token uuid PRIMARY KEY,
 inviter_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 invitee_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 inviter_generation text NOT NULL,
 invitee_generation text NOT NULL,
 expires_at timestamptz NOT NULL,
 CHECK(inviter_id != invitee_id),
 UNIQUE(inviter_id,invitee_id)
);
CREATE INDEX player_party_invitation_expiry ON player_party_invitations(expires_at);
