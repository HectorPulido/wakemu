//! Read-only native planting admission. World revalidates every final mutation.
use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::OnceLock;

use anyhow::{anyhow, bail, ensure, Context as _, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio_postgres::GenericClient;

use crate::Context;

const FOOTPRINTS: &[u8] =
    include_bytes!("../../../../../wakfu_server/items/native_ranch_building_footprints.json");
const TOPOLOGY: &[u8] =
    include_bytes!("../../../../../wakfu_server/items/native_ranch_biome_topology.json");
const BUILDINGS: &[u8] =
    include_bytes!("../../../../../wakfu_server/items/native_ranch_building_definitions.json");
const FOOTPRINT_SHA: &str = "f91ff213662da8a2b7c304b26cf3c949cd4240965e759deb6fead38a348a504c";
const TOPOLOGY_SHA: &str = "14083bf59e648102af3b3c8c64a3a731b6d470245390a7f9c6bbaeeb161b10dc";
const BUILDINGS_SHA: &str = "733982c0f8b5ac033756f4f2377aac766f1e6beba4a6620096cadf2b93a25c4b";
type Cell = (i64, i64, i64);

fn integer(value: &Value, name: &str) -> Result<i64> {
    value
        .get(name)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Missing native planting integer {name}"))
}
fn array(value: &Value) -> Result<&Vec<Value>> {
    value
        .as_array()
        .ok_or_else(|| anyhow!("Malformed native planting array"))
}
fn tuple(row: &Value) -> Result<Cell> {
    let row = array(row)?;
    ensure!(row.len() == 3, "Malformed native planting geometry cell");
    Ok((
        row[0].as_i64().context("Invalid native x")?,
        row[1].as_i64().context("Invalid native y")?,
        row[2].as_i64().context("Invalid native z")?,
    ))
}
fn actor_cell(actor: &Value) -> Result<Cell> {
    Ok((
        integer(actor, "x")?,
        integer(actor, "y")?,
        integer(actor, "z")?,
    ))
}
fn pinned<'a>(bytes: &[u8], expected: &str, cache: &'a OnceLock<Value>) -> Result<&'a Value> {
    if let Some(value) = cache.get() {
        return Ok(value);
    }
    ensure!(
        hex::encode(Sha256::digest(bytes)) == expected,
        "Conflicting pinned planting policy data"
    );
    if cache.get().is_none() {
        let _ = cache.set(serde_json::from_slice(bytes)?);
    }
    cache.get().context("Missing pinned planting policy")
}
fn topology() -> Result<&'static Value> {
    static CACHE: OnceLock<Value> = OnceLock::new();
    let data = pinned(TOPOLOGY, TOPOLOGY_SHA, &CACHE)?;
    ensure!(
        data["schema_version"] == 1
            && data["native_class"] == "fBm"
            && data["native_biome_id"] == 1
            && data["native_world_map_id"] == 1440,
        "Unsupported native Ranch biome topology"
    );
    Ok(data)
}
fn footprints() -> Result<&'static Value> {
    static CACHE: OnceLock<Value> = OnceLock::new();
    let data = pinned(FOOTPRINTS, FOOTPRINT_SHA, &CACHE)?;
    ensure!(
        data["schema_version"] == 1
            && data["source_asset_sha256"]
                == "83d32ce93198d3d71d95a97697662a7c945e1f5db5f2e5ad9f045375afff1fed"
            && data["definition_catalog_sha256"] == BUILDINGS_SHA,
        "Unsupported native Ranch footprint evidence"
    );
    Ok(data)
}
fn building_definitions() -> Result<&'static Value> {
    static CACHE: OnceLock<Value> = OnceLock::new();
    let data = pinned(BUILDINGS, BUILDINGS_SHA, &CACHE)?;
    ensure!(
        data["schema_version"] == 1 && data["native_class"] == "aMR",
        "Unsupported native Ranch building catalog"
    );
    Ok(data)
}
fn sector_for_cell(x: i64, y: i64) -> Result<Option<i64>> {
    let mut found = None;
    for area in array(&topology()?["terrain_areas"])? {
        if array(&area["chunks"])?
            .iter()
            .any(|c| c == &json!([x.div_euclid(18), y.div_euclid(18)]))
        {
            ensure!(
                found.is_none(),
                "Native Ranch terrain chunk has ambiguous area ownership"
            );
            found = Some(integer(area, "id")?);
        }
    }
    Ok(found)
}

