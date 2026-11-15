//! Deterministic regional weather, atomic forecast policy and publication plans.
//!
//! Simulation/transition commits are worker-owned; socket publication and its
//! final revalidation remain with World. No native values are inferred.
use std::collections::{BTreeMap, BTreeSet};

use anyhow::{ensure, Context as _, Result};
use chrono::{DateTime, Datelike, Duration, NaiveDate, TimeZone, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio_postgres::{types::ToSql, Transaction};

use crate::Context;

const WEATHER: [&str; 4] = ["ABSENT", "LIGHT", "HEAVY", "STORM"];

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct SimulationPolicy {
    enabled: bool,
    seed: i64,
    day_seconds: i64,
    forecast_days: usize,
    weather_weights: [i64; 4],
    season_temperature_samples: [i64; 4],
    temperature_variation: i64,
    wind_samples: [i64; 4],
}

impl SimulationPolicy {
    fn parse(value: &Value) -> Result<Self> {
        let policy: Self = serde_json::from_value(value.clone())
            .context("Invalid regional weather simulation policy")?;
        ensure!(
            (0..=i32::MAX as i64).contains(&policy.seed),
            "Invalid regional weather simulation seed"
        );
        ensure!(
            (10..=604800).contains(&policy.day_seconds),
            "Invalid regional weather simulation day_seconds"
        );
        ensure!(
            (1..=30).contains(&policy.forecast_days),
            "Invalid regional weather simulation forecast_days"
        );
        ensure!(
            (0..=30).contains(&policy.temperature_variation),
            "Invalid regional weather simulation temperature_variation"
        );
        ensure!(
            policy
                .weather_weights
                .iter()
                .all(|value| (0..=10000).contains(value))
                && policy.weather_weights.iter().sum::<i64>() > 0,
            "Invalid regional weather simulation weather weights"
        );
        ensure!(
            policy
                .season_temperature_samples
                .iter()
                .all(|value| (-90..=90).contains(value)),
            "Invalid regional weather simulation temperature samples"
        );
        ensure!(
            policy
                .wind_samples
                .iter()
                .all(|value| (0..=65535).contains(value)),
            "Invalid regional weather simulation wind samples"
        );
        Ok(policy)
    }

    fn fingerprint(&self) -> Result<String> {
        // Python simulation uses json.dumps(sort_keys=True), with spaces. Its
        // policy consists only of ASCII keys, booleans and integer arrays.
        fn spaced(value: &Value) -> Result<String> {
            Ok(match value {
                Value::Object(rows) => {
                    let ordered: BTreeMap<_, _> = rows.iter().collect();
                    format!(
                        "{{{}}}",
                        ordered
                            .into_iter()
                            .map(|(key, value)| Ok(format!(
                                "{}: {}",
                                serde_json::to_string(key)?,
                                spaced(value)?
                            )))
                            .collect::<Result<Vec<_>>>()?
                            .join(", ")
                    )
                }
                Value::Array(rows) => format!(
                    "[{}]",
                    rows.iter()
                        .map(spaced)
                        .collect::<Result<Vec<_>>>()?
                        .join(", ")
                ),
                _ => serde_json::to_string(value)?,
            })
        }
        Ok(hex::encode(Sha256::digest(
            spaced(&serde_json::to_value(self)?)?.as_bytes(),
        )))
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Day {
    season: i16,
    a: i16,
    b: i16,
    wind: i32,
    weather: usize,
    adjustment: i16,
    modifier: i16,
}

#[derive(Clone, Debug)]
struct Season {
    season: i16,
    minimum: i16,
    maximum: i16,
}

fn sample(policy: &SimulationPolicy, map_id: i32, region_id: i32, day: i64, purpose: &str) -> u64 {
    let input = format!("{}:{map_id}:{region_id}:{day}:{purpose}", policy.seed);
    let bytes = Sha256::digest(input.as_bytes());
    u64::from_be_bytes(bytes[..8].try_into().unwrap())
}

fn day_state(policy: &SimulationPolicy, map_id: i32, region_id: i32, day: i64) -> Result<Day> {
    let calendar = NaiveDate::from_ymd_opt(2026, 1, 1)
        .unwrap()
        .checked_add_signed(Duration::days(day.rem_euclid(146097)))
        .context("Regional weather calendar overflow")?;
    let season = (calendar.month() % 12 / 3) as usize;
    let factors = [
        [75, 110, 125, 110],
        [100, 115, 100, 100],
        [135, 85, 70, 80],
        [90, 110, 120, 110],
    ][season];
    let effective: Vec<u64> = policy
        .weather_weights
        .iter()
        .zip(factors)
        .map(|(weight, factor)| (weight * factor) as u64)
        .collect();
    let mut roll =
        sample(policy, map_id, region_id, day, "weather") % effective.iter().sum::<u64>();
    let mut weather = 0;
    for (index, weight) in effective.into_iter().enumerate() {
        weather = index;
        if roll < weight {
            break;
        }
        roll -= weight;
    }
    let delta = (sample(policy, map_id, region_id, day, "temperature")
        % (2 * policy.temperature_variation + 1) as u64) as i64
        - policy.temperature_variation;
    let temperature = policy.season_temperature_samples[season] + delta;
    Ok(Day {
        season: season as i16,
        a: (temperature - 3) as i16,
        b: (temperature + 3) as i16,
        wind: policy.wind_samples[weather] as i32,
        weather,
        adjustment: 0,
        modifier: 0,
    })
}

fn forecast_policy(
    policy: &SimulationPolicy,
    map_id: i32,
    region_id: i32,
    day: i64,
) -> Result<(Vec<Day>, Vec<Season>)> {
    if !policy.enabled {
        return Ok((vec![], vec![]));
    }
    let days = (1..=policy.forecast_days)
        .map(|offset| {
            day_state(
                policy,
                map_id,
                region_id,
                day.checked_add(offset as i64)
                    .context("Regional weather day overflow")?,
            )
        })
        .collect::<Result<Vec<_>>>()?;
    let used: BTreeSet<_> = days.iter().map(|day| day.season).collect();
    let seasons = used
        .into_iter()
        .map(|season| Season {
            season,
            minimum: (policy.season_temperature_samples[season as usize]
                - policy.temperature_variation
                - 3) as i16,
            maximum: (policy.season_temperature_samples[season as usize]
                + policy.temperature_variation
                + 3) as i16,
        })
        .collect();
    Ok((days, seasons))
}

fn weather_id(weather: &str) -> Result<usize> {
    WEATHER
        .iter()
        .position(|known| *known == weather)
        .context("Invalid native weather enum")
}

fn decode_weather(payload: &[u8]) -> Result<(i64, usize)> {
    ensure!(
        payload.len() == 37,
        "Invalid native territory weather payload"
    );
    for field in payload[9..33].chunks_exact(4) {
        ensure!(
            f32::from_be_bytes(field.try_into().unwrap()).is_finite(),
            "Invalid native territory weather state"
        );
    }
    let weather = i32::from_be_bytes(payload[33..37].try_into().unwrap());
    ensure!(
        (0..4).contains(&weather),
        "Invalid native territory weather state"
    );
    Ok((
        i64::from_be_bytes(payload[..8].try_into().unwrap()),
        weather as usize,
    ))
}

fn modeled_payload(identity: i64, state: &Day) -> Result<Vec<u8>> {
    ensure!(
        (-128..=127).contains(&state.a) && (-128..=127).contains(&state.b),
        "Invalid modeled weather temperature"
    );
    let base = (i32::from(state.a) + i32::from(state.b)).div_euclid(2);
    let wind = state.wind as f64 / 65535.0;
    let mut payload = identity.to_be_bytes().to_vec();
    payload.push(i8::try_from(base).context("Invalid modeled base temperature")? as u8);
    for value in [
        wind,
        state.a as f64,
        state.b as f64,
        state.adjustment as f64,
        wind,
        state.modifier as f64 / 32767.0,
    ] {
        payload.extend_from_slice(&(value as f32).to_be_bytes());
    }
    payload.extend_from_slice(&(state.weather as i32).to_be_bytes());
    Ok(payload)
}

fn encode_forecast(days: &[Day], seasons: &[Season]) -> Result<Vec<u8>> {
    ensure!(
        days.len() <= 255 && seasons.len() <= 4,
        "Invalid local weather forecast length"
    );
    let mut body = vec![days.len() as u8];
    let mut used = BTreeSet::new();
    for day in days {
        ensure!(
            (0..4).contains(&day.season) && day.weather < 4 && (0..=65535).contains(&day.wind),
            "Invalid weather forecast wire field"
        );
        used.insert(day.season);
        body.push(day.season as u8);
        body.push(i8::try_from(day.a).context("Invalid weather forecast sample")? as u8);
        body.push(i8::try_from(day.b).context("Invalid weather forecast sample")? as u8);
        body.extend_from_slice(&(day.wind as u16).to_be_bytes());
        body.extend_from_slice(&(day.weather as i32).to_be_bytes());
        body.push(i8::try_from(day.adjustment).context("Invalid weather forecast sample")? as u8);
        body.extend_from_slice(&day.modifier.to_be_bytes());
    }
    body.push(seasons.len() as u8);
    let mut seen = BTreeSet::new();
    for season in seasons {
        ensure!(
            (0..4).contains(&season.season) && seen.insert(season.season),
            "Invalid duplicate weather forecast season"
        );
        body.push(season.season as u8);
        body.push(
            i8::try_from(season.minimum).context("Invalid weather forecast seasonal sample")? as u8,
        );
        body.push(
            i8::try_from(season.maximum).context("Invalid weather forecast seasonal sample")? as u8,
        );
    }
    ensure!(
        used.is_subset(&seen),
        "Forecast day is missing seasonal adjustment values"
    );
    for _ in 0..2usize.saturating_sub(seasons.len()) {
        body.extend_from_slice(&[0, 0, 0]);
    }
    let length =
        u16::try_from(body.len()).context("Weather forecast exceeds native envelope capacity")?;
    let mut packet = length.to_be_bytes().to_vec();
    packet.extend_from_slice(&body);
    Ok(packet)
}

async fn known_territories(ctx: &Context) -> Result<BTreeSet<(i32, i32)>> {
    ctx.catalog.known_territories().await
}

async fn save_forecast(
    transaction: &Transaction<'_>,
    key: (i32, i64, i32),
    version: i32,
    days: &[Day],
    seasons: &[Season],
) -> Result<()> {
    ensure!(version > 0, "Invalid local forecast policy version");
    encode_forecast(days, seasons)?;
    let accepted = transaction.query_opt("INSERT INTO territory_weather_forecast_policy (map_id,instance_id,region_id,policy_version,source) VALUES($1,$2,$3,$4,'LOCAL_POLICY') ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET policy_version=EXCLUDED.policy_version,source='LOCAL_POLICY',updated_at=clock_timestamp() WHERE territory_weather_forecast_policy.policy_version<EXCLUDED.policy_version RETURNING policy_version", &[&key.0, &key.1, &key.2, &version]).await?;
    ensure!(accepted.is_some(), "Forecast policy version must increase");
    transaction.execute("DELETE FROM territory_weather_forecast_days WHERE map_id=$1 AND instance_id=$2 AND region_id=$3", &[&key.0,&key.1,&key.2]).await?;
    transaction.execute("DELETE FROM territory_weather_forecast_season_adjustments WHERE map_id=$1 AND instance_id=$2 AND region_id=$3", &[&key.0,&key.1,&key.2]).await?;
    for (index, day) in days.iter().enumerate() {
        let offset = i16::try_from(index + 1)?;
        let modifier = i32::from(day.modifier);
        transaction.execute("INSERT INTO territory_weather_forecast_days (map_id,instance_id,region_id,day_offset,season,temperature_sample_a,temperature_sample_b,wind_strength_u16,weather,temperature_adjustment_sample,signed_weather_modifier_i16) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)", &[&key.0,&key.1,&key.2,&offset,&day.season,&day.a,&day.b,&day.wind,&WEATHER[day.weather],&day.adjustment,&modifier]).await?;
    }
    for season in seasons {
        transaction.execute("INSERT INTO territory_weather_forecast_season_adjustments (map_id,instance_id,region_id,season,actual_minimum_adjustment,actual_maximum_adjustment) VALUES($1,$2,$3,$4,$5,$6)", &[&key.0,&key.1,&key.2,&season.season,&season.minimum,&season.maximum]).await?;
    }
    transaction.execute("INSERT INTO territory_weather_forecast_outbox (map_id,instance_id,region_id,policy_version) VALUES($1,$2,$3,$4)", &[&key.0,&key.1,&key.2,&version]).await?;
    Ok(())
}

async fn advance_simulation(
    ctx: &Context,
    limit: usize,
    scope: Option<(i32, i64, i32)>,
) -> Result<()> {
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    let Some(row) = transaction
        .query_opt(
            "SELECT value FROM settings WHERE name='weather_simulation'",
            &[],
        )
        .await?
    else {
        transaction.commit().await?;
        return Ok(());
    };
    let policy = SimulationPolicy::parse(&row.get::<_, Value>(0))?;
    let now: DateTime<Utc> = transaction
        .query_one("SELECT clock_timestamp()", &[])
        .await?
        .get(0);
    let epoch = Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).single().unwrap();
    let day = now
        .signed_duration_since(epoch)
        .num_microseconds()
        .context("Weather simulation clock overflow")?
        .div_euclid(policy.day_seconds * 1_000_000);
    let fingerprint = policy.fingerprint()?;
    let territories = known_territories(ctx).await?;
    let mut parameters: Vec<&(dyn ToSql + Sync)> = Vec::new();
    let due = if policy.enabled {
        parameters.extend([&day as &(dyn ToSql + Sync), &fingerprint]);
        "AND (s.simulated_day IS NULL OR s.simulated_day<>$1 OR s.configuration_hash<>$2) "
            .to_owned()
    } else {
        parameters.push(&fingerprint);
        "AND s.simulated_day IS NOT NULL AND s.configuration_hash<>$1 ".to_owned()
    };
    let scope_parameters: [i64; 3] = scope
        .map(|scope| [scope.0 as i64, scope.1, scope.2 as i64])
        .unwrap_or_default();
    let scope_filter = if scope.is_some() {
        let start = parameters.len() + 1;
        // Explicit bigint casts accept one compact parameter type for the scope.
        parameters.extend(scope_parameters.iter().map(|v| v as &(dyn ToSql + Sync)));
        format!("AND w.map_id=${start}::bigint AND w.instance_id=${}::bigint AND w.region_id=${}::bigint ",start+1,start+2)
    } else {
        String::new()
    };
    let limit = i64::try_from(limit)?;
    parameters.push(&limit);
    let row_lock = if scope.is_some() {
        "FOR UPDATE OF w"
    } else {
        "FOR UPDATE OF w SKIP LOCKED"
    };
    let sql = format!("SELECT w.* FROM territory_weather w JOIN territory_weather_local_policy p USING(map_id,region_id) LEFT JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) LEFT JOIN territory_weather_forecast_policy f USING(map_id,instance_id,region_id) WHERE p.source='LOCAL_POLICY' AND (s.explicit_override IS NULL OR NOT s.explicit_override) {due} AND (f.policy_version IS NULL OR f.policy_version=s.forecast_version) AND NOT EXISTS(SELECT 1 FROM territory_weather_transitions t WHERE t.map_id=w.map_id AND t.instance_id=w.instance_id AND t.region_id=w.region_id) {scope_filter} ORDER BY s.updated_at NULLS FIRST,w.map_id,w.instance_id,w.region_id LIMIT ${} {row_lock}",parameters.len());
    let rows = transaction.query(&sql, &parameters).await?;
    for current in rows {
        let key: (i32, i64, i32) = (
            current.get("map_id"),
            current.get("instance_id"),
            current.get("region_id"),
        );
        let authority = transaction.query_one("SELECT s.simulated_day,s.configuration_hash,s.explicit_override,s.forecast_version,f.policy_version FROM territory_weather w LEFT JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) LEFT JOIN territory_weather_forecast_policy f USING(map_id,instance_id,region_id) WHERE w.map_id=$1 AND w.instance_id=$2 AND w.region_id=$3", &[&key.0,&key.1,&key.2]).await?;
        let current_version: Option<i32> = authority.get("policy_version");
        let generated_version: Option<i32> = authority.get("forecast_version");
        if authority
            .get::<_, Option<bool>>("explicit_override")
            .unwrap_or(false)
            || (current_version.is_some() && current_version != generated_version)
        {
            continue;
        }
        if authority
            .get::<_, Option<String>>("configuration_hash")
            .as_deref()
            == Some(&fingerprint)
            && (!policy.enabled || authority.get::<_, Option<i64>>("simulated_day") == Some(day))
        {
            continue;
        }
        let original: Vec<u8> = current.get("native_payload");
        let (identity, previous_weather) = decode_weather(&original)?;
        ensure!(
            WEATHER[previous_weather] == current.get::<_, String>("weather"),
            "Inconsistent authoritative territory weather"
        );
        let state = day_state(&policy, key.0, key.2, day)?;
        let payload = modeled_payload(identity, &state)?;
        if policy.enabled && payload != original {
            let revision: i64 = transaction.query_one("UPDATE territory_weather SET weather=$1,native_payload=$2,revision=revision+1,updated_at=clock_timestamp() WHERE map_id=$3 AND instance_id=$4 AND region_id=$5 RETURNING revision", &[&WEATHER[state.weather],&payload,&key.0,&key.1,&key.2]).await?.get(0);
            transaction.execute("INSERT INTO territory_weather_outbox (map_id,instance_id,region_id,revision,weather,native_payload) VALUES($1,$2,$3,$4,$5,$6)", &[&key.0,&key.1,&key.2,&revision,&WEATHER[state.weather],&payload]).await?;
        }
        ensure!(
            territories.contains(&(key.0, key.2)),
            "Unknown local forecast territory"
        );
        let version = current_version
            .unwrap_or(0)
            .checked_add(1)
            .context("Weather forecast policy version overflow")?;
        let (days, seasons) = forecast_policy(&policy, key.0, key.2, day)?;
        save_forecast(&transaction, key, version, &days, &seasons).await?;
        transaction.execute("INSERT INTO territory_weather_simulation (map_id,instance_id,region_id,simulated_day,configuration_hash,forecast_version) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET simulated_day=EXCLUDED.simulated_day,configuration_hash=EXCLUDED.configuration_hash,forecast_version=EXCLUDED.forecast_version,updated_at=clock_timestamp()", &[&key.0,&key.1,&key.2,&day,&fingerprint,&version]).await?;
    }
    transaction.commit().await?;
    Ok(())
}

async fn advance_scheduled(ctx: &Context, limit: usize) -> Result<()> {
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    let limit = i64::try_from(limit)?;
    let rows=transaction.query("SELECT t.map_id,t.instance_id,t.region_id,t.transition_at,t.target_weather FROM territory_weather_transitions t WHERE t.transition_at<=clock_timestamp() AND t.transition_at=(SELECT max(t2.transition_at) FROM territory_weather_transitions t2 WHERE t2.map_id=t.map_id AND t2.instance_id=t.instance_id AND t2.region_id=t.region_id AND t2.transition_at<=clock_timestamp()) ORDER BY t.map_id,t.instance_id,t.region_id LIMIT $1 FOR UPDATE OF t SKIP LOCKED",&[&limit]).await?;
    for scheduled in rows {
        let key: (i32, i64, i32) = (
            scheduled.get("map_id"),
            scheduled.get("instance_id"),
            scheduled.get("region_id"),
        );
        let current=transaction.query_opt("SELECT weather,native_payload,revision FROM territory_weather WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 FOR UPDATE",&[&key.0,&key.1,&key.2]).await?.context("Authoritative territory weather unavailable")?;
        let mut payload: Vec<u8> = current.get("native_payload");
        let (_, previous) = decode_weather(&payload)?;
        let weather: String = current.get("weather");
        ensure!(
            WEATHER[previous] == weather,
            "Inconsistent authoritative territory weather"
        );
        let when: DateTime<Utc> = scheduled.get("transition_at");
        transaction.execute("DELETE FROM territory_weather_transitions WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 AND transition_at<=$4",&[&key.0,&key.1,&key.2,&when]).await?;
        let target: String = scheduled.get("target_weather");
        if target == weather {
            continue;
        }
        let target_id = weather_id(&target)?;
        payload[33..37].copy_from_slice(&(target_id as i32).to_be_bytes());
        let revision:i64=transaction.query_one("UPDATE territory_weather SET weather=$1,native_payload=$2,revision=revision+1,updated_at=clock_timestamp() WHERE map_id=$3 AND instance_id=$4 AND region_id=$5 RETURNING revision",&[&target,&payload,&key.0,&key.1,&key.2]).await?.get(0);
        transaction.execute("INSERT INTO territory_weather_outbox (map_id,instance_id,region_id,revision,weather,native_payload) VALUES($1,$2,$3,$4,$5,$6)",&[&key.0,&key.1,&key.2,&revision,&target,&payload]).await?;
    }
    transaction.commit().await?;
    Ok(())
}

async fn forecast_packet(
    transaction: &Transaction<'_>,
    key: (i32, i64, i32),
    version: Option<i32>,
) -> Result<Option<Vec<u8>>> {
    let Some(policy)=transaction.query_opt("SELECT policy_version FROM territory_weather_forecast_policy WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 FOR SHARE",&[&key.0,&key.1,&key.2]).await? else {
        return Ok(Some(encode_forecast(&[],&[])?));
    };
    if version.is_some() && version != Some(policy.get(0)) {
        return Ok(None);
    }
    let rows=transaction.query("SELECT day_offset,season,temperature_sample_a,temperature_sample_b,wind_strength_u16,weather,temperature_adjustment_sample,signed_weather_modifier_i16::smallint AS signed_weather_modifier_i16 FROM territory_weather_forecast_days WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 ORDER BY day_offset",&[&key.0,&key.1,&key.2]).await?;
    let mut days = Vec::new();
    for (index, row) in rows.into_iter().enumerate() {
        ensure!(
            row.get::<_, i16>("day_offset") as usize == index + 1,
            "Non-contiguous local forecast day offsets"
        );
        let weather: String = row.get("weather");
        days.push(Day {
            season: row.get("season"),
            a: row.get("temperature_sample_a"),
            b: row.get("temperature_sample_b"),
            wind: row.get("wind_strength_u16"),
            weather: weather_id(&weather)?,
            adjustment: row.get("temperature_adjustment_sample"),
            modifier: row.get("signed_weather_modifier_i16"),
        });
    }
    let rows=transaction.query("SELECT season,actual_minimum_adjustment,actual_maximum_adjustment FROM territory_weather_forecast_season_adjustments WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 ORDER BY season",&[&key.0,&key.1,&key.2]).await?;
    let seasons: Vec<Season> = rows
        .into_iter()
        .map(|row| Season {
            season: row.get("season"),
            minimum: row.get("actual_minimum_adjustment"),
            maximum: row.get("actual_maximum_adjustment"),
        })
        .collect();
    Ok(Some(encode_forecast(&days, &seasons)?))
}

pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!(
        (1..=1000).contains(&limit),
        "Invalid ecology weather batch size"
    );
    let epoch = snapshot
        .get("world_epoch")
        .or_else(|| snapshot.get("epoch"))
        .and_then(Value::as_str)
        .context("Missing weather world epoch")?;
    advance_simulation(ctx, limit, None).await?;
    advance_scheduled(ctx, limit).await?;
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    transaction.execute("UPDATE territory_weather_outbox o SET superseded_at=clock_timestamp() FROM territory_weather w WHERE o.map_id=w.map_id AND o.instance_id=w.instance_id AND o.region_id=w.region_id AND o.revision<>w.revision AND o.published_at IS NULL AND o.superseded_at IS NULL",&[]).await?;
    let cap = i64::try_from(limit)?;
    let rows=transaction.query("SELECT o.map_id,o.instance_id,o.region_id,o.revision FROM territory_weather_outbox o JOIN territory_weather w USING(map_id,instance_id,region_id) WHERE o.published_at IS NULL AND o.superseded_at IS NULL AND o.revision=w.revision AND o.weather=w.weather AND o.native_payload=w.native_payload ORDER BY created_at,map_id,instance_id,region_id,revision LIMIT $1",&[&cap]).await?;
    let mut plans = Vec::new();
    for row in rows {
        plans.push(json!({"domain":"weather","operation":"publish","world_epoch":epoch,"event":{"map_id":row.get::<_,i32>("map_id"),"instance_id":row.get::<_,i64>("instance_id"),"region_id":row.get::<_,i32>("region_id"),"revision":row.get::<_,i64>("revision")}}));
    }
    transaction.commit().await?;
    drop(connection);
    if plans.len() == limit {
        return Ok(plans);
    }
    let territories = known_territories(ctx).await?;
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    transaction.execute("UPDATE territory_weather_forecast_outbox o SET superseded_at=clock_timestamp() FROM territory_weather_forecast_policy p WHERE o.map_id=p.map_id AND o.instance_id=p.instance_id AND o.region_id=p.region_id AND o.policy_version<>p.policy_version AND o.published_at IS NULL AND o.superseded_at IS NULL",&[]).await?;
    let remaining = i64::try_from(limit - plans.len())?;
    let rows=transaction.query("SELECT o.map_id,o.instance_id,o.region_id,o.policy_version FROM territory_weather_forecast_outbox o JOIN territory_weather_forecast_policy p USING(map_id,instance_id,region_id) WHERE o.published_at IS NULL AND o.superseded_at IS NULL AND o.policy_version=p.policy_version ORDER BY o.created_at,o.map_id,o.instance_id,o.region_id LIMIT $1",&[&remaining]).await?;
    // Python reads each packet in a fresh transaction after loading outbox rows.
    transaction.commit().await?;
    drop(connection);
    for row in rows {
        let key: (i32, i64, i32) = (
            row.get("map_id"),
            row.get("instance_id"),
            row.get("region_id"),
        );
        ensure!(
            territories.contains(&(key.0, key.2)),
            "Unknown local forecast territory"
        );
        let version: i32 = row.get("policy_version");
        let mut connection = ctx.db.get().await?;
        let transaction = connection.transaction().await?;
        let payload = forecast_packet(&transaction, key, Some(version)).await?;
        transaction.commit().await?;
        let Some(payload) = payload else {
            continue;
        };
        plans.push(json!({"domain":"weather","operation":"forecast_publish","world_epoch":epoch,"event":{"map_id":key.0,"instance_id":key.1,"region_id":key.2,"policy_version":version},"payload_hex":hex::encode(payload)}));
    }
    Ok(plans)
}

/// Exact authoritative weather policy consumed by planting probability.
pub async fn context_weather(
    ctx: &Context,
    map_id: i32,
    instance_id: i64,
    region_id: i32,
) -> Result<String> {
    ensure!(instance_id >= 0, "Invalid native territory instance");
    let key = (map_id, instance_id, region_id);
    let territories = known_territories(ctx).await?;
    ensure!(
        territories.contains(&(map_id, region_id)),
        "Unknown native map region"
    );
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    let existing=transaction.query_opt("SELECT weather,native_payload FROM territory_weather WHERE map_id=$1 AND instance_id=$2 AND region_id=$3",&[&map_id,&instance_id,&region_id]).await?;
    if existing.is_none() {
        let mut policy=transaction.query_opt("SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6 FROM territory_weather_local_policy WHERE map_id=$1 AND region_id=$2",&[&map_id,&region_id]).await?;
        if policy.is_none() {
            let row = transaction
                .query_opt(
                    "SELECT value FROM settings WHERE name='weather_local_baseline'",
                    &[],
                )
                .await?
                .context("Invalid local weather baseline configuration")?;
            let settings: Value = row.get(0);
            let object = settings
                .as_object()
                .context("Invalid local weather baseline configuration")?;
            ensure!(
                object.len() == 4
                    && ["weather", "native_byte", "native_values", "policy_version"]
                        .iter()
                        .all(|key| object.contains_key(*key)),
                "Invalid local weather baseline configuration"
            );
            let weather = settings["weather"]
                .as_str()
                .context("Invalid local weather policy state")?;
            weather_id(weather)?;
            let native_byte = i16::try_from(
                settings["native_byte"]
                    .as_i64()
                    .context("Invalid local weather policy byte")?,
            )?;
            ensure!(
                (-128..=127).contains(&native_byte),
                "Invalid local weather policy byte"
            );
            let version = i32::try_from(
                settings["policy_version"]
                    .as_i64()
                    .context("Invalid local weather policy version")?,
            )?;
            ensure!(version >= 1, "Invalid local weather policy version");
            let raw = settings["native_values"]
                .as_array()
                .context("Invalid local weather policy values")?;
            ensure!(raw.len() == 6, "Invalid local weather policy values");
            let values: Vec<f32> = raw
                .iter()
                .map(|value| {
                    value
                        .as_f64()
                        .map(|value| value as f32)
                        .filter(|value| value.is_finite())
                        .context("Invalid local weather policy float range")
                })
                .collect::<Result<_>>()?;
            transaction.execute("INSERT INTO territory_weather_local_policy (map_id,region_id,source,policy_version,weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6) VALUES($1,$2,'LOCAL_POLICY',$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT(map_id,region_id) DO NOTHING",&[&map_id,&region_id,&version,&weather,&native_byte,&values[0],&values[1],&values[2],&values[3],&values[4],&values[5]]).await?;
            policy=transaction.query_opt("SELECT weather,native_byte,value_1,value_2,value_3,value_4,value_5,value_6 FROM territory_weather_local_policy WHERE map_id=$1 AND region_id=$2",&[&map_id,&region_id]).await?;
        }
        let policy = policy.context("Authoritative local weather policy unavailable")?;
        let weather: String = policy.get("weather");
        let weather_index = weather_id(&weather)?;
        let native_byte: i16 = policy.get("native_byte");
        let mut payload = (region_id as i64).to_be_bytes().to_vec();
        payload.push(i8::try_from(native_byte).context("Invalid local weather policy byte")? as u8);
        for index in 1..=6 {
            let value: f32 = policy.get(format!("value_{index}").as_str());
            ensure!(
                value.is_finite(),
                "Invalid local weather policy float range"
            );
            payload.extend_from_slice(&value.to_be_bytes());
        }
        payload.extend_from_slice(&(weather_index as i32).to_be_bytes());
        transaction.query_one("INSERT INTO territory_weather (map_id,instance_id,region_id,weather,native_payload) VALUES($1,$2,$3,$4,$5) ON CONFLICT(map_id,instance_id,region_id) DO UPDATE SET weather=territory_weather.weather RETURNING weather",&[&map_id,&instance_id,&region_id,&weather,&payload]).await?;
    }
    transaction.commit().await?;
    drop(connection);
    advance_simulation(ctx, 1, Some(key)).await?;
    let mut connection = ctx.db.get().await?;
    let transaction = connection.transaction().await?;
    let row=transaction.query_one("SELECT weather,native_payload FROM territory_weather WHERE map_id=$1 AND instance_id=$2 AND region_id=$3 FOR SHARE",&[&map_id,&instance_id,&region_id]).await?;
    let weather: String = row.get("weather");
    let payload: Vec<u8> = row.get("native_payload");
    let (_, state) = decode_weather(&payload)?;
    ensure!(
        WEATHER[state] == weather,
        "Inconsistent authoritative territory weather"
    );
    forecast_packet(&transaction, key, None)
        .await?
        .context("Weather forecast policy was superseded")?;
    transaction.commit().await?;
    Ok(weather)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn policy() -> SimulationPolicy {
        SimulationPolicy::parse(&json!({"enabled":true,"seed":20261011,"day_seconds":86400,"forecast_days":5,"weather_weights":[60,25,12,3],"season_temperature_samples":[2,12,23,12],"temperature_variation":5,"wind_samples":[13107,22937,42598,62258]})).unwrap()
    }
    #[test]
    fn deterministic_weather_matches_python_vectors() {
        let policy = policy();
        assert_eq!(
            policy.fingerprint().unwrap(),
            "da0d699da99a77fd1369000924794e0818c82f2459e2eca2429610c5a526ce29"
        );
        for (day, payload) in [
            (
                0,
                "00000000000135c5063e4ccccd4040000041100000000000003e4ccccd0000000000000000",
            ),
            (
                1,
                "00000000000135c5073f2666a64080000041200000000000003f2666a60000000000000002",
            ),
            (
                100,
                "00000000000135c50b3e4ccccd4100000041600000000000003e4ccccd0000000000000000",
            ),
            (
                317,
                "00000000000135c5103eb332b34150000041980000000000003eb332b30000000000000001",
            ),
            (
                -1,
                "00000000000135c5043e4ccccd3f80000040e00000000000003e4ccccd0000000000000000",
            ),
        ] {
            assert_eq!(
                hex::encode(
                    modeled_payload(79301, &day_state(&policy, 1134, 79301, day).unwrap()).unwrap()
                ),
                payload
            );
        }
    }
    #[test]
    fn forecast_codec_matches_native_python_envelope() {
        let (days, seasons) = forecast_policy(&policy(), 1134, 79301, 317).unwrap();
        assert_eq!(hex::encode(encode_forecast(&days,&seasons).unwrap()),"00440503080e599900000001000000030d13333300000000000000030b1133330000000000000003090f33330000000000000003050bf3320000000300000001030414000000");
        assert_eq!(
            hex::encode(encode_forecast(&[], &[]).unwrap()),
            "00080000000000000000"
        );
        let mut missing = seasons.clone();
        missing.clear();
        assert!(encode_forecast(&days, &missing).is_err());
        let mut disabled = policy();
        disabled.enabled = false;
        let (days, seasons) = forecast_policy(&disabled, 1134, 79301, 317).unwrap();
        assert!(days.is_empty() && seasons.is_empty());
    }
    #[test]
    fn invalid_wire_or_policy_is_not_reinterpreted() {
        assert!(decode_weather(&[0; 36]).is_err());
        let mut payload = vec![0; 37];
        payload[9..13].copy_from_slice(&f32::NAN.to_be_bytes());
        assert!(decode_weather(&payload).is_err());
        let mut value = serde_json::to_value(policy()).unwrap();
        value["enabled"] = json!(1);
        assert!(SimulationPolicy::parse(&value).is_err());
        value = serde_json::to_value(policy()).unwrap();
        value["weather_weights"] = json!([0, 0, 0, 0]);
        assert!(SimulationPolicy::parse(&value).is_err());
        let negative = Day {
            season: 0,
            a: -8,
            b: -5,
            wind: 0,
            weather: 0,
            adjustment: 0,
            modifier: 0,
        };
        assert_eq!(modeled_payload(1, &negative).unwrap()[8] as i8, -7);
    }
    #[test]
    fn yearly_weather_is_deterministic_territory_specific_and_spans_native_states() {
        let policy = policy();
        let states: Vec<_> = (0..366)
            .map(|day| day_state(&policy, 1134, 79201, day).unwrap())
            .collect();
        let repeated: Vec<_> = (0..366)
            .map(|day| day_state(&policy, 1134, 79201, day).unwrap())
            .collect();
        let other_territory: Vec<_> = (0..366)
            .map(|day| day_state(&policy, 1134, 79301, day).unwrap())
            .collect();
        assert_eq!(states, repeated);
        assert_ne!(states, other_territory);
        assert_eq!(
            states
                .iter()
                .map(|day| day.weather)
                .collect::<BTreeSet<_>>(),
            BTreeSet::from([0, 1, 2, 3])
        );
        assert_eq!(
            states.iter().map(|day| day.season).collect::<BTreeSet<_>>(),
            BTreeSet::from([0, 1, 2, 3])
        );
    }

    #[test]
    fn accelerated_forecasts_remain_native_encodable_and_predict_future_states() {
        let policy = policy();
        for day in [-300, 0, 90, 180, 270, 100_000_000] {
            let (days, seasons) = forecast_policy(&policy, 1134, 79201, day).unwrap();
            assert_eq!(days.len(), 5);
            for (offset, forecast) in days.iter().enumerate() {
                assert_eq!(
                    *forecast,
                    day_state(&policy, 1134, 79201, day + offset as i64 + 1).unwrap()
                );
            }
            let packet = encode_forecast(&days, &seasons).unwrap();
            assert_eq!(
                u16::from_be_bytes(packet[..2].try_into().unwrap()) as usize,
                packet.len() - 2
            );
            assert_eq!(packet[2], 5);
            let seasons_offset = 3 + days.len() * 12;
            assert_eq!(packet[seasons_offset] as usize, seasons.len());
            assert_eq!(packet.len(), seasons_offset + 1 + seasons.len().max(2) * 3);
        }
    }

    #[test]
    fn yearly_current_wire_and_forecast_ranges_share_native_temperature_and_wind_scale() {
        let policy = policy();
        for day in 0..366 {
            let current = day_state(&policy, 1134, 79201, day).unwrap();
            let packet = modeled_payload(79201, &current).unwrap();
            assert_eq!(decode_weather(&packet).unwrap(), (79201, current.weather));
            assert_eq!(
                packet[8] as i8 as f32,
                f32::from(current.a + current.b) / 2.0
            );
            let value = |offset| f32::from_be_bytes(packet[offset..offset + 4].try_into().unwrap());
            assert_eq!(value(13), f32::from(current.a));
            assert_eq!(value(17), f32::from(current.b));
            assert!((f64::from(value(9)) - f64::from(current.wind) / 65535.0).abs() < 1e-7);
            assert_eq!(value(9), value(25));
            let (days, seasons) = forecast_policy(&policy, 1134, 79201, day).unwrap();
            for forecast in days {
                let bounds = seasons
                    .iter()
                    .find(|season| season.season == forecast.season)
                    .unwrap();
                assert!(bounds.minimum <= forecast.a);
                assert!(bounds.maximum >= forecast.b);
            }
        }
    }

    #[test]
    fn yearly_zero_weight_weather_never_occurs() {
        let mut policy = policy();
        policy.weather_weights = [0, 0, 1, 0];
        for day in 0..366 {
            assert_eq!(
                WEATHER[day_state(&policy, 1134, 79201, day).unwrap().weather],
                "HEAVY"
            );
        }
    }

    #[test]
    fn invalid_simulation_policy_fields_fail_closed() {
        for (name, invalid) in [
            ("enabled", json!(1)),
            ("day_seconds", json!(true)),
            ("forecast_days", json!(256)),
            ("weather_weights", json!([0, 0, 0, 0])),
            ("seed", json!(-1)),
            ("season_temperature_samples", json!([127, 127, 127, 127])),
            ("wind_samples", json!([65536, 65536, 65536, 65536])),
        ] {
            let mut value = serde_json::to_value(policy()).unwrap();
            value[name] = invalid;
            assert!(
                SimulationPolicy::parse(&value).is_err(),
                "Accepted invalid {name}"
            );
        }
    }
}
