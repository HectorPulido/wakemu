CREATE TABLE account_professions (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    profession_id integer NOT NULL CHECK (profession_id > 0),
    xp bigint NOT NULL DEFAULT 0 CHECK (xp BETWEEN 0 AND 3000000),
    counters integer[] NOT NULL DEFAULT ARRAY[0,0,0,0]
        CHECK (cardinality(counters)=4 AND array_ndims(counters)=1
               AND array_position(counters,NULL) IS NULL AND 0 <= ALL(counters)),
    actions integer[] NOT NULL DEFAULT ARRAY[]::integer[]
        CHECK (cardinality(actions)<=65536 AND COALESCE(array_ndims(actions),1)=1
               AND array_position(actions,NULL) IS NULL AND 0 <= ALL(actions)),
    PRIMARY KEY (account_id, profession_id)
);
-- Preserve the greatest known level per account. No partial XP existed.
INSERT INTO account_professions(account_id,profession_id,xp)
SELECT c.account_id,p.profession_id,75::bigint*max(p.level)*max(p.level)
FROM character_professions p JOIN characters c ON c.id=p.character_id
GROUP BY c.account_id,p.profession_id;
DROP TABLE character_professions;
CREATE TABLE account_craft_state (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    configuration bytea NOT NULL DEFAULT decode('0800','hex'),
    additional bytea NOT NULL DEFAULT decode('18002000','hex')
);
INSERT INTO settings(name,value) VALUES
    ('profession_xp','{"multiplier_basis_points":10000}');
CREATE TABLE profession_xp_receipts (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    operation text NOT NULL CHECK (length(operation) BETWEEN 1 AND 128),
    profession_id integer NOT NULL,
    character_id bigint NOT NULL,
    applied_xp bigint NOT NULL CHECK (applied_xp BETWEEN 0 AND 3000000),
    PRIMARY KEY (account_id,operation,profession_id),
    FOREIGN KEY (account_id,profession_id)
        REFERENCES account_professions(account_id,profession_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id,character_id)
        REFERENCES characters(account_id,id) ON DELETE CASCADE
);
