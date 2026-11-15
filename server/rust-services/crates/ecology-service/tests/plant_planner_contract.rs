//! Native plant planner contracts migrated from the retired Python planner.
//!
//! Mutations are confined to a private schema in an explicitly named test DB.
//! The catalog census reads an explicit native catalog with SQL read-only mode.
use anyhow::{ensure, Context as _, Result};
use deadpool_postgres::Pool;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use tokio_postgres::{Client, Config, NoTls};
use wakemu_ecology::catalog::Catalog;
use wakemu_ecology::planners::plants;
use wakemu_ecology::Context;

struct Fixture {
    admin: Client,
    pool: Pool,
    schema: String,
    revision: String,
    generation: String,
}
impl Fixture {
    async fn create() -> Result<Self> {
        let dsn = std::env::var("WAKFU_POSTGRES_TEST_URL")
            .context("Set WAKFU_POSTGRES_TEST_URL to a dedicated test database")?;
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
        let (admin, connection) = config.connect(NoTls).await?;
        tokio::spawn(async move {
            let _ = connection.await;
        });
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        static NEXT_SCHEMA: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let sequence = NEXT_SCHEMA.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let schema = format!("rust_plant_contract_{}_{stamp}_{sequence}", std::process::id());
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema}"));
        let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(8)
            .build()?;
        let revision = hex::encode(Sha256::digest(schema.as_bytes()));
        let db = pool.get().await?;
        db.batch_execute("CREATE TABLE native_catalog_releases(revision text PRIMARY KEY,complete boolean NOT NULL);CREATE TABLE native_catalog_active(id integer PRIMARY KEY,revision text NOT NULL);CREATE TABLE native_catalog_documents(revision text,path text,raw bytea,sha256 text,source_bytes bigint,PRIMARY KEY(revision,path));CREATE TABLE native_compiled_catalog_releases(generation text PRIMARY KEY,policy text,source_revision text,source_inventory_sha256 text,compiler_contract_sha256 text,config_sha256 text,manifest_raw bytea,manifest jsonb,complete boolean);CREATE TABLE planted_resources(resource_uid bigint PRIMARY KEY,map_id integer,instance_id bigint,x integer,y integer,z smallint,resource_reference integer,stage smallint,creation_time bigint);CREATE TABLE resource_growth_transitions(resource_reference integer,from_stage smallint,to_stage smallint,delay_ms bigint,probability double precision);CREATE TABLE resource_growth_decisions(resource_uid bigint,from_stage smallint);CREATE TABLE environmental_owned_resources(resource_uid bigint PRIMARY KEY,retired_at_ms bigint);CREATE TABLE mining_vein_slots(resource_uid bigint,enabled boolean,active boolean,available_at timestamptz);CREATE TABLE fishing_spot_slots(resource_uid bigint,enabled boolean,active boolean,available_at timestamptz);CREATE TABLE planting_growth_outbox(resource_uid bigint,resource jsonb,published boolean DEFAULT false)").await?;
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
        let mut definitions = Map::new();
        let mut values = Map::new();
        for key in ["1", "2", "3", "4", "9", "32", "35", "92", "97", "100"] {
            definitions.insert(
                key.to_owned(),
                json!({"expandable":true,"hard_minimum":0,"hard_maximum":1000000}),
            );
            values.insert(
                key.to_owned(),
                json!({"minimum":0,"maximum":1000000,"current":0}),
            );
        }
        let mut profiles = Map::new();
        let mut monsters = Vec::new();
        for (reference, level, family, hp) in [
            (1, 1, 9001, 0),
            (2, 10, 9001, 100),
            (3, 20, 9001, 100),
            (4, 1, 9002, 0),
            (5, 10, 9002, 100),
        ] {
            profiles.insert(reference.to_string(),json!({"base_level":level,"at_base_level":values,"curves":{"1":[100,0.0],"2":[6,0.0],"3":[3,0.0],"4":[0,0.0]}}));
            monsters.push(json!({"ref":reference,"min_level":level,"family_id":family,"name":format!("Native fixture {reference}"),"sprite_id":1000+reference,"statistics":{"HP":{"base":hp,"per_level":0.0},"AP":{"base":6,"per_level":0.0},"MP":{"base":3,"per_level":0.0},"WP":{"base":0,"per_level":0.0},"INIT":{"base":5,"per_level":0.0}}}));
        }
        let manifest = json!({"policy":"wakemu.compiled-combat-catalog.v1","source_revision":revision,"source_inventory_sha256":"b".repeat(64),"compiler_contract_sha256":"c".repeat(64),"config_sha256":"d".repeat(64),"collections":{},"raw_documents":{},"documents":{"native-actor-characteristics.json":{"root_kind":"dict","header":{"characteristics":definitions,"npc_profiles":profiles},"collections":{}}}});
        let raw = serde_json::to_vec(&manifest)?;
        let generation = hex::encode(Sha256::digest(&raw));
        db.execute(
            "INSERT INTO native_compiled_catalog_releases VALUES($1,$2,$3,$4,$5,$6,$7,$8,true)",
            &[
                &generation,
                &"wakemu.compiled-combat-catalog.v1",
                &revision,
                &"b".repeat(64),
                &"c".repeat(64),
                &"d".repeat(64),
                &raw,
                &manifest,
            ],
        )
        .await?;
        drop(db);
        let fixture = Self {
            admin,
            pool,
            schema,
            revision,
            generation,
        };
        let candidate = |reference, level| json!({"reference":reference,"min_level":level,"boss_classification":"regular","world_properties":[]});
        let documents = [
            (
                "plant-resources.json",
                json!([
                    {"resource_reference":60,"family_id":1,"monster_resource":false,"stages":[1,2],"stage_definitions":[]},
                    {"resource_reference":901,"family_id":9001,"monster_resource":true,"monster_family_ids":[9001],"stages":[1]},
                    {"resource_reference":902,"family_id":9002,"monster_resource":true,"monster_family_ids":[9002],"stages":[1]},
                    {"resource_reference":903,"family_id":9999,"monster_resource":true,"monster_family_ids":[9999],"stages":[1]},
                    {"resource_reference":904,"family_id":9998,"monster_resource":true,"monster_family_ids":null,"stages":[1]}
                ]),
            ),
            (
                "seed-actions.json",
                json!([{"item_reference":9101,"resource_reference":901}]),
            ),
            ("monsters.json", json!({"monsters":monsters})),
            (
                "monster-encyclopedia.json",
                json!({"monsters":[{"ref":2,"collect_actions":[{"d":1,"csP":9101,"clT":""}]}]}),
            ),
            (
                "monster-growth-catalog.json",
                json!({"families":[{"family_id":9001,"resource_references":[901],"tiers":[{"candidates":[candidate(1,1)]},{"candidates":[candidate(2,10)]},{"candidates":[candidate(3,20)]}]},{"family_id":9002,"resource_references":[902],"tiers":[{"candidates":[candidate(4,1)]},{"candidates":[candidate(5,10)]}]}]}),
            ),
        ];
        for (name, value) in documents {
            fixture.document(name, &value).await?;
        }
        Ok(fixture)
    }
    async fn document(&self, name: &str, value: &Value) -> Result<()> {
        let raw = serde_json::to_vec(value)?;
        let digest = hex::encode(Sha256::digest(&raw));
        self.pool.get().await?.execute("INSERT INTO native_catalog_documents VALUES($1,$2,$3,$4,$5) ON CONFLICT(revision,path) DO UPDATE SET raw=EXCLUDED.raw,sha256=EXCLUDED.sha256,source_bytes=EXCLUDED.source_bytes",&[&self.revision,&name,&raw,&digest,&(raw.len()as i64)]).await?;
        Ok(())
    }
    fn context(&self) -> Context {
        Context {
            db: self.pool.clone(),
            catalog: Catalog::new(
                self.pool.clone(),
                self.revision.clone(),
                Some(self.generation.clone()),
            ),
        }
    }
    fn snapshot(&self) -> Value {
        json!({"world_epoch":self.schema,"now_ms":1000000,"growth_seconds":30,"planning_tick":1,"players":[],"skip_interactive":true})
    }
    async fn resource(&self, uid: i64, reference: i32) -> Result<Value> {
        let resource = json!({"resource_uid":uid,"map_id":1,"instance_id":0,"x":uid,"y":2,"z":0,"resource_reference":reference,"stage":1,"creation_time":0});
        self.pool
            .get()
            .await?
            .execute(
                "INSERT INTO planted_resources VALUES($1,1,0,$2,2,0,$3,1,0)",
                &[&uid, &i32::try_from(uid)?, &reference],
            )
            .await?;
        Ok(resource)
    }
    async fn count(&self, table: &str) -> Result<i64> {
        ensure!(
            matches!(table, "planted_resources" | "planting_growth_outbox"),
            "Invalid fixture table"
        );
        Ok(self
            .pool
            .get()
            .await?
            .query_one(&format!("SELECT count(*)::bigint FROM {table}"), &[])
            .await?
            .get(0))
    }
    async fn cleanup(self) -> Result<()> {
        self.pool.close();
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }
}

