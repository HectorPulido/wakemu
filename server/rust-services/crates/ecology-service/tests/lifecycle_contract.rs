//! Native lifecycle creation replaces retired Python clocks and plan generators.
//! World receipt/fence/failure/publication tests retain explicit SQL fixtures.
use anyhow::{ensure, Context as _, Result};
use deadpool_postgres::Pool;
use serde_json::{json, Value};
use std::collections::HashSet;
use tokio_postgres::{Client, Config, NoTls};
use wakemu_ecology::{catalog::Catalog, planners::mob_lifecycle as life, Context};

struct Fixture {
    admin: Client,
    schema: String,
    ctx: Context,
}
impl Fixture {
    async fn new() -> Result<Self> {
        let dsn = std::env::var("WAKFU_POSTGRES_TEST_URL")
            .context("Explicit private PostgreSQL test DSN required")?;
        let mut config: Config = dsn.parse()?;
        let name = config
            .get_dbname()
            .context("Explicit test database required")?;
        ensure!(
            name.contains("test") && !matches!(name, "wakemu" | "wakemu_runtime"),
            "Refusing a runtime database"
        );
        if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
            config.password(std::fs::read_to_string(path)?.trim());
        }
        let (admin, conn) = config.connect(NoTls).await?;
        tokio::spawn(async move {
            let _ = conn.await;
        });
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        let schema = format!("rust_lifecycle_{}_{}", std::process::id(), nonce);
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema}"));
        let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(8)
            .runtime(deadpool_postgres::Runtime::Tokio1)
            .build()?;
        let db = pool.get().await?;
        db.batch_execute("CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL);
            CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,status text,members jsonb,revision bigint DEFAULT 0,PRIMARY KEY(map_id,instance_id,group_id));
            CREATE TABLE combat_group_members(map_id integer,instance_id bigint,group_id bigint,monster_id bigint,PRIMARY KEY(map_id,instance_id,monster_id),FOREIGN KEY(map_id,instance_id,group_id) REFERENCES combat_groups(map_id,instance_id,group_id) ON DELETE CASCADE);
            CREATE TABLE environmental_owned_groups(instance_id bigint,group_ordinal bigint,map_id integer,world_instance_id bigint,group_id bigint);
            CREATE TABLE environmental_owned_group_members(instance_id bigint,group_ordinal bigint,monster_id bigint);
            CREATE TABLE objectives_public_hunts(map_id integer,group_id bigint);
            CREATE TABLE dungeon_instances(instance_id bigint);
            CREATE TABLE personal_ecology_receipts(id bigint);
            CREATE TABLE ecology_service_proposals(id text);").await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/022_monster_maturation_timers.sql"
        )))
        .await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/023_monster_maturation_receipts.sql"
        )))
        .await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/024_monster_reproduction_policy.sql"
        )))
        .await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/025_monster_reproduction_receipts.sql"
        )))
        .await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/164_monster_life_plans.sql"
        )))
        .await?;
        for kind in ["maturation", "reproduction"] {
            let key = format!("monster_{kind}");
            db.execute(
                "UPDATE settings SET value=$1 WHERE name=$2",
                &[&policy(kind), &key],
            )
            .await?;
        }
        drop(db);
        let ctx = Context {
            db: pool.clone(),
            catalog: Catalog::new(pool, "a".repeat(64), None),
        };
        Ok(Self { admin, schema, ctx })
    }
    async fn group(
        &self,
        map: i32,
        instance: i64,
        gid: i64,
        reference: i32,
        id: i64,
        status: &str,
    ) -> Result<()> {
        let member = json!({"id":id,"ref":reference,"level":1,"map_id":map,"instance_id":instance,"x":0,"y":0,"z":0,"team":1,"hp":100,"max_hp":100});
        let db = self.ctx.db.get().await?;
        db.execute(
            "INSERT INTO combat_groups VALUES($1,$2,$3,$4,$5,0)",
            &[&map, &instance, &gid, &status, &json!([member])],
        )
        .await?;
        db.execute(
            "INSERT INTO combat_group_members VALUES($1,$2,$3,$4)",
            &[&map, &instance, &gid, &id],
        )
        .await?;
        Ok(())
    }
    async fn timer(&self, kind: &str, map: i32, instance: i64, id: i64) -> Result<Value> {
        ensure!(
            matches!(kind, "maturation" | "reproduction"),
            "Invalid test timer kind"
        );
        Ok(self.ctx.db.get().await?.query_one(&format!("SELECT to_jsonb(t) FROM monster_{kind}_timers t WHERE map_id=$1 AND instance_id=$2 AND monster_id=$3"),&[&map,&instance,&id]).await?.get(0))
    }
    async fn close(self) -> Result<()> {
        self.ctx.db.close();
        drop(self.ctx);
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }
}
fn policy(kind: &str) -> Value {
    match kind {
        "maturation" => {
            json!({"interval_ms":60000,"base_probability":0.25,"stage_decay":0.5,"boss_probability":0.00001})
        }
        "reproduction" => {
            json!({"interval_ms":60000,"birth_probability":0.25,"birth_stage_decay":0.5,"new_group_probability":0.5,"max_members":8,"max_zone_members":100000,"max_zone_groups":100000})
        }
        _ => panic!("Invalid test policy kind"),
    }
}
fn ticket(id: i64, gid: i64, reference: i32, cycle: i64) -> Value {
    json!({"map_id":1134,"instance_id":0,"group_id":gid,"monster_id":id,"reference":reference,"cycle":cycle})
}