async fn planting_cells(ctx: &Context, map_id: i32, x: i64, y: i64) -> Result<Vec<Value>> {
    ctx.catalog
        .surfaces_at(map_id, i32::try_from(x)?, i32::try_from(y)?)
        .await
}
async fn ranch_surfaces(ctx: &Context, x: i64, y: i64) -> Result<Vec<Value>> {
    let candidates = planting_cells(ctx, 1440, x, y).await?;
    let geometry = ctx.catalog.map_geometry(1440).await?;
    let cells: HashSet<_> = array(&geometry["cells"])?
        .iter()
        .map(tuple)
        .collect::<Result<_>>()?;
    let filtered = candidates
        .into_iter()
        .filter(|c| c["z"].as_i64().is_some_and(|z| cells.contains(&(x, y, z))))
        .collect::<Vec<_>>();
    ensure!(!filtered.is_empty(), "Absent native Ranch planting surface");
    Ok(filtered)
}
fn private_garden(actor: &Value) -> bool {
    let Some(instance) = actor["instance_id"].as_i64().filter(|v| *v > 0) else {
        return false;
    };
    match actor["map_id"].as_i64() {
        Some(9) => {
            instance
                == actor["haven_bag"]["owner_id"]
                    .as_i64()
                    .or(actor["id"].as_i64())
                    .unwrap_or(0)
        }
        Some(1440) => {
            actor["haven_ranch_session"] == true
                && actor["haven_bag"]["owner_id"].as_i64() == Some(instance)
        }
        _ => false,
    }
}
fn garden_room(actor: &Value, x: i64, y: i64) -> Result<()> {
    ensure!(
        integer(actor, "map_id")? == 9 && private_garden(actor),
        "Garden requires the active Haven Bag layout"
    );
    ensure!(
        (0..18).contains(&x) && (0..18).contains(&y),
        "Garden target is outside the Haven Bag rooms"
    );
    let index = (x / 6) * 3 + y / 6;
    let room = array(&actor["haven_bag"]["rooms"])?
        .iter()
        .find(|r| r["index"].as_i64() == Some(index))
        .context("Planting requires an installed garden gem")?;
    ensure!(
        room["enabled"] == true && matches!(room["primary_ref"].as_i64(), Some(4266 | 11099)),
        "Planting requires an installed garden gem"
    );
    Ok(())
}