#[tokio::test]
async fn flora_prepare_is_read_only_bounded_json_safe_and_keyset_wraps() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    fixture
        .pool
        .get()
        .await?
        .execute(
            "INSERT INTO resource_growth_transitions VALUES(60,1,2,1000,1.0)",
            &[],
        )
        .await?;
    let original = fixture.resource(9041, 60).await?;
    fixture.resource(9042, 60).await?;
    let mut chosen = Vec::new();
    for _ in 0..3 {
        let plans = plants::prepare(&ctx, &fixture.snapshot(), 1).await?;
        ensure!(
            plans.len() == 1,
            "Native planner exceeded bounded flora quota"
        );
        serde_json::to_vec(&plans)?;
        chosen.push(plans[0]["expected"]["resource_uid"].as_i64().unwrap());
    }
    assert_eq!(chosen, vec![9041, 9042, 9041]);
    let row: Value = fixture
        .pool
        .get()
        .await?
        .query_one(
            "SELECT to_jsonb(p) FROM planted_resources p WHERE resource_uid=9041",
            &[],
        )
        .await?
        .get(0);
    assert_eq!(row, original);
    assert_eq!(fixture.count("planted_resources").await?, 2);
    assert_eq!(fixture.count("planting_growth_outbox").await?, 0);
    assert!(plants::prepare(&ctx, &fixture.snapshot(), 0).await.is_err());
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn active_environment_resources_are_excluded_but_retired_rows_can_grow() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    let db = fixture.pool.get().await?;
    db.execute(
        "INSERT INTO resource_growth_transitions VALUES(60,1,2,1000,1.0)",
        &[],
    )
    .await?;
    fixture.resource(9039, 60).await?;
    fixture.resource(9040, 60).await?;
    fixture.resource(9041, 60).await?;
    db.execute(
        "INSERT INTO environmental_owned_resources VALUES(9039,NULL),(9040,1)",
        &[],
    )
    .await?;
    let mut selected = Vec::new();
    for _ in 0..3 {
        let plans = plants::prepare(&ctx, &fixture.snapshot(), 1).await?;
        assert_eq!(plans.len(), 1);
        selected.push(plans[0]["expected"]["resource_uid"].as_i64().unwrap());
    }
    assert_eq!(selected, vec![9040, 9041, 9040]);
    assert_eq!(fixture.count("planted_resources").await?, 3);
    assert_eq!(fixture.count("planting_growth_outbox").await?, 0);
    drop(db);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn publication_keeps_its_quota_with_flora_backlog() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    fixture
        .pool
        .get()
        .await?
        .execute(
            "INSERT INTO resource_growth_transitions VALUES(60,1,2,1000,1.0)",
            &[],
        )
        .await?;
    for uid in 9051..9058 {
        fixture.resource(uid, 60).await?;
    }
    fixture
        .pool
        .get()
        .await?
        .execute(
            "INSERT INTO planting_growth_outbox(resource_uid,resource) VALUES(9051,'{}')",
            &[],
        )
        .await?;
    let plans = plants::prepare(&ctx, &fixture.snapshot(), 4).await?;
    assert!(plans.len() <= 4);
    assert!(plans.iter().any(|row| row["kind"] == "growth_publish"));
    assert!(plans.iter().any(|row| row["kind"] == "resource_growth"));
    assert_eq!(fixture.count("planted_resources").await?, 7);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn blocked_first_sixty_four_do_not_starve_next_seed_or_reroll_after_restart() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    for uid in 1..=65 {
        fixture.resource(uid, 901).await?;
    }
    let players: Vec<_> = (1..=64)
        .map(|uid| json!({"map_id":1,"instance_id":0,"x":uid,"y":2,"z":0}))
        .collect();
    let mut snapshot = fixture.snapshot();
    snapshot["reserve_monster_births"] = json!(true);
    snapshot["players"] = json!(players);
    assert!(plants::prepare(&ctx, &snapshot, 4).await?.is_empty());
    let plans = plants::prepare(&ctx, &snapshot, 4).await?;
    assert_eq!(plans.len(), 1);
    assert_eq!(plans[0]["resources"].as_array().unwrap().len(), 1);
    assert_eq!(plans[0]["resources"][0]["expected"]["resource_uid"], 65);
    let member = plans[0]["resources"][0]["member"].clone();
    drop(ctx);
    let restarted = fixture.context();
    snapshot["world_epoch"] = json!(format!("{}:restarted", fixture.schema));
    assert!(plants::prepare(&restarted, &snapshot, 4).await?.is_empty());
    let repeated = plants::prepare(&restarted, &snapshot, 4).await?;
    assert_eq!(repeated[0]["resources"][0]["member"], member);
    assert_eq!(fixture.count("planted_resources").await?, 65);
    assert_eq!(fixture.count("planting_growth_outbox").await?, 0);
    drop(restarted);
    fixture.cleanup().await
}

