//! Exercise the same probability/admission stages called by interactive prepare.
use super::*;
use wakemu_ecology::planners::planting_intents;

fn envelope(bonus: i64) -> (Value, Value, Vec<u8>) {
    let body = vec![1u8; 20];
    let intent = json!({"id":"private-intent","intent_version":1,"world_epoch":"private-world","account_id":4,"generation":"lease","character_id":12});
    let snapshot = json!({"planting_equipment":[{"intent_id":"private-intent","intent_version":1,"world_epoch":"private-world","account_id":4,"generation":"lease","character_id":12,"profession_id":72,"body_hex":hex::encode(&body),"plant_probability":bonus}]});
    (intent, snapshot, body)
}

#[tokio::test]
async fn native_bag_probability_precedes_open_policy_and_rejects_monster_seeds() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let (intent, snapshot, body) = envelope(0);
    let actor = json!({"id":12,"account_id":4,"map_id":9,"instance_id":77});
    let request = json!({"x":29,"y":6});
    let seed = json!({"profession_id":72});
    let resource = ctx.catalog.resource_definition(60).await?;
    let mut chances = Vec::new();
    for open in [false, true] {
        chances.push(
            planting_intents::probability_for(
                &ctx, &snapshot, &intent, &body, &actor, &request, &seed, &resource, 4, open,
            )
            .await?,
        );
    }
    assert_eq!(chances[0], chances[1]);
    assert!(chances[0] > 0.0);
    let monster = ctx.catalog.resource_definition(186).await?;
    for open in [false, true] {
        let error = planting_intents::probability_for(
            &ctx, &snapshot, &intent, &body, &actor, &request, &seed, &monster, 4, open,
        )
        .await
        .unwrap_err();
        assert!(error
            .to_string()
            .contains("Monster reproduction is unavailable"));
    }
    // A public open profile cannot invent an equipment result for a bag garden.
    assert!(planting_intents::probability_for(
        &ctx,
        &json!({}),
        &intent,
        &body,
        &actor,
        &request,
        &seed,
        &resource,
        4,
        true
    )
    .await
    .is_err());
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn private_ranch_closed_policy_uses_declared_context_and_open_uses_setting() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let db = fixture.pool.get().await?;
    db.batch_execute("CREATE TABLE settings(name text PRIMARY KEY,value jsonb);CREATE TABLE territory_weather(map_id integer,instance_id bigint,region_id integer,weather text,native_payload bytea);CREATE TABLE territory_weather_forecast_policy(map_id integer,instance_id bigint,region_id integer,policy_version integer)").await?;
    db.execute(
        "INSERT INTO settings VALUES('open_planting_probability','0.01'::jsonb)",
        &[],
    )
    .await?;
    let (intent, snapshot, body) = envelope(2);
    let actor = json!({"id":12,"account_id":4,"map_id":1440,"instance_id":77,"haven_bag":{"owner_id":77},"haven_ranch_session":true});
    let request = json!({"x":29,"y":6});
    let seed = json!({"profession_id":72});
    // The installed Ranch has terrain but no territory grid for this cell.
    // Keep that unsupported closed context explicit; open policy has authority.
    assert!(ctx.catalog.territory_region(1440, 29, 6).await.is_err());
    let native_resource = ctx.catalog.resource_definition(60).await?;
    let error = planting_intents::probability_for(
        &ctx,
        &snapshot,
        &intent,
        &body,
        &actor,
        &request,
        &seed,
        &native_resource,
        4,
        false,
    )
    .await
    .unwrap_err();
    assert!(error.to_string().contains("Unknown native map territory"));
    assert_eq!(
        planting_intents::probability_for(
            &ctx,
            &json!({}),
            &intent,
            &body,
            &actor,
            &request,
            &seed,
            &native_resource,
            4,
            true
        )
        .await?,
        0.01
    );
    // Successful routing uses explicitly declared isolated test authority.
    // Installed Ranch metadata is incomplete in closed mode; the synthetic
    // ground/climate/territory below never enter the production catalog.
    for name in [
        "planting-maps/1440.json",
        "planting-grounds.json",
        "resource-climates.json",
        "plant-resources.json",
    ] {
        fixture
            .document(name, &ctx.catalog.document(name).await?)
            .await?;
    }
    fixture.document("territory-map-cells.json",&json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":1440,"regions":[{"region_id":7,"cells":[[1,0]]}]}]})).await?;
    fixture
        .document(
            "planting-maps/1440.json",
            &json!({"cells":[[29,6,4,0,28,7]]}),
        )
        .await?;
    fixture
        .document(
            "planting-grounds.json",
            &json!([{"ground_id":28,"resources":{"60":70,"186":50},"families":{}}]),
        )
        .await?;
    fixture.document("resource-climates.json", &json!([{"resource_reference":60,"climate":"NONE","allowed_weather":[]},{"resource_reference":186,"climate":"NONE","allowed_weather":[]}])).await?;
    drop(ctx);
    let ctx = fixture.context();
    let region = ctx.catalog.territory_region(1440, 29, 6).await?;
    let mut payload = i64::from(region).to_be_bytes().to_vec();
    payload.push(0);
    payload.extend([0u8; 24]);
    payload.extend(0i32.to_be_bytes()); // ABSENT native weather index.
    db.execute(
        "INSERT INTO territory_weather VALUES(1440,77,$1,'ABSENT',$2)",
        &[&region, &payload],
    )
    .await?;
    let surfaces = ctx.catalog.surfaces_at(1440, 29, 6).await?;
    let grounds = ctx.catalog.document("planting-grounds.json").await?;
    let climates = ctx.catalog.document("resource-climates.json").await?;
    for reference in [60, 186] {
        let resource = ctx.catalog.resource_definition(reference).await?;
        let expected = planting_intents::native_cell_probability(
            &resource, "ABSENT", 2.0, &surfaces, 4, &grounds, &climates,
        )?;
        let closed = planting_intents::probability_for(
            &ctx, &snapshot, &intent, &body, &actor, &request, &seed, &resource, 4, false,
        )
        .await?;
        assert_eq!(closed, expected);
        let open = planting_intents::probability_for(
            &ctx,
            &json!({}),
            &intent,
            &body,
            &actor,
            &request,
            &seed,
            &resource,
            4,
            true,
        )
        .await?;
        assert_eq!(open, 0.01);
    }
    drop(db);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn interactive_prepare_rejects_mineral_and_fishing_seeds_before_occupation() -> Result<()> {
    for (profession, message) in [
        (73, "Mining resources cannot be planted"),
        (75, "Fishing resources cannot be planted"),
    ] {
        let fixture = Fixture::create().await?;
        fixture.document("seed-actions.json", &json!([{"item_reference":9101,"resource_reference":901,"action_id":77,"has_item_criteria":false}])).await?;
        fixture.document("plant-resources.json", &json!([{"resource_reference":901,"family_id":1,"monster_resource":false,"stage_definitions":[{"actions":[{"profession_id":profession}]}]}])).await?;
        let db = fixture.pool.get().await?;
        db.batch_execute("CREATE TABLE characters(id bigint,account_id bigint,map_id integer,instance_id bigint,x integer,y integer,z smallint,deleted_at timestamptz);CREATE TABLE sessions(account_id bigint,generation text,character_id bigint,expires_at timestamptz);CREATE TABLE inventory_items(uid bigint,character_id bigint,reference integer);CREATE TABLE ecology_planting_intents(id text,intent_version bigint,world_epoch text,account_id bigint,generation text,character_id bigint,actor_location jsonb,body bytea,status text,created_at timestamptz);INSERT INTO characters VALUES(12,4,1134,0,0,0,0,NULL);INSERT INTO sessions VALUES(4,'lease',12,CURRENT_TIMESTAMP+INTERVAL '1 day');INSERT INTO inventory_items VALUES(55,12,9101)").await?;
        let mut body = 77i32.to_be_bytes().to_vec();
        body.extend(55i64.to_be_bytes());
        body.extend(1i32.to_be_bytes());
        body.extend(0i32.to_be_bytes());
        let location = json!({"map_id":1134,"instance_id":0,"x":0,"y":0,"z":0});
        db.execute("INSERT INTO ecology_planting_intents VALUES('fixed-seed',1,'world',4,'lease',12,$1,$2,'pending',CURRENT_TIMESTAMP-INTERVAL '1 day')",&[&location,&body]).await?;
        let ctx = fixture.context();
        let snapshot = json!({"world_epoch":"world","started_at_ms":chrono::Utc::now().timestamp_millis(),"open_planting":true,"players":[{"id":12,"account_id":4,"map_id":1134,"instance_id":0,"x":0,"y":0,"z":0}]});
        let plans = planting_intents::prepare(&ctx, &snapshot, 4).await?;
        assert_eq!(plans.len(), 1);
        assert_eq!(plans[0]["kind"], "planting_rejected");
        assert_eq!(plans[0]["error"], message);
        assert_eq!(fixture.count("planted_resources").await?, 0);
        assert_eq!(fixture.count("planting_growth_outbox").await?, 0);
        drop(db);
        drop(ctx);
        fixture.cleanup().await?;
    }
    Ok(())
}