#[path = "lifecycle_contract/clock_cases.rs"]
mod clock_cases;

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn restart_failures_policy_and_next_block_preserve_original_seed() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    let t = ticket(-1, 1, 4, 1);
    let config = policy("reproduction");
    let first = life::attach(&f.ctx, 1134, 0, "reproduction", &[t.clone()], &config)
        .await?
        .remove(0);
    let reopened = Context {
        db: f.ctx.db.clone(),
        catalog: Catalog::new(f.ctx.db.clone(), "a".repeat(64), None),
    };
    let mut changed = config.clone();
    changed["birth_probability"] = json!(0.9);
    assert_eq!(
        life::attach(&reopened, 1134, 0, "reproduction", &[t.clone()], &changed).await?,
        vec![first.clone()]
    );
    // World owns failure charging; this explicit exhausted receipt state checks
    // that native attachment respects the durable event budget after reopen.
    f.ctx
        .db
        .get()
        .await?
        .execute(
            "UPDATE monster_life_plans SET events=jsonb_set(events,'{0,attempts}','5')",
            &[],
        )
        .await?;
    assert!(
        life::attach(&reopened, 1134, 0, "reproduction", &[t], &changed)
            .await?
            .is_empty()
    );
    let later = life::attach(
        &reopened,
        1134,
        0,
        "reproduction",
        &[ticket(-1, 1, 4, 33)],
        &changed,
    )
    .await?
    .remove(0);
    let db = f.ctx.db.get().await?;
    let row = db
        .query_one("SELECT seed,block_start FROM monster_life_plans", &[])
        .await?;
    let seed: String = row.get(0);
    assert_eq!(row.get::<_, i64>(1), 33);
    drop(db);
    assert_eq!(later["decision"], life::event(&seed, 33)?);
    assert_eq!(later["plan_policy"], config);
    assert_eq!(later["plan_incarnation"], first["plan_incarnation"]);
    drop(reopened);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn defeat_respawn_and_delete_invalidate_old_tickets() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    let t = ticket(-1, 1, 4, 1);
    let config = policy("reproduction");
    let first = life::attach(&f.ctx, 1134, 0, "reproduction", &[t.clone()], &config)
        .await?
        .remove(0);
    let db = f.ctx.db.get().await?;
    db.execute("UPDATE combat_groups SET status='defeated'", &[])
        .await?;
    assert_eq!(
        db.query_one("SELECT count(*) FROM monster_life_plans", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    drop(db);
    assert!(
        life::attach(&f.ctx, 1134, 0, "reproduction", &[t.clone()], &config)
            .await?
            .is_empty()
    );
    f.ctx
        .db
        .get()
        .await?
        .execute("UPDATE combat_groups SET status='available'", &[])
        .await?;
    let respawn = life::attach(&f.ctx, 1134, 0, "reproduction", &[t.clone()], &config)
        .await?
        .remove(0);
    assert_ne!(respawn["plan_incarnation"], first["plan_incarnation"]);
    f.ctx
        .db
        .get()
        .await?
        .execute("DELETE FROM combat_groups", &[])
        .await?;
    assert!(life::attach(&f.ctx, 1134, 0, "reproduction", &[t], &config)
        .await?
        .is_empty());
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM monster_life_plans", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn preexisting_defeated_due_timers_and_ticket_read_before_defeat_cannot_recreate_deleted_plan(
) -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    for kind in ["maturation", "reproduction"] {
        let config = policy(kind);
        let refs = HashSet::from([4]);
        life::observe(
            &f.ctx,
            1134,
            0,
            true,
            "before",
            0,
            &HashSet::new(),
            kind,
            &refs,
            &config,
        )
        .await?;
        life::observe(
            &f.ctx,
            1134,
            0,
            true,
            "before",
            60000,
            &HashSet::new(),
            kind,
            &refs,
            &config,
        )
        .await?;
    }
    let read = life::pending(&f.ctx, 1134, 0, "reproduction").await?;
    assert_eq!(read.len(), 1);
    f.ctx
        .db
        .get()
        .await?
        .execute("UPDATE combat_groups SET status='defeated'", &[])
        .await?;
    for kind in ["maturation", "reproduction"] {
        f.ctx
            .db
            .get()
            .await?
            .execute(
                &format!("UPDATE monster_{kind}_timers SET due=true,remaining_ms=0,cycle=1"),
                &[],
            )
            .await?;
        assert!(life::pending(&f.ctx, 1134, 0, kind).await?.is_empty());
        assert!(life::attach(&f.ctx, 1134, 0, kind, &read, &policy(kind))
            .await?
            .is_empty());
    }
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM monster_life_plans", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn set_based_noops_commit_once_and_reject_stale_or_fighting_rosters() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    let mut config = policy("reproduction");
    config["birth_probability"] = json!(0.0);
    let refs = HashSet::from([4]);
    life::observe(
        &f.ctx,
        1134,
        0,
        true,
        "noop",
        0,
        &HashSet::new(),
        "reproduction",
        &refs,
        &config,
    )
    .await?;
    life::observe(
        &f.ctx,
        1134,
        0,
        true,
        "noop",
        60000,
        &HashSet::new(),
        "reproduction",
        &refs,
        &config,
    )
    .await?;
    let t = life::attach(
        &f.ctx,
        1134,
        0,
        "reproduction",
        &[ticket(-1, 1, 4, 1)],
        &config,
    )
    .await?
    .remove(0);
    let members: Value = f
        .ctx
        .db
        .get()
        .await?
        .query_one("SELECT members FROM combat_groups", &[])
        .await?
        .get(0);
    let proposal = json!({"kind":"reproduction","ticket":t,"configuration":config,"expected_members":members,"draw":t["decision"]["draw"],"noop":true,"_noop_probability":0.0});
    let mut stale = proposal.clone();
    stale["expected_members"] = json!([]);
    life::resolve_noops(&f.ctx, vec![stale]).await?;
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM monster_reproduction_receipts", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    f.ctx
        .db
        .get()
        .await?
        .execute("UPDATE combat_groups SET status='fighting'", &[])
        .await?;
    life::resolve_noops(&f.ctx, vec![proposal.clone()]).await?;
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM monster_reproduction_receipts", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    f.ctx
        .db
        .get()
        .await?
        .execute("UPDATE combat_groups SET status='available'", &[])
        .await?;
    let mut bad = proposal.clone();
    bad["ticket"]["plan_incarnation"] = json!("wrong");
    life::resolve_noops(&f.ctx, vec![bad]).await?;
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM monster_reproduction_receipts", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    assert!(life::resolve_noops(&f.ctx, vec![proposal.clone()])
        .await?
        .is_empty());
    let receipt: Value = f
        .ctx
        .db
        .get()
        .await?
        .query_one(
            "SELECT to_jsonb(r) FROM monster_reproduction_receipts r",
            &[],
        )
        .await?
        .get(0);
    assert!(receipt["child_id"].is_null());
    life::resolve_noops(&f.ctx, vec![proposal]).await?;
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one(
                "SELECT jsonb_agg(to_jsonb(r)) FROM monster_reproduction_receipts r",
                &[]
            )
            .await?
            .get::<_, Value>(0),
        json!([receipt])
    );
    let timer = f.timer("reproduction", 1134, 0, -1).await?;
    assert_eq!(timer["due"], false);
    assert_eq!(timer["remaining_ms"], 60000);
    assert_eq!(
        f.ctx
            .db
            .get()
            .await?
            .query_one("SELECT count(*) FROM personal_ecology_receipts", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn five_thousand_actors_use_batched_attach_and_noop_resolution() -> Result<()> {
    let f = Fixture::new().await?;
    let mut groups = Vec::new();
    let mut tickets = Vec::new();
    for gid in 1..=1000i64 {
        let roster: Vec<Value> = (0..5)
            .map(|j| json!({"id":-(gid*5+j),"ref":4,"x":gid,"y":j,"z":0}))
            .collect();
        for member in &roster {
            tickets.push(ticket(member["id"].as_i64().unwrap(), gid, 4, 1));
        }
        groups.push(json!({"group_id":gid,"members":roster}));
    }
    let db = f.ctx.db.get().await?;
    db.execute("INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) SELECT 1134,0,x.group_id,x.members,'available' FROM jsonb_to_recordset($1) x(group_id bigint,members jsonb)",&[&json!(groups)]).await?;
    db.execute("INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) SELECT 1134,0,x.group_id,x.monster_id FROM jsonb_to_recordset($1) x(group_id bigint,monster_id bigint)",&[&json!(tickets)]).await?;
    db.execute("INSERT INTO monster_reproduction_timers(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) SELECT 1134,0,x.monster_id,4,0,true,1 FROM jsonb_to_recordset($1) x(monster_id bigint)",&[&json!(tickets)]).await?;
    db.batch_execute("CREATE TABLE write_audit(name text); CREATE FUNCTION audit_statement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN INSERT INTO write_audit VALUES(TG_TABLE_NAME||':'||TG_OP); RETURN NULL; END $$; CREATE TRIGGER plans_write AFTER INSERT OR UPDATE ON monster_life_plans FOR EACH STATEMENT EXECUTE FUNCTION audit_statement(); CREATE TRIGGER timer_write AFTER UPDATE ON monster_reproduction_timers FOR EACH STATEMENT EXECUTE FUNCTION audit_statement(); CREATE TRIGGER receipt_write AFTER INSERT ON monster_reproduction_receipts FOR EACH STATEMENT EXECUTE FUNCTION audit_statement();").await?;
    drop(db);
    let mut config = policy("reproduction");
    config["birth_probability"] = json!(0.0);
    let start = std::time::Instant::now();
    let attached = life::attach(&f.ctx, 1134, 0, "reproduction", &tickets, &config).await?;
    assert_eq!(attached.len(), 5000);
    let db = f.ctx.db.get().await?;
    assert!(
        db.query_one("SELECT count(*) FROM write_audit", &[])
            .await?
            .get::<_, i64>(0)
            <= 2
    );
    db.execute("DELETE FROM write_audit", &[]).await?;
    drop(db);
    let by_id: std::collections::HashMap<i64, &Value> = groups
        .iter()
        .map(|g| (g["group_id"].as_i64().unwrap(), &g["members"]))
        .collect();
    let proposals=attached.into_iter().map(|t|{let roster=by_id[&t["group_id"].as_i64().unwrap()];json!({"kind":"reproduction","configuration":config,"expected_members":roster,"draw":t["decision"]["draw"],"ticket":t,"noop":true,"_noop_probability":0.0})}).collect();
    assert!(life::resolve_noops(&f.ctx, proposals).await?.is_empty());
    let db = f.ctx.db.get().await?;
    assert!(
        db.query_one("SELECT count(*) FROM write_audit", &[])
            .await?
            .get::<_, i64>(0)
            <= 2
    );
    for (sql, expected) in [
        ("SELECT count(*) FROM monster_reproduction_receipts", 5000),
        (
            "SELECT count(*) FROM monster_reproduction_timers WHERE due",
            0,
        ),
        ("SELECT count(*) FROM personal_ecology_receipts", 0),
        ("SELECT count(*) FROM ecology_service_proposals", 0),
    ] {
        assert_eq!(db.query_one(sql, &[]).await?.get::<_, i64>(0), expected);
    }
    eprintln!(
        "native lifecycle load: actors=5000, groups=1000, elapsed={:?}",
        start.elapsed()
    );
    drop(db);
    f.close().await
}

#[tokio::test]
async fn finite_challenge_namespace_bypasses_ecology_without_database_or_policy_reads() -> Result<()>
{
    let config: Config =
        "host=127.0.0.1 port=1 user=never dbname=unreachable_test connect_timeout=1".parse()?;
    let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
        .max_size(2)
        .runtime(deadpool_postgres::Runtime::Tokio1)
        .build()?;
    let ctx = Context {
        db: pool.clone(),
        catalog: Catalog::new(pool, "a".repeat(64), None),
    };
    for kind in ["maturation", "reproduction"] {
        assert!(life::observe(
            &ctx,
            1134,
            576460752303423489,
            true,
            "challenge",
            0,
            &HashSet::new(),
            kind,
            &HashSet::from([4]),
            &Value::Null
        )
        .await?
        .is_empty());
    }
    assert!(life::dungeon_population(&ctx, 576460752303423489).await?);
    Ok(())
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn owned_identity_excludes_ordinary_ecology_but_preserves_same_breed_wild_and_collision(
) -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "available").await?;
    f.group(1134, 0, 2, 4, -2, "available").await?;
    let db = f.ctx.db.get().await?;
    db.execute(
        "INSERT INTO environmental_owned_groups VALUES(10,1,1134,0,2)",
        &[],
    )
    .await?;
    db.execute(
        "INSERT INTO environmental_owned_group_members VALUES(10,1,-2)",
        &[],
    )
    .await?;
    db.execute("INSERT INTO monster_maturation_timers(map_id,instance_id,monster_id,reference,remaining_ms) VALUES(1134,0,-2,4,60000)",&[]).await?;
    drop(db);
    life::observe(
        &f.ctx,
        1134,
        0,
        true,
        "owned",
        0,
        &HashSet::new(),
        "maturation",
        &HashSet::from([4]),
        &policy("maturation"),
    )
    .await?;
    let db = f.ctx.db.get().await?;
    let ids: Vec<i64> = db
        .query(
            "SELECT monster_id FROM monster_maturation_timers ORDER BY monster_id",
            &[],
        )
        .await?
        .iter()
        .map(|r| r.get(0))
        .collect();
    assert_eq!(ids, vec![-1]);
    // Eligibility never removes physical actors or their collision coordinates.
    let rosters: Vec<Value> = db
        .query("SELECT members FROM combat_groups ORDER BY group_id", &[])
        .await?
        .iter()
        .map(|r| r.get(0))
        .collect();
    assert_eq!(rosters.len(), 2);
    for roster in rosters {
        assert_eq!(roster[0]["ref"], 4);
        assert_eq!(roster[0]["x"], 0);
        assert_eq!(roster[0]["y"], 0);
    }
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn failed_claim_and_reproduction_observation_never_revive_defeated_group() -> Result<()> {
    let f = Fixture::new().await?;
    f.group(1134, 0, 1, 4, -1, "defeated").await?;
    life::observe(
        &f.ctx,
        1134,
        0,
        true,
        "defeated",
        60000,
        &HashSet::new(),
        "reproduction",
        &HashSet::from([4]),
        &policy("reproduction"),
    )
    .await?;
    assert!(life::pending(&f.ctx, 1134, 0, "reproduction")
        .await?
        .is_empty());
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one("SELECT status FROM combat_groups", &[])
            .await?
            .get::<_, String>(0),
        "defeated"
    );
    assert_eq!(
        db.query_one("SELECT count(*) FROM monster_reproduction_timers", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    drop(db);
    f.close().await
}
