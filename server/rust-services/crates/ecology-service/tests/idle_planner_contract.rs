//! Native planner replacements for test_monster_birth_home_producer.py and the
//! frozen-episode planning cases in test_monster_idle_distribution_postgres.py.
//! World CAS/race/ledger checks remain Python authority tests with explicit JSON.
use anyhow::{ensure, Context as _, Result};
use deadpool_postgres::Pool;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use tokio_postgres::{Client, Config, NoTls};
use wakemu_ecology::{
    catalog::Catalog,
    planners::{mob_geometry, mob_idle, native_monster, plants},
    Context,
};

struct Fixture {
    admin: Client,
    schema: String,
    ctx: Context,
}
impl Fixture {
    async fn new() -> Result<Self> {
        Self::with_radius(0).await
    }
    async fn with_radius(radius: i64) -> Result<Self> {
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
        let schema = format!("rust_idle_{}_{}", std::process::id(), nonce);
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema}"));
        let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(8)
            .runtime(deadpool_postgres::Runtime::Tokio1)
            .build()?;
        let db = pool.get().await?;
        db.batch_execute("CREATE TABLE native_catalog_releases(revision text PRIMARY KEY,complete boolean); CREATE TABLE native_catalog_active(id integer PRIMARY KEY,revision text);
            CREATE TABLE native_catalog_documents(revision text,path text,raw bytea,sha256 text,source_bytes bigint);
            CREATE TABLE native_compiled_catalog_releases(generation text PRIMARY KEY,source_revision text,complete boolean,manifest_raw bytea,manifest jsonb,policy text,source_inventory_sha256 text,compiler_contract_sha256 text,config_sha256 text);
            CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,status text,members jsonb,revision bigint DEFAULT 0,PRIMARY KEY(map_id,instance_id,group_id));
            CREATE TABLE monster_group_birth_homes(map_id integer,instance_id bigint,group_id bigint,region_id integer);
            CREATE TABLE planting_growth_outbox(published boolean,group_payload jsonb,resource jsonb);
            CREATE TABLE planting_receipts(published boolean,success boolean,group_payload jsonb,resource jsonb);
            CREATE TABLE planted_resources(map_id integer,instance_id bigint,x integer,y integer,resource_uid bigint,stage smallint,creation_time bigint,resource_reference integer);").await?;
        db.batch_execute(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../migrations/314_monster_idle_distribution.sql"
        )))
        .await?;
        let revision = "a".repeat(64);
        db.execute(
            "INSERT INTO native_catalog_releases VALUES($1,true)",
            &[&revision],
        )
        .await?;
        db.execute(
            "INSERT INTO native_catalog_active VALUES(1,$1)",
            &[&revision],
        )
        .await?;
        // A sealed metadata fixture uses the production Catalog verification;
        // actor radii are immutable header records, not a mocked planner.
        let policy = "wakemu.compiled-combat-catalog.v1";
        let config_hash = hex::encode(Sha256::digest(schema.as_bytes()));
        let mut definitions = serde_json::Map::new();
        let mut values = serde_json::Map::new();
        let mut curves = serde_json::Map::new();
        for key in ["1", "2", "3", "4", "9", "32", "35", "92", "97", "100"] {
            let value = match key {
                "1" => 100,
                "2" => 6,
                "3" => 3,
                "9" => 10,
                _ => 0,
            };
            definitions.insert(
                key.into(),
                json!({"hard_minimum":0,"hard_maximum":10000,"expandable":key=="1"}),
            );
            values.insert(
                key.into(),
                json!({"minimum":0,"maximum":if key=="1"{100}else{10000},"current":value}),
            );
            curves.insert(key.into(), json!([value, 0.0]));
        }
        let child_profile =
            json!({"physical_radius":0,"base_level":4,"at_base_level":values,"curves":curves});
        let manifest = json!({"policy":policy,"source_revision":revision,"source_inventory_sha256":"b".repeat(64),"compiler_contract_sha256":"c".repeat(64),"config_sha256":config_hash,"collections":{},"documents":{"native-actor-characteristics.json":{"root_kind":"dict","header":{"npc_profiles":{"2":child_profile,"4":{"physical_radius":radius},"5":{"physical_radius":0},"6":{"physical_radius":0},"7":{"physical_radius":0},"41":{"physical_radius":0}},"characteristics":definitions},"collections":{}}},"raw_documents":{}});
        let raw = serde_json::to_vec(&manifest)?;
        let generation = hex::encode(Sha256::digest(&raw));
        db.execute(
            "INSERT INTO native_compiled_catalog_releases VALUES($1,$2,true,$3,$4,$5,$6,$7,$8)",
            &[
                &generation,
                &revision,
                &raw,
                &manifest,
                &policy,
                &"b".repeat(64),
                &"c".repeat(64),
                &config_hash,
            ],
        )
        .await?;
        drop(db);
        let ctx = Context {
            db: pool.clone(),
            catalog: Catalog::new(pool, revision, Some(generation)),
        };
        Ok(Self { admin, schema, ctx })
    }
    async fn document(&self, path: &str, value: Value) -> Result<()> {
        let raw = serde_json::to_vec(&value)?;
        let digest = hex::encode(Sha256::digest(&raw));
        let size = raw.len() as i64;
        self.ctx
            .db
            .get()
            .await?
            .execute(
                "INSERT INTO native_catalog_documents VALUES($1,$2,$3,$4,$5)",
                &[&"a".repeat(64), &path, &raw, &digest, &size],
            )
            .await?;
        Ok(())
    }
    async fn group(&self, map: i32, gid: i64, roster: Value, home: i32) -> Result<()> {
        let db = self.ctx.db.get().await?;
        db.execute("INSERT INTO combat_groups(map_id,instance_id,group_id,status,members) VALUES($1,0,$2,'available',$3)",&[&map,&gid,&roster]).await?;
        db.execute(
            "INSERT INTO monster_group_birth_homes VALUES($1,0,$2,$3)",
            &[&map, &gid, &home],
        )
        .await?;
        Ok(())
    }
    async fn close(self) -> Result<()> {
        self.ctx.db.close();
        drop(self.ctx);
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }
    async fn home_geometry(&self, inside: bool) -> Result<()> {
        self.document("monsters.json",json!({"monsters":[{"ref":2,"min_level":4,"sprite_id":12345,"statistics":{"HP":{"base":100,"per_level":0},"AP":{"base":6,"per_level":0},"MP":{"base":3,"per_level":0},"WP":{"base":0,"per_level":0},"INIT":{"base":10,"per_level":0}}}]})).await?;
        let origin = [-37, 16, 0];
        let east = [-36, 16, 0];
        let north = [-37, 17, 0];
        let edges = if inside {
            json!([[origin, east], [origin, north]])
        } else {
            json!([[origin, east]])
        };
        self.document(
            "combat-maps/546.json",
            json!({"map_id":546,"cells":[origin,east,north],"edges":edges}),
        )
        .await?;
        self.document("territory-map-cells.json",json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":546,"regions":[{"region_id":62201,"cells":[[-3,0]]},{"region_id":62202,"cells":[[-2,0]]}]}]})).await?;
        self.document("ecology-regions.json",json!([{"map_id":546,"regions":[{"region_id":62201,"monster_families":[{"family_id":999}]}]}])).await?;
        self.document(
            "planting-maps/546.json",
            json!({"cells":[[-37,16,0,0,0,62201],[-36,16,0,0,0,62202],[-37,17,0,0,0,62201]]}),
        )
        .await
    }
}
fn member(reference: i64, id: i64, map: i64, x: i64, y: i64) -> Value {
    json!({"id":id,"ref":reference,"breed":reference,"family_id":316,"level":10,"hp":70,"max_hp":100,"map_id":map,"instance_id":0,"x":x,"y":y,"z":0,"team":1})
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn roaming_foreign_family_keeps_birth_home_without_native_family_gate() -> Result<()> {
    let f = Fixture::new().await?;
    f.home_geometry(true).await?;
    let actor = member(41, -9201, 546, -37, 16);
    let groups = vec![json!({"group_id":9201,"status":"available","members":[actor.clone()]})];
    let snapshot = json!({"world_epoch":"home","players":[{"id":40,"map_id":546,"instance_id":0,"x":-37,"y":19,"z":0}],"excluded_ids":[],"domain_planning_tick":0,"allow_wander":true});
    let policy = json!({"interval_seconds":1,"move_probability":1.0,"radius":20,"min_steps":1,"max_steps":1});
    let proposal = mob_geometry::prepare_scope_wander(
        &f.ctx,
        &snapshot,
        [546, 0],
        &groups,
        &policy,
        &HashMap::from([(9201, 62201)]),
    )
    .await?
    .context("Expected native home-contained movement")?;
    let moved = &proposal["moves"][0];
    assert_eq!(moved["expected_members"], json!([actor]));
    assert_eq!(
        mob_geometry::point(&moved["moved_members"][0])?,
        [-37, 17, 0]
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn reproduction_candidate_and_new_child_stay_within_parent_birth_home() -> Result<()> {
    for inside in [true, false] {
        let f = Fixture::new().await?;
        f.home_geometry(inside).await?;
        let actor = member(41, -9201, 546, -37, 16);
        let groups = vec![json!({"group_id":9201,"status":"available","members":[actor.clone()]})];
        let candidates = mob_geometry::birth_destinations(
            &f.ctx,
            [546, 0],
            &actor,
            &groups,
            &[],
            Some(62201),
            2,
        )
        .await?;
        assert_eq!(candidates, if inside { vec![[-37, 17, 0]] } else { vec![] });
        for destination in candidates {
            let child = native_monster::owned_instance_in(
                &f.ctx,
                2,
                4,
                -1125900015900000,
                546,
                0,
                1,
                i32::try_from(destination[0])?,
                i32::try_from(destination[1])?,
                i16::try_from(destination[2])?,
            )
            .await?;
            assert_eq!(mob_geometry::point(&child)?, [-37, 17, 0]);
            assert!(mob_geometry::home_allowed(&f.ctx, 546, Some(62201), destination, &[0]).await?);
        }
        f.close().await?;
    }
    Ok(())
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn frozen_episode_resumes_chunks_without_replanning_and_completed_runs_stay_done(
) -> Result<()> {
    let f = Fixture::new().await?;
    let map = 999999i32;
    let home = 77i32;
    let mut cells = vec![];
    let mut edges = vec![];
    for x in 0..16 {
        for y in 0..16 {
            let p = [x, y, 0];
            cells.push(p);
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let q = [x + dx, y + dy, 0];
                if (0..16).contains(&q[0]) && (0..16).contains(&q[1]) {
                    edges.push([p, q]);
                }
            }
        }
    }
    f.document(
        "combat-maps/999999.json",
        json!({"map_id":map,"cells":cells,"edges":edges}),
    )
    .await?;
    f.document("territory-map-cells.json",json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":map,"regions":[{"region_id":home,"cells":[[0,0]]}]}]})).await?;
    f.document("ecology-regions.json", json!([])).await?;
    for i in 0..9 {
        f.group(
            map,
            9000 + i,
            json!([member(4, -9000 - i, map as i64, i, 0)]),
            home,
        )
        .await?;
    }
    let snapshot = json!({"world_epoch":"frozen","empty_scopes":[{"map_id":map,"instance_id":0,"empty_generation":1}]});
    let first = mob_idle::prepare(&f.ctx, &snapshot, 16).await?;
    ensure!(!first.is_empty(), "Expected a frozen native placement");
    let db = f.ctx.db.get().await?;
    let frozen: Value = db
        .query_one(
            "SELECT jsonb_agg(to_jsonb(m) ORDER BY ordinal) FROM monster_idle_distribution_moves m",
            &[],
        )
        .await?
        .get(0);
    let run: i64 = db
        .query_one("SELECT id FROM monster_idle_distribution_runs", &[])
        .await?
        .get(0);
    drop(db);
    let rows = frozen
        .as_array()
        .context("Expected frozen distribution rows")?;
    let mut counts = HashMap::<i64, usize>::new();
    for row in rows {
        *counts
            .entry(row["chunk_index"].as_i64().unwrap())
            .or_default() += 1;
        let before = row["expected_members"].as_array().unwrap();
        let after = row["moved_members"].as_array().unwrap();
        for (old, new) in before.iter().zip(after) {
            let mut old = old.as_object().unwrap().clone();
            let mut new = new.as_object().unwrap().clone();
            for key in ["x", "y", "z"] {
                old.remove(key);
                new.remove(key);
            }
            assert_eq!(old, new, "Native idle planning changed owned fields");
        }
    }
    assert!(counts.values().all(|n| *n <= 8));
    // A later roster change cannot cause the already frozen episode to replan.
    f.ctx
        .db
        .get()
        .await?
        .execute(
            "UPDATE combat_groups SET members=jsonb_set(members,'{0,hp}','69') WHERE group_id=9000",
            &[],
        )
        .await?;
    let again = mob_idle::prepare(&f.ctx, &snapshot, 16).await?;
    assert_eq!(first, again);
    let db = f.ctx.db.get().await?;
    let unchanged: Value = db
        .query_one(
            "SELECT jsonb_agg(to_jsonb(m) ORDER BY ordinal) FROM monster_idle_distribution_moves m",
            &[],
        )
        .await?
        .get(0);
    assert_eq!(frozen, unchanged);
    db.execute(
        "UPDATE monster_idle_distribution_moves SET status='applied' WHERE run_id=$1",
        &[&run],
    )
    .await?;
    db.execute(
        "UPDATE monster_idle_distribution_runs SET status='completed' WHERE id=$1",
        &[&run],
    )
    .await?;
    drop(db);
    for _ in 0..3 {
        assert!(mob_idle::prepare(&f.ctx, &snapshot, 16).await?.is_empty());
    }
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one("SELECT count(*) FROM monster_idle_distribution_runs", &[])
            .await?
            .get::<_, i64>(0),
        1
    );
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn reserved_birth_planner_does_not_spend_slots_on_affinity_reconciliation() -> Result<()> {
    let f = Fixture::new().await?;
    f.document("plant-resources.json", json!([])).await?;
    // The schema intentionally has no character/affinity receipts tables.
    // An accidental reconciliation pass for this active owner fails visibly.
    let snapshot = json!({"world_epoch":"reserved","now_ms":100000,"planning_tick":0,
        "reserve_monster_births":true,"skip_interactive":true,
        "players":[{"id":1,"account_id":2,"map_id":546,"instance_id":0,"x":-37,"y":19,"z":0}]});
    assert_eq!(
        plants::prepare(&f.ctx, &snapshot, 4).await?,
        Vec::<Value>::new()
    );
    f.close().await
}

#[path = "idle_planner_contract/home_cases.rs"]
mod home_cases;

#[path = "idle_planner_contract/idle_cases.rs"]
mod idle_cases;
