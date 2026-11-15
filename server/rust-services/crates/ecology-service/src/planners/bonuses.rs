//! Read complete regional populations outside World ownership locks.
use std::collections::{BTreeMap, BTreeSet};
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, ensure, Context as _, Result};
use serde_json::{json, Map, Value};

use crate::Context;

fn integer(value: &Value, label: &str) -> Result<i64> {
    value.as_i64().ok_or_else(|| anyhow!("Invalid {label}"))
}

fn scopes(snapshot: &Value) -> Result<BTreeSet<(i32, i64)>> {
    let mut result = BTreeSet::new();
    let players = match snapshot.get("players") {
        Some(value) => value
            .as_array()
            .ok_or_else(|| anyhow!("Invalid regional bonus player list"))?,
        None => return Ok(result),
    };
    for player in players {
        let map = integer(&player["map_id"], "regional bonus map")?;
        let instance = integer(&player["instance_id"], "regional bonus instance")?;
        ensure!(
            map > 0 && map <= i32::MAX as i64 && instance >= 0,
            "Invalid regional bonus scope"
        );
        result.insert((map as i32, instance));
    }
    Ok(result)
}

fn control_health_policy(value: &Value) -> Result<BTreeMap<String, i64>> {
    let object = value
        .as_object()
        .ok_or_else(|| anyhow!("Missing or invalid territory control health policy"))?;
    ensure!(
        object.len() == 2
            && object.contains_key("schema_version")
            && object.contains_key("states")
            && value["schema_version"].as_i64() == Some(1),
        "Missing or invalid territory control health policy"
    );
    let states = value["states"]
        .as_object()
        .ok_or_else(|| anyhow!("Missing or invalid territory control health policy"))?;
    ensure!(
        states.len() == 3,
        "Missing or invalid territory control health policy"
    );
    let mut output = BTreeMap::new();
    for key in ["1915", "1916", "1917"] {
        let number = states
            .get(key)
            .and_then(Value::as_i64)
            .ok_or_else(|| anyhow!("Missing or invalid territory control health policy"))?;
        ensure!(
            (-1000..=1000).contains(&number),
            "Missing or invalid territory control health policy"
        );
        output.insert(key.to_owned(), number);
    }
    Ok(output)
}

fn state_id(satisfied: usize, total: usize) -> Option<i64> {
    if total == 0 {
        None
    } else if satisfied == 0 {
        Some(1917)
    } else if satisfied == total {
        Some(1916)
    } else {
        Some(1915)
    }
}

fn evaluate(territory: &Value, counts: &Value) -> Result<Option<i64>> {
    let mut total = 0;
    let mut satisfied = 0;
    for (wishes, kind) in [("monster_wishes", "monster"), ("plant_wishes", "plant")] {
        for wish in territory[wishes]
            .as_array()
            .ok_or_else(|| anyhow!("Missing native territory wishes"))?
        {
            total += 1;
            let family = integer(&wish["family_id"], "wish family")?.to_string();
            let count = counts
                .get(kind)
                .and_then(|counts| counts.get(&family))
                .and_then(Value::as_i64)
                .unwrap_or(0);
            ensure!(count >= 0, "Invalid native family population count");
            let minimum = integer(&wish["minimum"], "wish minimum")?;
            let maximum = integer(&wish["maximum"], "wish maximum")?;
            if minimum <= count && count <= maximum {
                satisfied += 1;
            }
        }
    }
    Ok(state_id(satisfied, total))
}

