//! SQL contracts for the sole native regional bonus producer.
#[path = "weather_planner_contract/fixture.rs"]
mod fixture;
use anyhow::{ensure, Result};
use fixture::Fixture;
use serde_json::{json, Value};
use std::collections::BTreeSet;
use wakemu_ecology::planners::bonuses;

async fn setup() -> Result<Fixture> {
    let f = Fixture::create().await?;
    f.sql("CREATE TABLE ecology_dirty_scopes(map_id bigint,instance_id bigint,revision bigint); CREATE TABLE planted_resources(resource_uid bigint,map_id integer,instance_id bigint,x integer,y integer,z smallint,resource_reference integer,stage smallint); CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,status text,members jsonb); CREATE TABLE environmental_owned_groups(map_id integer,world_instance_id bigint,group_id bigint,retired_at_ms bigint); CREATE TABLE objectives_public_hunts(map_id integer,group_id bigint); CREATE TABLE developer_item_test_groups(map_id integer,instance_id bigint,group_id bigint); INSERT INTO settings VALUES('territory_control_health_policy','{\"schema_version\":1,\"states\":{\"1915\":1,\"1916\":2,\"1917\":-1}}');").await?;
    f.document("territory-protector-bonuses.json", &json!({"territories":{"79201":{"map_id":1134,"monster_wishes":[],"plant_wishes":[{"family_id":8,"minimum":0,"maximum":2}]}},"states":{"1915":{"effects":[]},"1916":{"effects":[{"effect_class":166,"variant":0,"criteria":"","parameters":[12]}]},"1917":{"effects":[]}}})).await?;
    f.document("plant-resources.json", &json!([{"resource_reference":60,"family_id":8,"monster_resource":false,"stage_definitions":[]}])).await?;
    Ok(f)
}
fn snapshot(tick: i64, scopes: i64) -> Value {
    let players: Vec<_> = (0..scopes)
        .flat_map(|instance| {
            [
                json!({"map_id":1134,"instance_id":instance}),
                json!({"map_id":1134,"instance_id":instance}),
            ]
        })
        .collect();
    json!({"world_epoch":"bonus-contract","planning_tick":tick*5,"domain_planning_tick":tick,"players":players})
}
#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn duplicate_players_share_one_scope_and_domain_cadence_visits_all_eighty() -> Result<()> {
    let f = setup().await?;
    let result = async {
        let ctx = f.context();
        let plans = bonuses::prepare(&ctx, &snapshot(0, 2), 16).await?;
        ensure!(plans.len() == 2, "Duplicate players inflated scope work");
        ensure!(
            plans[0]["region_states"]["79201"] == 1916
                && plans[0]["regions"]["79201"] == json!({"1":2,"36":12}),
            "Native empty-population wish/effect evaluation differs"
        );
        let mut visited = BTreeSet::new();
        for tick in 0..80 {
            let plans = bonuses::prepare(&ctx, &snapshot(tick, 80), 1).await?;
            ensure!(plans.len() == 1, "Budget changed");
            visited.insert(plans[0]["instance_id"].as_i64().unwrap());
            ensure!(plans[0]["world_epoch"] == "bonus-contract", "Epoch lost");
        }
        ensure!(
            visited.len() == 80,
            "Global five-domain cadence starved scopes"
        );
        let mut visited = BTreeSet::new();
        for tick in 0..80 {
            for plan in bonuses::prepare(&ctx, &snapshot(tick, 80), 16).await? {
                visited.insert(plan["instance_id"].as_i64().unwrap());
            }
        }
        ensure!(visited.len() == 80, "Sixteen-scope budget starved scopes");
        ensure!(
            bonuses::prepare(&ctx, &snapshot(0, 1), 0).await.is_err(),
            "Zero budget accepted"
        );
        Ok(())
    }
    .await;
    f.close().await?;
    result
}
#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn unresolved_population_clears_all_derived_effects_instead_of_granting_partial_bonus(
) -> Result<()> {
    let f = setup().await?;
    let result = async {
        f.sql("INSERT INTO planted_resources VALUES(1,1134,0,9999,9999,0,60,1)")
            .await?;
        let plans = bonuses::prepare(&f.context(), &snapshot(0, 1), 1).await?;
        ensure!(
            plans.len() == 1
                && plans[0]["regions"]["79201"] == json!({})
                && plans[0]["region_states"]["79201"].is_null(),
            "Incomplete regional snapshot granted partial effects"
        );
        Ok(())
    }
    .await;
    f.close().await?;
    result
}
#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn dirty_revision_change_during_native_population_read_discards_entire_proposal() -> Result<()>
{
    let f = setup().await?;
    let result=async {
        // A real SQL view changes its visible revision between the two reads;
        // the planner still performs its actual SQL census and fencing logic.
        f.sql("DROP TABLE ecology_dirty_scopes; CREATE SEQUENCE fixture_revision; CREATE VIEW ecology_dirty_scopes AS SELECT 1134::bigint map_id,0::bigint instance_id,nextval('fixture_revision') revision").await?;
        ensure!(bonuses::prepare(&f.context(),&snapshot(0,1),1).await?.is_empty(),"Torn population snapshot escaped revision fence");
        Ok(())
    }.await;
    f.close().await?;
    result
}