fn building_occupied(rows: &[Value], x: i64, y: i64) -> Result<bool> {
    let definitions = array(&building_definitions()?["definitions"])?;
    let shapes = array(&footprints()?["footprints"])?;
    let mut ids = HashSet::new();
    let mut occupied = false;
    for row in rows {
        let uid = integer(row, "uid")?;
        ensure!(
            uid > 0 && ids.insert(uid),
            "Malformed native Ranch building collision identity"
        );
        let reference = integer(row, "building_ref")?;
        let def = definitions
            .iter()
            .find(|r| r["p"].as_i64() == Some(reference))
            .context("Persisted Ranch building has no pinned aMR definition")?;
        let mode = integer(row, "mode_id")?;
        let kind = integer(row, "view_kind")?;
        let selector = integer(row, "view_value")?;
        let selected = array(&def["epD"])?
            .iter()
            .find(|r| r["p"].as_i64() == Some(mode))
            .context("Native Ranch building mode is unavailable")?;
        let (list, key) = match kind {
            0 => ("epP", "epS"),
            1 => ("epQ", "epL"),
            _ => bail!("Native Ranch building view is unavailable for this mode"),
        };
        let view = array(&selected[list])?
            .iter()
            .find(|r| r[key].as_i64() == Some(selector))
            .context("Native Ranch building view is unavailable for this mode")?;
        let shape = shapes
            .iter()
            .find(|r| {
                r["building_ref"].as_i64() == Some(reference)
                    && r["mode_id"].as_i64() == Some(mode)
                    && r["selection_kind"].as_i64() == Some(kind)
                    && r["selector_value"].as_i64() == Some(selector)
            })
            .context("Original Ranch collision footprint is unavailable")?;
        ensure!(
            shape["native_view_id"] == view["epM"]["eki"],
            "Original Ranch collision footprint is unavailable"
        );
        let ox = integer(row, "x")?;
        let oy = integer(row, "y")?;
        for c in array(&shape["cells"])? {
            let c = array(c)?;
            ensure!(c.len() == 2, "Malformed native Ranch footprint cell");
            let dx = c[0].as_i64().context("Invalid Ranch footprint x")?;
            let dy = c[1].as_i64().context("Invalid Ranch footprint y")?;
            occupied |= ox.checked_add(dx) == Some(x) && oy.checked_add(dy) == Some(y);
        }
    }
    Ok(occupied)
}
async fn assert_cell_empty<C: GenericClient + Sync>(
    db: &C,
    map_id: i32,
    instance: i64,
    x: i32,
    y: i32,
) -> Result<()> {
    if db.query_opt("SELECT 1 FROM mining_vein_slots WHERE map_id=$1 AND instance_id=$2 AND x=$3 AND y=$4 AND enabled", &[&map_id,&instance,&x,&y]).await?.is_some() { bail!("Planting surface is reserved for a mineral vein"); }
    if db.query_opt("SELECT 1 FROM fishing_spot_slots WHERE map_id=$1 AND instance_id::bigint=$2 AND x=$3 AND y=$4 AND enabled", &[&map_id,&instance,&x,&y]).await?.is_some() { bail!("Planting surface is reserved for a fishing spot"); }
    ensure!(
        db.query_opt(
            "SELECT 1 FROM planted_resources WHERE map_id=$1 AND instance_id=$2 AND x=$3 AND y=$4",
            &[&map_id, &instance, &x, &y]
        )
        .await?
        .is_none(),
        "Planting surface is occupied"
    );
    Ok(())
}
async fn ranch_empty(ctx: &Context, actor: &Value, x: i32, y: i32) -> Result<()> {
    let owner = integer(actor, "instance_id")?;
    ensure!(
        owner > 0,
        "Private Ranch requires its canonical host instance"
    );
    let mut client = ctx.db.get().await?;
    let tx = client.transaction().await?;
    tx.batch_execute("SET LOCAL statement_timeout='1s'; SET LOCAL lock_timeout='250ms'")
        .await?;
    ensure!(tx.query_opt("SELECT 1 FROM haven_ranch_furniture WHERE owner_character_id=$1 AND map_id=1440 AND x=$2 AND y=$3", &[&owner,&x,&y]).await?.is_none(), "Planting surface contains Ranch furniture");
    let account: i64 = tx
        .query_opt(
            "SELECT account_id FROM account_haven_bags WHERE character_id=$1",
            &[&owner],
        )
        .await?
        .context("Private Ranch has no canonical account binding")?
        .get(0);
    let buildings = tx
        .query(
            "SELECT to_jsonb(b) FROM account_ranch_buildings b WHERE account_id=$1 AND biome_id=1",
            &[&account],
        )
        .await?
        .into_iter()
        .map(|r| r.get::<_, Value>(0))
        .collect::<Vec<_>>();
    ensure!(
        !building_occupied(&buildings, x.into(), y.into())?,
        "Planting surface contains a native Ranch building"
    );
    let paddocks=tx.query("SELECT uid,sector_id FROM account_ranch_paddocks WHERE account_id=$1 AND biome_id=1 AND active=TRUE ORDER BY uid", &[&account]).await?;
    let mut by_sector: HashMap<i64, HashSet<i64>> = HashMap::new();
    for row in paddocks {
        let uid: i64 = row.get(0);
        let sector: i32 = row.get(1);
        ensure!(uid > 0, "Malformed native Ranch paddock identity");
        by_sector.entry(sector.into()).or_default().insert(uid);
    }
    let creatures=tx.query("SELECT to_jsonb(c) FROM account_ranch_creatures c WHERE account_id=$1 AND biome_id=1 AND inventory=FALSE AND released_at IS NULL ORDER BY uid", &[&account]).await?;
    let mut seen = HashSet::new();
    let mut blocked = false;
    for row in creatures {
        let c: Value = row.get(0);
        let uid = integer(&c, "uid")?;
        let sector = integer(&c, "sector_id")?;
        let px = integer(&c, "x")?;
        let py = integer(&c, "y")?;
        let paddock = c["paddock_uid"].as_i64().unwrap_or(-1);
        ensure!(
            uid > 0
                && seen.insert(uid)
                && c["inventory"] == false
                && c["biome_id"] == 1
                && by_sector.get(&sector).is_some_and(|p| p.contains(&paddock))
                && sector_for_cell(px, py)? == Some(sector),
            "Invalid native Ranch creature occupancy identity"
        );
        blocked |= px == i64::from(x) && py == i64::from(y);
    }
    ensure!(
        !blocked,
        "Planting surface contains a deployed Ranch creature"
    );
    assert_cell_empty(&*tx, 1440, owner, x, y).await?;
    tx.commit().await?;
    Ok(())
}
fn edges(geometry: &Value) -> Result<HashMap<Cell, Vec<Cell>>> {
    let mut graph: HashMap<Cell, Vec<Cell>> = HashMap::new();
    for edge in array(&geometry["edges"])? {
        let e = array(edge)?;
        ensure!(e.len() == 2, "Malformed native planting geometry edge");
        graph.entry(tuple(&e[0])?).or_default().push(tuple(&e[1])?);
    }
    Ok(graph)
}
fn reachable_surfaces(
    actor: &Value,
    x: i64,
    y: i64,
    candidates: &[Value],
    geometry: &Value,
) -> Result<Vec<Value>> {
    let graph = edges(geometry)?;
    let source = actor_cell(actor)?;
    let targets = candidates
        .iter()
        .map(|c| Ok(((x, y, integer(c, "z")?), c.clone())))
        .collect::<Result<HashMap<_, _>>>()?;
    let mut queue = VecDeque::from([source]);
    let mut seen = HashSet::from([source]);
    while !queue.is_empty() {
        let mut layer = Vec::new();
        for _ in 0..queue.len() {
            let p = queue.pop_front().unwrap();
            if let Some(c) = targets.get(&p) {
                layer.push(c.clone());
            }
            for n in graph.get(&p).into_iter().flatten() {
                if seen.insert(*n) {
                    queue.push_back(*n);
                }
            }
        }
        if !layer.is_empty() {
            return Ok(layer);
        }
    }
    Ok(Vec::new())
}
fn ground_percent(grounds: &Value, resource: &Value, ground_id: i64) -> Result<f64> {
    let Some(ground) = array(grounds)?
        .iter()
        .find(|r| r["ground_id"].as_i64() == Some(ground_id))
    else {
        return Ok(0.0);
    };
    let reference = integer(resource, "resource_reference")?.to_string();
    let family = integer(resource, "family_id")?.to_string();
    let v = ground["resources"]
        .get(&reference)
        .filter(|value| !value.is_null())
        .or_else(|| ground["families"].get(&family));
    v.map(|v| {
        v.as_f64()
            .context("Invalid native planting ground percentage")
    })
    .unwrap_or(Ok(0.0))
}

