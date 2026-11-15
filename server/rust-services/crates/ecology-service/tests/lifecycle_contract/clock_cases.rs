//! Migrated active-clock cases from test_monster_maturation.py,
//! test_monster_reproduction_tick.py and test_monster_reproduction_dungeons.py.
//! The production Rust observer owns elapsed time; World attempts use frozen SQL fixtures.
use super::*;

async fn observe(
    f: &Fixture,
    kind: &str,
    now: i64,
    present: bool,
    generation: &str,
    excluded: &[i64],
    eligible: &[i32],
    configuration: &Value,
) -> Result<Vec<Value>> {
    life::observe(
        &f.ctx,
        1134,
        0,
        present,
        generation,
        now,
        &excluded.iter().copied().collect(),
        kind,
        &eligible.iter().copied().collect(),
        configuration,
    )
    .await
}
async fn counts(f: &Fixture, kind: &str) -> Result<i64> {
    Ok(f.ctx
        .db
        .get()
        .await?
        .query_one(&format!("SELECT count(*) FROM monster_{kind}_timers"), &[])
        .await?
        .get(0))
}
async fn register_pair(f: &Fixture) -> Result<()> {
    f.group(1134, 0, 1, 2, -1, "available").await?;
    f.group(1134, 0, 2, 39, -2, "available").await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn observe_batches_hundred_growable_members_and_terminal_deletion() -> Result<()> {
    // Replaces the old pre-life-plan literal-five-query assertions with actual
    // PostgreSQL per-statement audit triggers: the native writes remain bounded.
    let f = Fixture::new().await?;
    for i in 0..100 {
        f.group(1134, 0, 1000 + i, 2, -1000 - i, "available")
            .await?;
    }
    let db = f.ctx.db.get().await?;
    db.batch_execute("CREATE TABLE clock_statement_audit(operation text); CREATE FUNCTION audit_clock_statement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN INSERT INTO clock_statement_audit VALUES(TG_OP); RETURN NULL; END $$; CREATE TRIGGER clock_statement AFTER INSERT OR UPDATE OR DELETE ON monster_maturation_timers FOR EACH STATEMENT EXECUTE FUNCTION audit_clock_statement()").await?;
    drop(db);
    let due = observe(
        &f,
        "maturation",
        100,
        true,
        "batched",
        &[],
        &[2],
        &policy("maturation"),
    )
    .await?;
    assert!(due.is_empty());
    assert_eq!(counts(&f, "maturation").await?, 100);
    let db = f.ctx.db.get().await?;
    let rows=db.query("SELECT operation,count(*) FROM clock_statement_audit GROUP BY operation ORDER BY operation",&[]).await?;
    assert_eq!(
        rows.iter()
            .map(|r| (r.get::<_, String>(0), r.get::<_, i64>(1)))
            .collect::<Vec<_>>(),
        vec![
            ("DELETE".to_owned(), 1),
            ("INSERT".to_owned(), 1),
            ("UPDATE".to_owned(), 1)
        ]
    );
    db.execute(
        "UPDATE combat_groups SET members=jsonb_set(members,'{0,ref}','44') WHERE group_id=1000",
        &[],
    )
    .await?;
    db.execute("TRUNCATE clock_statement_audit", &[]).await?;
    drop(db);
    observe(
        &f,
        "maturation",
        100,
        true,
        "batched",
        &[],
        &[2],
        &policy("maturation"),
    )
    .await?;
    assert_eq!(counts(&f, "maturation").await?, 99);
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one(
            "SELECT count(*) FROM clock_statement_audit WHERE operation='DELETE'",
            &[]
        )
        .await?
        .get::<_, i64>(0),
        2
    );
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn absent_observation_uses_only_guarded_timer_update() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    observe(
        &f,
        "maturation",
        100,
        true,
        "absent",
        &[],
        &[2],
        &policy("maturation"),
    )
    .await?;
    // Absence must not load policy/group/catalog authority, including malformed
    // policy input. Remove these relations to make an accidental read visible.
    let db = f.ctx.db.get().await?;
    db.execute("ALTER TABLE combat_groups RENAME TO parked_groups", &[])
        .await?;
    db.execute("DROP TABLE settings", &[]).await?;
    drop(db);
    assert!(observe(
        &f,
        "maturation",
        500000,
        false,
        "absent",
        &[],
        &[],
        &Value::Null
    )
    .await?
    .is_empty());
    let row = f.timer("maturation", 1134, 0, -1).await?;
    assert_eq!(row["remaining_ms"], 60000);
    assert!(row["last_active_ms"].is_null());
    assert_eq!(row["due"], false);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn tied_catalog_alternatives_get_independent_valid_level_clocks() -> Result<()> {
    let f = Fixture::new().await?;
    register_pair(&f).await?;
    assert!(observe(
        &f,
        "maturation",
        100,
        true,
        "ties",
        &[],
        &[2, 39],
        &policy("maturation")
    )
    .await?
    .is_empty());
    for (id, reference) in [(-1, 2), (-2, 39)] {
        let row = f.timer("maturation", 1134, 0, id).await?;
        assert_eq!(row["reference"], reference);
        assert_eq!(row["remaining_ms"], 60000);
        assert_eq!(row["observer_generation"], "ties");
    }
    let due = observe(
        &f,
        "maturation",
        60100,
        true,
        "ties",
        &[-2],
        &[2, 39],
        &policy("maturation"),
    )
    .await?;
    assert_eq!(due.len(), 1);
    assert_eq!(due[0]["monster_id"], -1);
    assert_eq!(
        f.timer("maturation", 1134, 0, -2).await?["remaining_ms"],
        60000
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn miaumiau_stages_require_full_active_interval_after_each_transition() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2616, -1, "available").await?;
    let mut p = policy("maturation");
    p["interval_ms"] = json!(900000);
    assert!(observe(
        &f,
        "maturation",
        0,
        true,
        "miau-a",
        &[],
        &[2616, 2598, 1816],
        &p
    )
    .await?
    .is_empty());
    assert!(observe(
        &f,
        "maturation",
        899999,
        true,
        "miau-a",
        &[],
        &[2616, 2598, 1816],
        &p
    )
    .await?
    .is_empty());
    assert_eq!(f.timer("maturation", 1134, 0, -1).await?["remaining_ms"], 1);
    assert_eq!(
        observe(
            &f,
            "maturation",
            900000,
            true,
            "miau-a",
            &[],
            &[2616, 2598, 1816],
            &p
        )
        .await?[0]["cycle"],
        1
    );
    // The retained Python World test commits both real native transitions and
    // checks receipt/reset fields. Here simulate its already committed reset.
    let db = f.ctx.db.get().await?;
    db.execute(
        "UPDATE combat_groups SET members=jsonb_set(members,'{0,ref}','2598')",
        &[],
    )
    .await?;
    db.execute("UPDATE monster_maturation_timers SET reference=2598,remaining_ms=900000,due=false,last_active_ms=NULL",&[]).await?;
    drop(db);
    observe(
        &f,
        "maturation",
        900000,
        true,
        "miau-a",
        &[],
        &[2616, 2598, 1816],
        &p,
    )
    .await?;
    observe(
        &f,
        "maturation",
        1200000,
        true,
        "miau-a",
        &[],
        &[2616, 2598, 1816],
        &p,
    )
    .await?;
    assert_eq!(
        f.timer("maturation", 1134, 0, -1).await?["remaining_ms"],
        600000
    );
    observe(
        &f,
        "maturation",
        1250000,
        false,
        "miau-a",
        &[],
        &[],
        &Value::Null,
    )
    .await?;
    observe(
        &f,
        "maturation",
        10000000,
        true,
        "miau-b",
        &[],
        &[2616, 2598, 1816],
        &p,
    )
    .await?;
    assert_eq!(
        f.timer("maturation", 1134, 0, -1).await?["remaining_ms"],
        600000
    );
    assert!(observe(
        &f,
        "maturation",
        10599999,
        true,
        "miau-b",
        &[],
        &[2616, 2598, 1816],
        &p
    )
    .await?
    .is_empty());
    let due = observe(
        &f,
        "maturation",
        10600000,
        true,
        "miau-b",
        &[],
        &[2616, 2598, 1816],
        &p,
    )
    .await?;
    assert_eq!(due.len(), 1);
    assert_eq!(due[0]["reference"], 2598);
    assert_eq!(due[0]["cycle"], 2);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn clock_policy_is_frozen_per_monster_and_new_rows_use_updates() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    let first = policy("maturation");
    observe(&f, "maturation", 0, true, "policy", &[], &[2], &first).await?;
    f.group(1134, 0, 2, 2, -2, "available").await?;
    let mut next = first.clone();
    next["interval_ms"] = json!(90000);
    observe(&f, "maturation", 0, true, "policy", &[], &[2], &next).await?;
    assert_eq!(
        f.timer("maturation", 1134, 0, -1).await?["remaining_ms"],
        60000
    );
    assert_eq!(
        f.timer("maturation", 1134, 0, -2).await?["remaining_ms"],
        90000
    );
    let db = f.ctx.db.get().await?;
    let rows = db
        .query(
            "SELECT monster_id,policy FROM monster_life_plans ORDER BY monster_id DESC",
            &[],
        )
        .await?;
    assert_eq!(rows[0].get::<_, Value>(1), first);
    assert_eq!(rows[1].get::<_, Value>(1), next);
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn combat_and_harvest_exclusions_freeze_elapsed_time() -> Result<()> {
    let f = Fixture::new().await?;
    register_pair(&f).await?;
    let p = policy("maturation");
    observe(&f, "maturation", 0, true, "pause", &[], &[2, 39], &p).await?;
    observe(&f, "maturation", 30000, true, "pause", &[], &[2, 39], &p).await?;
    let db = f.ctx.db.get().await?;
    db.execute(
        "UPDATE combat_groups SET status='fighting' WHERE group_id=1",
        &[],
    )
    .await?;
    drop(db);
    observe(&f, "maturation", 500000, true, "pause", &[-2], &[2, 39], &p).await?;
    for id in [-1, -2] {
        let row = f.timer("maturation", 1134, 0, id).await?;
        assert_eq!(row["remaining_ms"], 30000);
        assert!(row["last_active_ms"].is_null());
    }
    let db = f.ctx.db.get().await?;
    db.execute(
        "UPDATE combat_groups SET status='available' WHERE group_id=1",
        &[],
    )
    .await?;
    drop(db);
    assert!(
        observe(&f, "maturation", 700000, true, "pause", &[], &[2, 39], &p)
            .await?
            .is_empty()
    );
    assert!(
        observe(&f, "maturation", 729999, true, "pause", &[], &[2, 39], &p)
            .await?
            .is_empty()
    );
    assert_eq!(
        observe(&f, "maturation", 730000, true, "pause", &[], &[2, 39], &p)
            .await?
            .len(),
        2
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn new_observer_and_presence_generation_do_not_catch_up_offline_time() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    let p = policy("maturation");
    observe(&f, "maturation", 0, true, "epoch:presence:1", &[], &[2], &p).await?;
    observe(
        &f,
        "maturation",
        30000,
        true,
        "epoch:presence:1",
        &[],
        &[2],
        &p,
    )
    .await?;
    assert!(observe(
        &f,
        "maturation",
        1000000,
        true,
        "epoch:presence:2",
        &[],
        &[2],
        &p
    )
    .await?
    .is_empty());
    assert_eq!(
        f.timer("maturation", 1134, 0, -1).await?["remaining_ms"],
        30000
    );
    assert!(
        observe(&f, "maturation", 2000000, true, "new-epoch", &[], &[2], &p)
            .await?
            .is_empty()
    );
    assert_eq!(
        f.timer("maturation", 1134, 0, -1).await?["remaining_ms"],
        30000
    );
    assert_eq!(
        observe(&f, "maturation", 2030000, true, "new-epoch", &[], &[2], &p)
            .await?
            .len(),
        1
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn due_cycle_is_claimed_once_and_reopens_durably() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    let p = policy("maturation");
    observe(&f, "maturation", 0, true, "due", &[], &[2], &p).await?;
    let due = observe(&f, "maturation", 60000, true, "due", &[], &[2], &p).await?;
    assert_eq!(due.len(), 1);
    assert_eq!(due[0]["cycle"], 1);
    assert!(
        observe(&f, "maturation", 120000, true, "due", &[], &[2], &p)
            .await?
            .is_empty()
    );
    let pending = life::pending(&f.ctx, 1134, 0, "maturation").await?;
    assert_eq!(pending, due);
    // A fresh owner object reads the same committed PostgreSQL cycle.
    let reopened = Context {
        db: f.ctx.db.clone(),
        catalog: Catalog::new(f.ctx.db.clone(), "a".repeat(64), None),
    };
    assert_eq!(life::pending(&reopened, 1134, 0, "maturation").await?, due);
    drop(reopened);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn reference_change_resets_clock_but_keeps_cycle_number() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    let p = policy("maturation");
    observe(&f, "maturation", 0, true, "ref", &[], &[2, 39], &p).await?;
    let db = f.ctx.db.get().await?;
    db.execute(
        "UPDATE monster_maturation_timers SET cycle=9,due=true,remaining_ms=0",
        &[],
    )
    .await?;
    db.execute(
        "UPDATE combat_groups SET members=jsonb_set(members,'{0,ref}','39')",
        &[],
    )
    .await?;
    drop(db);
    assert!(
        observe(&f, "maturation", 100000, true, "ref", &[], &[2, 39], &p)
            .await?
            .is_empty()
    );
    let timer = f.timer("maturation", 1134, 0, -1).await?;
    assert_eq!(timer["reference"], 39);
    assert_eq!(timer["cycle"], 9);
    assert_eq!(timer["remaining_ms"], 60000);
    assert_eq!(timer["due"], false);
    assert!(timer["last_active_ms"].is_null());
    assert!(timer["observer_generation"].is_null());
    observe(&f, "maturation", 100000, true, "ref", &[], &[2, 39], &p).await?;
    assert_eq!(
        observe(&f, "maturation", 160000, true, "ref", &[], &[2, 39], &p).await?[0]["cycle"],
        10
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn terminal_and_unrecognized_references_do_not_get_clocks() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 44, -1, "available").await?;
    f.group(1134, 0, 2, 999999, -2, "available").await?;
    assert!(observe(
        &f,
        "maturation",
        0,
        true,
        "terminal",
        &[],
        &[2, 39],
        &policy("maturation")
    )
    .await?
    .is_empty());
    assert_eq!(counts(&f, "maturation").await?, 0);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn active_reproduction_clock_pauses_when_absent_or_restarted_and_initial_offspring_get_clocks(
) -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    f.group(1134, 0, 2, 4, -2, "available").await?;
    let p = policy("reproduction");
    observe(&f, "reproduction", 0, true, "first", &[], &[2, 4], &p).await?;
    observe(&f, "reproduction", 30000, true, "first", &[], &[2, 4], &p).await?;
    observe(
        &f,
        "reproduction",
        90000,
        false,
        "first",
        &[],
        &[],
        &Value::Null,
    )
    .await?;
    observe(
        &f,
        "reproduction",
        500000,
        true,
        "restart",
        &[],
        &[2, 4],
        &p,
    )
    .await?;
    for id in [-1, -2] {
        let row = f.timer("reproduction", 1134, 0, id).await?;
        assert_eq!(row["remaining_ms"], 30000);
        assert_eq!(row["due"], false);
    }
    assert!(observe(
        &f,
        "reproduction",
        529999,
        true,
        "restart",
        &[],
        &[2, 4],
        &p
    )
    .await?
    .is_empty());
    assert_eq!(
        observe(
            &f,
            "reproduction",
            530000,
            true,
            "restart",
            &[],
            &[2, 4],
            &p
        )
        .await?
        .len(),
        2
    );
    f.group(1134, 0, 3, 2, -3, "available").await?;
    observe(
        &f,
        "reproduction",
        590000,
        true,
        "restart",
        &[],
        &[2, 4],
        &p,
    )
    .await?;
    let child = f.timer("reproduction", 1134, 0, -3).await?;
    assert_eq!(child["reference"], 2);
    assert_eq!(child["remaining_ms"], 60000);
    assert_eq!(child["cycle"], 0);
    assert_eq!(counts(&f, "reproduction").await?, 3);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn all_room_maps_block_timers_pending_births_and_old_outbox() -> Result<()> {
    let f = Fixture::new().await?;
    f.ctx
        .db
        .get()
        .await?
        .execute("INSERT INTO dungeon_instances VALUES(700)", &[])
        .await?;
    for map in [1086, 1234, 9999] {
        f.group(map, 700, map as i64, 4, -(map as i64), "available")
            .await?;
        assert!(life::observe(
            &f.ctx,
            map,
            700,
            true,
            "dungeon",
            1000,
            &HashSet::new(),
            "reproduction",
            &HashSet::from([4]),
            &policy("reproduction")
        )
        .await?
        .is_empty());
        assert!(life::pending(&f.ctx, map, 700, "reproduction")
            .await?
            .is_empty());
        assert!(life::unpublished(&f.ctx, map, 700, "reproduction")
            .await?
            .is_empty());
    }
    assert_eq!(counts(&f, "reproduction").await?, 0);
    assert!(!life::dungeon_population(&f.ctx, 0).await?);
    assert!(!life::dungeon_population(&f.ctx, 701).await?);
    assert!(life::dungeon_population(&f.ctx, 700).await?);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn exterior_observation_still_enters_active_clock_engine() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    observe(
        &f,
        "reproduction",
        1234,
        true,
        "exterior",
        &[],
        &[4],
        &policy("reproduction"),
    )
    .await?;
    let row = f.timer("reproduction", 1134, 0, -1).await?;
    assert_eq!(row["last_active_ms"], 1234);
    assert_eq!(row["remaining_ms"], 60000);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn absent_location_pauses_clock_without_charging_offline_gap() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 2, -1, "available").await?;
    let p = policy("maturation");
    observe(&f, "maturation", 0, true, "gap", &[], &[2], &p).await?;
    observe(
        &f,
        "maturation",
        50000,
        false,
        "gap",
        &[],
        &[],
        &Value::Null,
    )
    .await?;
    assert!(
        observe(&f, "maturation", 100000, true, "gap", &[], &[2], &p)
            .await?
            .is_empty()
    );
    let row = f.timer("maturation", 1134, 0, -1).await?;
    assert_eq!(row["remaining_ms"], 60000);
    assert_eq!(row["last_active_ms"], 100000);
    assert_eq!(
        observe(&f, "maturation", 160000, true, "gap", &[], &[2], &p)
            .await?
            .len(),
        1
    );
    f.close().await
}
