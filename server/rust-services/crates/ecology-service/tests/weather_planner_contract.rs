//! Actual native weather planner SQL regression contracts.
mod weather_planner_contract {
    pub mod fixture;
}
use anyhow::{ensure, Result};
use weather_planner_contract::fixture::Fixture;
#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn simulation_is_durable_forecast_consistent_and_coalesces_missed_days() -> Result<()> {
    let f = Fixture::create().await?;
    let result = async {
        f.local().await?;
        let plans = f.prepare().await?;
        ensure!(
            plans.iter().any(|p| p["operation"] == "forecast_publish"),
            "Missing forecast publication"
        );
        let first = f.state().await?;
        ensure!(
            first["day"] == 10 && first["version"] == 1,
            "Wrong initial cursor"
        );
        ensure!(
            f.number("SELECT count(*) FROM territory_weather_forecast_days")
                .await?
                == 5,
            "Forecast horizon differs"
        );
        let forecast: String = f
            .pool
            .get()
            .await?
            .query_one(
                "SELECT weather FROM territory_weather_forecast_days WHERE day_offset=1",
                &[],
            )
            .await?
            .get(0);
        f.prepare().await?; // A fresh Context/Catalog models process reconnection.
        ensure!(f.state().await? == first, "Reconnect rerolled the same day");
        f.sql("UPDATE fixture_clock SET now='2026-01-12 01:00:00+00'")
            .await?;
        f.prepare().await?;
        ensure!(
            f.state().await?["weather"] == forecast,
            "Forecast did not become actual weather"
        );
        f.sql("UPDATE fixture_clock SET now='2026-03-02 01:00:00+00'")
            .await?;
        f.prepare().await?;
        let last = f.state().await?;
        ensure!(
            last["day"] == 60 && last["version"] == 3,
            "Missed days were replayed instead of coalesced"
        );
        ensure!(
            last["payload"]
                .as_str()
                .unwrap()
                .starts_with("00000000075bcd15"),
            "Native identity changed"
        );
        Ok(())
    }
    .await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn forecast_failure_rolls_back_weather_cursor_and_outboxes() -> Result<()> {
    let f = Fixture::create().await?;
    let result=async {
        f.local().await?;
        let before=f.state().await?;
        f.sql("ALTER TABLE territory_weather_forecast_days ADD CONSTRAINT fixture_reject_forecast CHECK(day_offset<1)").await?;
        ensure!(f.prepare().await.is_err(),"Injected forecast failure was ignored");
        ensure!(f.state().await?==before,"Partial weather/cursor transaction escaped");
        for table in ["territory_weather_outbox","territory_weather_forecast_outbox","territory_weather_simulation","territory_weather_forecast_policy"] {
            ensure!(f.number(&format!("SELECT count(*) FROM {table}")).await?==0,"Partial rows in {table}");
        }
        Ok(())
    }.await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn concurrent_first_update_generates_one_cursor_and_forecast_version() -> Result<()> {
    let f = Fixture::create().await?;
    let result = async {
        f.local().await?;
        let (a, b) = tokio::join!(f.prepare(), f.prepare());
        a?;
        b?;
        ensure!(
            f.state().await?["version"] == 1,
            "Concurrent planners generated duplicate versions"
        );
        ensure!(
            f.number("SELECT count(*) FROM territory_weather_simulation")
                .await?
                == 1,
            "Duplicate cursor"
        );
        ensure!(
            f.number("SELECT count(*) FROM territory_weather_forecast_outbox")
                .await?
                == 1,
            "Duplicate forecast outbox"
        );
        Ok(())
    }
    .await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn preserved_state_operator_override_and_forecast_remain_authoritative() -> Result<()> {
    let f = Fixture::create().await?;
    let result=async {
        f.local().await?;
        f.sql("UPDATE territory_weather_local_policy SET source='PRESERVED_STATE'").await?;
        let before=f.state().await?; f.prepare().await?;
        ensure!(f.state().await?==before,"Native snapshot overwritten");
        f.sql("UPDATE territory_weather_local_policy SET source='LOCAL_POLICY'; INSERT INTO territory_weather_simulation(map_id,instance_id,region_id,simulated_day,configuration_hash,forecast_version,explicit_override) VALUES(1134,17,79201,10,'operator',1,true)").await?;
        let before=f.state().await?; f.prepare().await?;
        ensure!(f.state().await?==before,"Explicit operator override overwritten");
        f.sql("DELETE FROM territory_weather_simulation; INSERT INTO territory_weather_forecast_policy VALUES(1134,17,79201,99,'LOCAL_POLICY',clock_timestamp())").await?;
        let before=f.state().await?; f.prepare().await?;
        ensure!(f.state().await?==before,"Independent operator forecast overwritten");
        Ok(())
    }.await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn disabling_clears_forecast_once_and_reenabling_resumes() -> Result<()> {
    let f = Fixture::create().await?;
    let result=async {
        f.local().await?; f.prepare().await?;
        let weather=f.state().await?;
        f.sql("UPDATE settings SET value=jsonb_set(value,'{enabled}','false') WHERE name='weather_simulation'").await?;
        f.prepare().await?;
        let disabled=f.state().await?;
        ensure!(disabled["version"]==2 && disabled["payload"]==weather["payload"],"Disable mutated actual weather");
        ensure!(f.number("SELECT count(*) FROM territory_weather_forecast_days").await?==0,"Disabled forecast remained");
        f.prepare().await?; ensure!(f.state().await?==disabled,"Disabled cursor rerolled");
        f.sql("UPDATE settings SET value=jsonb_set(value,'{enabled}','true') WHERE name='weather_simulation'").await?;
        f.prepare().await?;
        ensure!(f.state().await?["version"]==3,"Reenable did not advance version");
        ensure!(f.number("SELECT count(*) FROM territory_weather_forecast_days").await?==5,"Forecast did not resume");
        Ok(())
    }.await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn scheduled_updates_are_instance_scoped_coalesced_and_enum_only() -> Result<()> {
    let f = Fixture::create().await?;
    let result=async {
        f.instance(17).await?; f.instance(18).await?;
        f.sql("DELETE FROM settings WHERE name='weather_simulation'; INSERT INTO territory_weather_transitions(map_id,instance_id,region_id,transition_at,target_weather) VALUES(1134,17,79201,'2026-01-09','HEAVY'),(1134,17,79201,'2026-01-10','STORM'),(1134,18,79201,'2026-01-10','LIGHT')").await?;
        let original=f.state().await?;
        let plans=f.prepare().await?;
        let updated=f.state().await?;
        ensure!(updated["revision"]==2 && updated["weather"]=="STORM","Latest due transition not coalesced");
        ensure!(updated["payload"].as_str().unwrap()[..66]==original["payload"].as_str().unwrap()[..66],"Scheduled transition altered native climate fields");
        ensure!(plans.len()==1 && plans[0]["event"]["instance_id"]==17 && plans[0]["world_epoch"]=="weather-contract","Wrong publication scope");
        ensure!(f.number("SELECT revision FROM territory_weather WHERE instance_id=18").await?==1,"No-op changed second instance");
        ensure!(f.number("SELECT count(*) FROM territory_weather_transitions").await?==0,"Consumed transitions remained");
        f.prepare().await?;
        ensure!(f.number("SELECT count(*) FROM territory_weather_outbox").await?==1,"No-op/retry duplicated outbox");
        Ok(())
    }.await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn locked_latest_due_transition_never_falls_back_to_older_due_row() -> Result<()> {
    let f = Fixture::create().await?;
    let result=async {
        f.instance(17).await?;
        f.sql("DELETE FROM settings WHERE name='weather_simulation'; INSERT INTO territory_weather_transitions(map_id,instance_id,region_id,transition_at,target_weather) VALUES(1134,17,79201,'2026-01-09','HEAVY'),(1134,17,79201,'2026-01-10','STORM')").await?;
        let mut lock=f.pool.get().await?;
        let tx=lock.transaction().await?;
        tx.query_one("SELECT target_weather FROM territory_weather_transitions ORDER BY transition_at DESC LIMIT 1 FOR UPDATE",&[]).await?;
        let plans=tokio::time::timeout(std::time::Duration::from_secs(5),f.prepare()).await??;
        ensure!(plans.is_empty() && f.state().await?["revision"]==1,"Locked latest row caused older transition application");
        ensure!(f.number("SELECT count(*) FROM territory_weather_transitions").await?==2,"Locked queue changed");
        tx.rollback().await?;
        f.prepare().await?;
        ensure!(f.state().await?["weather"]=="STORM","Unlocked latest transition failed");
        Ok(())
    }.await;
    f.close().await?;
    result
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn bounded_batches_refresh_configuration_without_cross_instance_starvation() -> Result<()> {
    let f = Fixture::create().await?;
    let result = async {
        f.local().await?;
        f.instance(18).await?;
        let ctx=f.context();
        let snapshot=serde_json::json!({"world_epoch":"weather-contract"});
        for _ in 0..2 {
            let plans=wakemu_ecology::planners::weather::prepare(&ctx,&snapshot,1).await?;
            ensure!(plans.len()<=1,"Planner exceeded publication limit");
        }
        ensure!(f.number("SELECT count(*) FROM territory_weather_simulation WHERE simulated_day=10 AND forecast_version=1").await?==2,"Bounded batches starved an instance");
        ensure!(f.number("SELECT count(DISTINCT native_payload) FROM territory_weather").await?==1,"Instance identity changed regional climate");
        let before=f.state().await?;
        f.sql("UPDATE settings SET value=jsonb_set(value,'{seed}','20') WHERE name='weather_simulation'").await?;
        for _ in 0..2 { wakemu_ecology::planners::weather::prepare(&ctx,&snapshot,1).await?; }
        let after=f.state().await?;
        ensure!(after["version"]==2 && after["hash"]!=before["hash"],"Changed policy did not refresh same-day model");
        ensure!(f.number("SELECT count(*) FROM territory_weather_simulation WHERE forecast_version=2").await?==2,"Changed policy missed an instance");
        ensure!(f.number("SELECT count(*) FROM territory_weather_outbox o JOIN territory_weather w USING(map_id,instance_id,region_id) WHERE o.revision<>w.revision AND o.superseded_at IS NULL AND o.published_at IS NULL").await?==0,"Stale weather publication remains eligible");
        Ok(())
    }.await;
    f.close().await?;
    result
}