fn stat_bonuses(
    catalog: &Value,
    state: Option<i64>,
    policy: &BTreeMap<String, i64>,
) -> Result<Value> {
    let Some(state) = state else {
        return Ok(json!({}));
    };
    let mut output = Map::new();
    let key = state.to_string();
    let effects = catalog["states"][&key]["effects"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing native protector effects"))?;
    for effect in effects {
        let (characteristic, sign) = match effect["effect_class"].as_i64() {
            Some(166) => ("36", 1),
            Some(167) => ("36", -1),
            Some(162) => ("33", 1),
            Some(163) => ("33", -1),
            _ => continue,
        };
        let values = effect["parameters"].as_array();
        let value = values
            .filter(|values| values.len() == 1)
            .and_then(|values| values[0].as_f64());
        if effect["variant"].as_i64() != Some(0)
            || effect["criteria"].as_str() != Some("")
            || value.is_none()
            || !(0.0..=1000.0).contains(&value.unwrap_or(-1.0))
            || output.contains_key(characteristic)
        {
            return Ok(json!({}));
        }
        output.insert(
            characteristic.to_owned(),
            json!(sign * value.unwrap() as i64),
        );
    }
    output.insert(
        "1".to_owned(),
        json!(policy
            .get(&key)
            .ok_or_else(|| anyhow!("Unknown territory control health state"))?),
    );
    Ok(Value::Object(output))
}

async fn revision(db: &tokio_postgres::Transaction<'_>, scope: (i32, i64)) -> Result<i64> {
    let dirty_map_id = i64::from(scope.0);
    Ok(db
        .query_opt(
            "SELECT revision FROM ecology_dirty_scopes WHERE map_id=$1 AND instance_id=$2",
            &[&dirty_map_id, &scope.1],
        )
        .await?
        .map_or(0, |row| row.get(0)))
}

pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!(
        (1..=64).contains(&limit),
        "Invalid regional bonus preparation limit"
    );
    let epoch = snapshot
        .get("world_epoch")
        .or_else(|| snapshot.get("epoch"))
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .context("Missing regional bonus world epoch")?;
    let mut scopes: Vec<_> = scopes(snapshot)?.into_iter().collect();
    if scopes.is_empty() {
        return Ok(vec![]);
    }
    let tick = snapshot
        .get("domain_planning_tick")
        .or_else(|| snapshot.get("planning_tick"))
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let offset = tick.rem_euclid(scopes.len() as i64) as usize;
    scopes.rotate_left(offset);
    scopes.truncate(limit);
    let catalog = ctx
        .catalog
        .document("territory-protector-bonuses.json")
        .await?;
    let territories = catalog["territories"]
        .as_object()
        .context("Missing protector territory catalog")?;
    let health = {
        let mut connection = ctx.db.get().await?;
        let transaction = connection.transaction().await?;
        let row = transaction
            .query_opt(
                "SELECT value FROM settings WHERE name='territory_control_health_policy'",
                &[],
            )
            .await?
            .context("Missing territory control health policy")?;
        let value: Value = row.get(0);
        let policy = control_health_policy(&value)?;
        transaction.commit().await?;
        policy
    };
    let mut output = Vec::new();
    for scope in scopes {
        let observed = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs_f64();
        let mut connection = ctx.db.get().await?;
        let transaction = connection.transaction().await?;
        let before = revision(&transaction, scope).await?;
        let population = ctx
            .catalog
            .population_snapshot_regional(&transaction, scope.0, scope.1)
            .await?;
        let after = revision(&transaction, scope).await?;
        transaction.commit().await?;
        if before != after {
            continue;
        }
        let complete = population["complete"].as_bool().unwrap_or(false);
        let mut regions = Map::new();
        let mut states = Map::new();
        for (region, territory) in territories {
            if territory["map_id"].as_i64() != Some(scope.0 as i64) {
                continue;
            }
            let state = if complete {
                evaluate(territory, &population["regions"][region])?
            } else {
                None
            };
            states.insert(region.clone(), json!(state));
            regions.insert(region.clone(), stat_bonuses(&catalog, state, &health)?);
        }
        output.push(json!({"domain":"bonuses", "operation":"regional_snapshot", "world_epoch":epoch,
            "map_id":scope.0,"instance_id":scope.1,"revision":after,"regions":regions,
            "region_states":states,"observed_at":observed,"observation_bucket":(observed / 2.0).floor() as i64}));
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wishes_and_effect_mapping_preserve_native_state_policy() {
        let territory = json!({"monster_wishes":[{"family_id":5,"minimum":2,"maximum":4}],"plant_wishes":[{"family_id":8,"minimum":1,"maximum":3}]});
        assert_eq!(
            evaluate(&territory, &json!({"monster":{"5":3},"plant":{"8":2}})).unwrap(),
            Some(1916)
        );
        assert_eq!(
            evaluate(&territory, &json!({"monster":{"5":3}})).unwrap(),
            Some(1915)
        );
        assert_eq!(evaluate(&territory, &json!({})).unwrap(), Some(1917));
        let catalog = json!({"states":{"1915":{"effects":[{"effect_class":166,"variant":0,"criteria":"","parameters":[12.9]},{"effect_class":163,"variant":0,"criteria":"","parameters":[3]}]}}});
        let policy = control_health_policy(
            &json!({"schema_version":1,"states":{"1915":4,"1916":5,"1917":-2}}),
        )
        .unwrap();
        assert_eq!(
            stat_bonuses(&catalog, Some(1915), &policy).unwrap(),
            json!({"1":4,"36":12,"33":-3})
        );
        assert_eq!(stat_bonuses(&catalog, None, &policy).unwrap(), json!({}));
    }
    #[test]
    fn incomplete_or_invalid_policy_never_grants_partial_bonus() {
        assert!(control_health_policy(
            &json!({"schema_version":true,"states":{"1915":0,"1916":0,"1917":0}})
        )
        .is_err());
        assert!(control_health_policy(
            &json!({"schema_version":1,"states":{"1915":true,"1916":0,"1917":0}})
        )
        .is_err());
        let policy = BTreeMap::from([("1915".to_owned(), 1)]);
        let catalog = json!({"states":{"1915":{"effects":[{"effect_class":166,"variant":1,"criteria":"","parameters":[10]}]}}});
        assert_eq!(
            stat_bonuses(&catalog, Some(1915), &policy).unwrap(),
            json!({})
        );
        assert!(scopes(&json!({"players":[{"map_id":1,"instance_id":-1}]})).is_err());
    }
}