#[tokio::test]
async fn initial_pool_handles_invalid_candidates_eligibility_and_fallback() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    assert_eq!(
        plants::initial_candidates(&ctx, 9001, None)
            .await?
            .iter()
            .map(|row| row["reference"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![2]
    );
    assert_eq!(
        plants::initial_candidates(&ctx, 9001, Some(&HashSet::from([3])))
            .await?
            .iter()
            .map(|row| row["reference"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![3]
    );
    assert_eq!(
        plants::initial_candidates(&ctx, 9002, None)
            .await?
            .iter()
            .map(|row| row["reference"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![5]
    );
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn unavailable_family_row_does_not_block_later_valid_birth() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    fixture.resource(101, 903).await?;
    let valid = fixture.resource(102, 901).await?;
    let mut snapshot = fixture.snapshot();
    snapshot["reserve_monster_births"] = json!(true);
    let plans = plants::prepare(&ctx, &snapshot, 4).await?;
    assert_eq!(plans.len(), 1);
    assert_eq!(plans[0]["resources"].as_array().unwrap().len(), 1);
    assert_eq!(plans[0]["resources"][0]["expected"], valid);
    assert_eq!(fixture.count("planted_resources").await?, 2);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn unrelated_malformed_native_state_is_not_downgraded_to_unavailable() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = fixture.context();
    fixture.resource(103, 904).await?;
    let mut snapshot = fixture.snapshot();
    snapshot["reserve_monster_births"] = json!(true);
    let error = plants::prepare(&ctx, &snapshot, 4).await.unwrap_err();
    assert!(error.to_string().contains("monster_family_ids"));
    assert_eq!(fixture.count("planted_resources").await?, 1);
    drop(ctx);
    fixture.cleanup().await
}

/// Native data is read through a separate read-only pool; generated test seeds
/// remain confined to the private schema and never enter the running World.
async fn native_context(fixture: &Fixture) -> Result<Context> {
    let dsn = std::env::var("WAKFU_NATIVE_CATALOG_TEST_URL")
        .context("Set WAKFU_NATIVE_CATALOG_TEST_URL for the native seed census (read-only)")?;
    let mut config: Config = dsn.parse()?;
    if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
        config.password(std::fs::read_to_string(path)?.trim());
    }
    config.options("-c default_transaction_read_only=on");
    let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
        .max_size(8)
        .build()?;
    let db = pool.get().await?;
    ensure!(
        db.query_one("SHOW default_transaction_read_only", &[])
            .await?
            .get::<_, String>(0)
            == "on",
        "Native census requires read-only SQL"
    );
    drop(db);
    let revision =
        std::env::var("WAKFU_CATALOG_REVISION").context("Native catalog revision required")?;
    let generation = std::env::var("WAKFU_COMPILED_CATALOG_GENERATION")
        .context("Compiled generation required")?;
    let catalog = Catalog::new(pool, revision, Some(generation));
    catalog.verify().await?;
    Ok(Context {
        db: fixture.pool.clone(),
        catalog,
    })
}

#[tokio::test]
async fn native_family_113_has_qualified_initial_candidates() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let family = plants::initial_candidates(&ctx, 113, None).await?;
    let references: HashSet<_> = family
        .iter()
        .map(|row| row["reference"].as_i64().unwrap())
        .collect();
    assert_eq!(references, HashSet::from([135, 95, 1275, 4544]));
    assert!(family
        .iter()
        .all(|row| (38..=40).contains(&row["min_level"].as_i64().unwrap())));
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn every_native_seed_has_qualified_initial_candidates() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let definitions = ctx.catalog.document("plant-resources.json").await?;
    let by_ref: HashMap<_, _> = definitions
        .as_array()
        .context("Native resource catalog must be an array")?
        .iter()
        .map(|row| (row["resource_reference"].as_i64().unwrap(), row.clone()))
        .collect();
    let tutorial = by_ref
        .get(&186)
        .context("Native tutorial seed resource186 absent")?;
    assert_eq!(tutorial["monster_resource"], true);
    assert!(tutorial["monster_family_ids"]
        .as_array()
        .unwrap()
        .contains(&json!(113)));
    let growth = plants::normalize_growth_catalog(
        ctx.catalog.document("monster-growth-catalog.json").await?,
    )?;
    let growth_families: HashMap<_, _> = growth["families"]
        .as_array()
        .context("Native growth families required")?
        .iter()
        .map(|row| (row["family_id"].as_i64().unwrap(), row))
        .collect();
    let seeds = ctx.catalog.document("seed-actions.json").await?;
    let native_monsters = ctx.catalog.document("monsters.json").await?;
    let native_families: HashSet<_> = native_monsters["monsters"]
        .as_array()
        .context("Native monster catalog required")?
        .iter()
        .filter_map(|row| row["family_id"].as_i64())
        .collect();
    let mut expected = HashMap::new();
    let mut uid = 1;
    for seed in seeds
        .as_array()
        .context("Native seed actions must be an array")?
    {
        let reference = seed["resource_reference"]
            .as_i64()
            .context("Seed resource reference required")?;
        let definition = by_ref
            .get(&reference)
            .context("Native seed resource definition missing")?;
        if definition["monster_resource"] != true {
            continue;
        }
        fixture.resource(uid, i32::try_from(reference)?).await?;
        expected.insert(uid, reference);
        uid += 1;
    }
    assert!(!expected.is_empty(), "Native monster seed catalog is empty");
    // Resource186 is explicitly qualified even if a future seed-item inventory
    // does not enumerate its tutorial action among ordinary account seeds.
    fixture.resource(uid, 186).await?;
    expected.insert(uid, 186);

    let mut snapshot = fixture.snapshot();
    snapshot["reserve_monster_births"] = json!(true);
    snapshot["world_epoch"] = json!(format!("{}:native-census", fixture.schema));
    let mut produced = HashSet::new();
    for _ in 0..(expected.len().div_ceil(64) + 1) {
        for batch in plants::prepare(&ctx, &snapshot, 4).await? {
            for row in batch["resources"]
                .as_array()
                .context("Native birth batch required")?
            {
                let uid = row["expected"]["resource_uid"].as_i64().unwrap();
                let reference = row["member"]["ref"].as_i64().unwrap();
                let monster = ctx.catalog.monster_definition(reference).await?;
                assert!(by_ref[&expected[&uid]]["monster_family_ids"]
                    .as_array()
                    .unwrap()
                    .contains(&monster["family_id"]));
                assert!(reference > 0);
                produced.insert(uid);
            }
        }
    }
    let mut unavailable = HashSet::new();
    for (uid, reference) in &expected {
        if produced.contains(uid) {
            continue;
        }
        for family in by_ref[reference]["monster_family_ids"].as_array().unwrap() {
            let family = family.as_i64().unwrap();
            assert!(
                !native_families.contains(&family),
                "Native family {family} has native templates but no seed can produce one"
            );
            assert!(
                growth_families
                    .get(&family)
                    .map_or(true, |row| row["missing_catalog"] == true
                        || row["tiers"].as_array().is_some_and(Vec::is_empty)),
                "Family {family} is unavailable without a missing catalog"
            );
            unavailable.insert(family);
        }
    }
    assert_eq!(unavailable, HashSet::from([469, 470]));
    assert_eq!(
        fixture.count("planted_resources").await?,
        expected.len() as i64
    );
    assert_eq!(fixture.count("planting_growth_outbox").await?, 0);
    drop(ctx);
    fixture.cleanup().await
}

#[path = "plant_planner_contract/balance_cases.rs"]
mod balance_cases;

#[path = "plant_planner_contract/private_probability_cases.rs"]
mod private_probability_cases;

#[path = "plant_planner_contract/probability_context_cases.rs"]
mod probability_context_cases;
