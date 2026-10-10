-- One authoritative Haven Bag per account. Retain physical gem UIDs and plant
-- instance identities by selecting an existing durable character bag.
-- Other character bags are retained as migration archives; never discard items.
CREATE TABLE account_haven_bags (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    character_id bigint NOT NULL UNIQUE REFERENCES haven_bags(character_id)
);
INSERT INTO account_haven_bags(account_id, character_id)
SELECT DISTINCT ON (c.account_id) c.account_id, c.id
FROM characters c JOIN haven_bags h ON h.character_id=c.id
ORDER BY c.account_id,
    (SELECT count(*) FROM haven_bag_gems g WHERE g.character_id=c.id) DESC,
    jsonb_array_length(h.furniture) DESC,
    (SELECT count(*) FROM planted_resources p WHERE p.map_id=9 AND p.instance_id=c.id) DESC,
    c.id;
