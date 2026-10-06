-- Run against migrations001+002. Test data is always rolled back.
BEGIN;
DO $$
DECLARE
    owner_id bigint;
    other_id bigint;
    char_id bigint;
    other_char bigint;
    bag_id bigint;
    item_id bigint;
BEGIN
    INSERT INTO accounts(username,username_key,salt,password_hash)
        VALUES ('PgOwner','pgowner',decode(repeat('00',16),'hex'),decode('01','hex'))
        RETURNING id INTO owner_id;
    INSERT INTO accounts(username,username_key,salt,password_hash)
        VALUES ('PgOther','pgother',decode(repeat('00',16),'hex'),decode('01','hex'))
        RETURNING id INTO other_id;
    INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp)
        VALUES (owner_id,'Pg Owner','pg owner',8,false,0,0,'[]','{}',20,60)
        RETURNING id INTO char_id;
    INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp)
        VALUES (other_id,'Pg Other','pg other',8,false,0,0,'[]','{}',20,60)
        RETURNING id INTO other_char;
    INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags)
        VALUES (char_id,2175,0,30,0) RETURNING uid INTO bag_id;
    INSERT INTO inventory_items(character_id,reference,quantity,container,slot)
        VALUES (char_id,2021,1,bag_id,0) RETURNING uid INTO item_id;
    IF item_id <= bag_id THEN RAISE EXCEPTION 'Shared allocator failed'; END IF;
    BEGIN
        INSERT INTO inventory_items(character_id,reference,quantity,container,slot)
            VALUES (other_char,2021,1,bag_id,1);
        RAISE EXCEPTION 'Foreign container accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO sessions(account_id,generation,expires_at,character_id)
            VALUES (other_id,'foreign-test',CURRENT_TIMESTAMP + INTERVAL '1 minute',char_id);
        RAISE EXCEPTION 'Foreign selected character accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO inventory_items(character_id,reference,quantity,container,slot)
            VALUES (char_id,2021,1,bag_id,0);
        RAISE EXCEPTION 'Occupied slot accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO inventory_item_elements VALUES (item_id,1,0);
        RAISE EXCEPTION 'Invalid element bit accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    RAISE NOTICE 'PASS: shared UID, owner FKs, occupied slot, element mask';
END $$;
ROLLBACK;