/// Resolve a unique native planting height and all read-only occupation fences.
/// The caller supplies the SQL-owned actor overlaid with its authorized live scene.
pub async fn authorize_cell(
    ctx: &Context,
    actor: &Value,
    request: &Value,
    _seed: &Value,
    resource: &Value,
    open_policy: bool,
) -> Result<i16> {
    let map_id = i32::try_from(integer(actor, "map_id")?)?;
    let instance = integer(actor, "instance_id")?;
    let source = actor_cell(actor)?;
    ensure!(
        i32::try_from(source.0).is_ok()
            && i32::try_from(source.1).is_ok()
            && i16::try_from(source.2).is_ok(),
        "Invalid authoritative planting position"
    );
    let x = i32::try_from(integer(request, "x")?)?;
    let y = i32::try_from(integer(request, "y")?)?;
    ensure!(map_id > 0 && instance >= 0, "Invalid planting scope");
    if map_id == 9 {
        ensure!(
            resource["monster_resource"] == false,
            "Monster reproduction is unavailable inside private gardens"
        );
        garden_room(actor, x.into(), y.into())?;
        let source = actor_cell(actor)?;
        ensure!(
            source.2 == 0 && source.0.abs_diff(x.into()) + source.1.abs_diff(y.into()) == 1,
            "Move next to the garden planting cell"
        );
        for item in array(&actor["haven_bag"]["furniture"])? {
            if item["deployed"] == true
                && item["x"].as_i64() == Some(x.into())
                && item["y"].as_i64() == Some(y.into())
            {
                bail!("Garden planting cell contains furniture");
            }
        }
        let db = ctx.db.get().await?;
        ensure!(db.query_opt("SELECT 1 FROM planted_resources WHERE map_id=9 AND instance_id=$1 AND x=$2 AND y=$3", &[&instance,&x,&y]).await?.is_none(),"Garden planting cell is occupied");
        return Ok(0);
    }
    let geometry = ctx.catalog.map_geometry(map_id).await?;
    let candidates = if map_id == 1440 {
        ensure!(
            private_garden(actor),
            "Merkalugar planting requires an active private Ranch"
        );
        ranch_surfaces(ctx, x.into(), y.into()).await?
    } else {
        let grounds = ctx.catalog.document("planting-grounds.json").await?;
        let mut selected = Vec::new();
        for c in planting_cells(ctx, map_id, x.into(), y.into()).await? {
            let ground = integer(&c, "ground_id")?;
            if open_policy || ground != 0 && ground_percent(&grounds, resource, ground)? > 0.0 {
                selected.push(c);
            }
        }
        if open_policy && selected.len() > 1 {
            reachable_surfaces(actor, x.into(), y.into(), &selected, &geometry)?
        } else {
            selected
        }
    };
    ensure!(
        candidates.len() == 1,
        if map_id == 1440 {
            "Absent or ambiguous native Ranch planting height"
        } else {
            "Absent or ambiguous native planting surface"
        }
    );
    let z = i16::try_from(integer(&candidates[0], "z")?)?;
    let source = actor_cell(actor)?;
    let target = (i64::from(x), i64::from(y), i64::from(z));
    ensure!(
        edges(&geometry)?
            .get(&source)
            .is_some_and(|out| out.contains(&target)),
        if map_id == 1440 {
            "Move next to the garden planting cell"
        } else {
            "Move next to the planting cell"
        }
    );
    if map_id == 1440 {
        ranch_empty(ctx, actor, x, y).await?;
    } else {
        let db = ctx.db.get().await?;
        assert_cell_empty(&**db, map_id, instance, x, y).await?;
    }
    Ok(z)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ranch_data_are_pinned() {
        assert!(topology().is_ok());
        assert!(footprints().is_ok());
        assert!(building_definitions().is_ok());
    }
    #[test]
    fn garden_room_requires_actual_owner_and_gem() {
        let mut actor = json!({"id":7,"map_id":9,"instance_id":7,"haven_bag":{"owner_id":7,"rooms":[{"index":0,"enabled":true,"primary_ref":4266}]}});
        assert!(garden_room(&actor, 0, 0).is_ok());
        assert!(garden_room(&actor, 6, 0).is_err());
        actor["instance_id"] = json!(8);
        assert!(garden_room(&actor, 0, 0).is_err());
    }
    #[test]
    fn nearest_native_surface_is_not_an_arbitrary_height() {
        let actor = json!({"x":0,"y":0,"z":0});
        let candidates = vec![json!({"z":0}), json!({"z":3})];
        let geo = json!({"edges":[[[0,0,0],[1,0,3]],[[1,0,3],[2,0,0]],[[2,0,0],[1,0,0]]]});
        let result = reachable_surfaces(&actor, 1, 0, &candidates, &geo).unwrap();
        assert_eq!(result, vec![json!({"z":3})]);
    }
    #[test]
    fn public_ground_override_zero_precedes_family() {
        let grounds = json!([{"ground_id":28,"resources":{"1":0},"families":{"2":100}}]);
        let resource = json!({"resource_reference":1,"family_id":2});
        assert_eq!(ground_percent(&grounds, &resource, 28).unwrap(), 0.0);
        let missing = json!([{"ground_id":28,"resources":{"1":null},"families":{"2":100}}]);
        assert_eq!(ground_percent(&missing, &resource, 28).unwrap(), 100.0);
    }
}
