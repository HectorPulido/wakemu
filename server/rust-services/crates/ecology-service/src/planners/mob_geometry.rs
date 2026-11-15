//! Native directed monster movement and immutable birth-territory fences.
//!
//! Planning never commits actor positions or sends packets. World rechecks the
//! exact roster, epoch, occupancy and durable receipts before publication.
use crate::Context;
#[cfg(test)]
use rand::Rng;
use anyhow::{anyhow, ensure, Result};
use serde_json::{json, Value};
use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

pub use wakemu_world_spatial::geometry::*;

type SpatialCacheKey = (String, String, i64);
fn spatial_cache_key(
    revision: &str,
    generation: Option<&str>,
    map_id: i64,
) -> Option<SpatialCacheKey> {
    generation.map(|generation| (revision.to_owned(), generation.to_owned(), map_id))
}
fn spatial_key_charge(key: &SpatialCacheKey) -> usize {
    key.0
        .capacity()
        .saturating_add(key.1.capacity())
        .saturating_add(64)
}
const TERRAIN_CACHE_BYTES: usize = 8 * 1024 * 1024;
#[derive(Default)]
struct TerrainCache {
    entries: VecDeque<((SpatialCacheKey, bool), Arc<TerrainPolicy>, usize)>,
    bytes: usize,
}
static TERRAINS: OnceLock<Mutex<TerrainCache>> = OnceLock::new();
fn hash_map_charge<K, V>(map: &HashMap<K, V>) -> usize {
    map.capacity()
        .saturating_mul(8)
        .div_ceil(7)
        .saturating_mul(std::mem::size_of::<(K, V)>() + 1)
}
fn terrain_charge(terrain: &TerrainPolicy) -> usize {
    hash_map_charge(&terrain.regions)
        .saturating_add(hash_map_charge(&terrain.surfaces))
        .saturating_add(terrain.authority.capacity())
        .saturating_add(512)
}

pub async fn terrain_policy(
    ctx: &Context,
    map_id: i64,
    instance_id: i64,
) -> Result<Arc<TerrainPolicy>> {
    // Establish this Catalog's pins before consulting process-global derived data.
    // Source-only contexts are never evidence for shared cache reuse.
    ctx.catalog.ensure_authority().await?;
    let key = spatial_cache_key(
        ctx.catalog.revision(),
        ctx.catalog.compiled_generation(),
        map_id,
    )
    .map(|key| (key, instance_id == 0));
    let cache = TERRAINS.get_or_init(Default::default);
    if let Some(key) = &key {
        let mut cache = cache.lock().unwrap_or_else(|error| error.into_inner());
        if let Some(index) = cache.entries.iter().position(|entry| &entry.0 == key) {
            let entry = cache.entries.remove(index).unwrap();
            let result = Arc::clone(&entry.1);
            cache.entries.push_back(entry);
            return Ok(result);
        }
    }
    let territories = ctx
        .catalog
        .document_bytes("territory-map-cells.json")
        .await?;
    let ecology = ctx.catalog.document_bytes("ecology-regions.json").await?;
    let name = format!("planting-maps/{map_id}.json");
    let surfaces = if ctx.catalog.document_exists(&name).await? {
        Some(ctx.catalog.document_bytes(&name).await?)
    } else {
        None
    };
    let mut policy = terrain_bytes(
        &territories,
        &ecology,
        surfaces.as_deref(),
        map_id,
        instance_id,
        ctx.catalog.revision(),
    )?;
    // Homing fields use the same sealed identity. An unsealed policy supplies
    // no process-global cache certificate, even if a caller reuses its revision.
    policy.authority = ctx
        .catalog
        .compiled_generation()
        .map(|generation| format!("{}:{generation}:{map_id}", ctx.catalog.revision()))
        .unwrap_or_default();
    let value = Arc::new(policy);
    if let Some(key) = key {
        let charge = terrain_charge(&value).saturating_add(spatial_key_charge(&key.0));
        if charge > TERRAIN_CACHE_BYTES {
            return Ok(value);
        }
        let mut cache = cache.lock().unwrap_or_else(|error| error.into_inner());
        if let Some(index) = cache.entries.iter().position(|entry| entry.0 == key) {
            let entry = cache.entries.remove(index).unwrap();
            let result = Arc::clone(&entry.1);
            cache.entries.push_back(entry);
            return Ok(result);
        }
        while cache.bytes + charge > TERRAIN_CACHE_BYTES {
            if let Some(entry) = cache.entries.pop_front() {
                cache.bytes -= entry.2;
            } else {
                break;
            }
        }
        cache.bytes += charge;
        cache.entries.push_back((key, Arc::clone(&value), charge));
    }
    Ok(value)
}

const GEOMETRY_CACHE_BYTES: usize = 64 * 1024 * 1024;
#[derive(Default)]
struct GeometryCache {
    entries: VecDeque<(SpatialCacheKey, Arc<Geometry>, usize)>,
    bytes: usize,
}
static GEOMETRIES: OnceLock<Mutex<GeometryCache>> = OnceLock::new();

fn geometry_charge(geometry: &Geometry) -> usize {
    let buckets = geometry.adjacent.capacity().saturating_mul(8).div_ceil(7);
    geometry
        .cells
        .capacity()
        .saturating_mul(std::mem::size_of::<Point>())
        .saturating_add(buckets.saturating_mul(std::mem::size_of::<(Point, Vec<Point>)>() + 1))
        .saturating_add(
            geometry
                .adjacent
                .values()
                .map(|values| values.capacity() * std::mem::size_of::<Point>())
                .sum::<usize>(),
        )
        .saturating_add(512)
}

pub async fn load_geometry(ctx: &Context, map_id: i64) -> Result<Arc<Geometry>> {
    let map = i32::try_from(map_id)?;
    ensure!(map > 0, "Invalid native map geometry identity");
    ctx.catalog.ensure_authority().await?;
    let key = spatial_cache_key(
        ctx.catalog.revision(),
        ctx.catalog.compiled_generation(),
        map_id,
    );
    let cache = GEOMETRIES.get_or_init(Default::default);
    if let Some(key) = &key {
        let mut cache = cache.lock().unwrap_or_else(|error| error.into_inner());
        if let Some(index) = cache.entries.iter().position(|entry| &entry.0 == key) {
            let entry = cache.entries.remove(index).unwrap();
            let result = Arc::clone(&entry.1);
            cache.entries.push_back(entry);
            return Ok(result);
        }
    }
    let value = if map == 2_000_000_000 {
        // Preserve the explicit interior template and native namespace collision fence.
        geometry(&ctx.catalog.map_geometry(map).await?)?
    } else {
        let raw = ctx
            .catalog
            .document_bytes(&format!("combat-maps/{map}.json"))
            .await?;
        geometry_bytes(&raw, map)?
    };
    let value = Arc::new(value);
    if let Some(key) = key {
        let charge = geometry_charge(&value).saturating_add(spatial_key_charge(&key));
        if charge > GEOMETRY_CACHE_BYTES {
            return Ok(value);
        }
        let mut cache = cache.lock().unwrap_or_else(|error| error.into_inner());
        if let Some(index) = cache.entries.iter().position(|entry| entry.0 == key) {
            let entry = cache.entries.remove(index).unwrap();
            let result = Arc::clone(&entry.1);
            cache.entries.push_back(entry);
            return Ok(result);
        }
        while cache.bytes + charge > GEOMETRY_CACHE_BYTES {
            if let Some(entry) = cache.entries.pop_front() {
                cache.bytes -= entry.2;
            } else {
                break;
            }
        }
        cache.bytes += charge;
        cache.entries.push_back((key, Arc::clone(&value), charge));
    }
    Ok(value)
}

pub async fn physical_radius(ctx: &Context, reference: i64) -> Result<i64> {
    let profile = ctx
        .catalog
        .document_record(
            "native-actor-characteristics.json",
            "npc_profiles",
            &json!(reference.to_string()),
        )
        .await?;
    let radius = integer(&profile, "physical_radius")?;
    ensure!(
        (-128..=127).contains(&radius),
        "Missing native monster physical radius"
    );
    Ok(radius)
}
pub async fn region_for_point(ctx: &Context, map_id: i64, p: Point) -> Result<i64> {
    terrain_policy(ctx, map_id, 0).await?.region(p)
}
pub async fn home_allowed(
    ctx: &Context,
    map_id: i64,
    home: Option<i64>,
    p: Point,
    radii: &[i64],
) -> Result<bool> {
    if home.is_none() {
        return Ok(true);
    }
    Ok(terrain_policy(ctx, map_id, 0)
        .await?
        .home_allowed(home, p, radii))
}

#[derive(Clone)]
struct Home {
    region: i64,
    kind: String,
    key: String,
    anchor: Option<Point>,
    existing: bool,
}

fn source(
    sources: &mut HashMap<i64, Home>,
    durable: &HashMap<i64, Value>,
    gid: i64,
    region: i64,
    kind: &str,
    key: String,
    anchor: Option<Point>,
) {
    if durable.contains_key(&gid) && region > 0 {
        sources.entry(gid).or_insert(Home {
            region,
            kind: kind.to_owned(),
            key,
            anchor,
            existing: false,
        });
    }
}
pub async fn ensure_homes(
    ctx: &Context,
    scope: [i64; 2],
    groups: &[Value],
) -> Result<HashMap<i64, i64>> {
    let mut seen = HashSet::new();
    let requested: Vec<i64> = groups
        .iter()
        .filter(|g| {
            g["members"]
                .as_array()
                .map(|m| !m.is_empty())
                .unwrap_or(false)
        })
        .map(group_id)
        .collect::<Result<Vec<_>>>()?
        .into_iter()
        .filter(|id| seen.insert(*id))
        .collect();
    if scope[1] != 0 || requested.is_empty() {
        return Ok(HashMap::new());
    }
    let map = i32::try_from(scope[0])?;
    let client = ctx.db.get().await?;
    let existing=client.query("SELECT group_id,region_id FROM monster_group_birth_homes WHERE map_id=$1 AND instance_id=$2",&[&map,&scope[1]]).await?;
    let mut homes: HashMap<i64, Home> = existing
        .into_iter()
        .map(|r| {
            (
                r.get("group_id"),
                Home {
                    region: r.get::<_, i32>("region_id") as i64,
                    kind: String::new(),
                    key: String::new(),
                    anchor: None,
                    existing: true,
                },
            )
        })
        .collect();
    if requested.iter().all(|id| homes.contains_key(id)) {
        return Ok(requested.iter().map(|id| (*id, homes[id].region)).collect());
    }
    let durable:HashMap<i64,Value>=client.query("SELECT to_jsonb(g) FROM (SELECT group_id,members,status FROM combat_groups WHERE map_id=$1 AND instance_id=$2) g",&[&map,&scope[1]]).await?.into_iter().map(|r|{let v:Value=r.get(0);Ok((integer(&v,"group_id")?,v))}).collect::<Result<_>>()?;
    let initial:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT region_id,group_id,initial_members FROM monster_initial_population WHERE map_id=$1 AND instance_id=$2) g",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    let planted:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT operation_id AS source_key,resource,group_payload FROM planting_receipts WHERE group_payload IS NOT NULL AND (resource->>'map_id')::int=$1 AND (resource->>'instance_id')::bigint=$2 UNION ALL SELECT resource_uid::text,resource,group_payload FROM planting_growth_outbox WHERE group_payload IS NOT NULL AND (resource->>'map_id')::int=$1 AND (resource->>'instance_id')::bigint=$2) g",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    let births:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT monster_id,cycle,parent_group_id,child_group_id,child FROM monster_reproduction_receipts WHERE map_id=$1 AND instance_id=$2 AND child_id IS NOT NULL AND child_group_id<>parent_group_id) g",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    let arches:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT group_id,region_id,spawn_id FROM archmonster_spawn_births WHERE map_id=$1 AND world_instance_id=$2) g",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    let environmental:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT g.group_id,e.region_id,g.instance_id,g.group_ordinal FROM environmental_owned_groups g JOIN environmental_event_instances e ON e.instance_id=g.instance_id WHERE g.map_id=$1 AND g.world_instance_id=$2 AND e.region_id IS NOT NULL) g",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    let genesis:Vec<Value>=client.query("SELECT to_jsonb(g) FROM (SELECT id,outcome FROM ecology_admin_operations WHERE command IN ('!genesis','!genesis-all') AND outcome->'created_groups' IS NOT NULL) g",&[]).await?.into_iter().map(|r|r.get(0)).collect();
    drop(client);
    let terrain = terrain_policy(ctx, scope[0], scope[1]).await?;
    let mut sources = HashMap::new();
    let mut reproduction = HashMap::new();
    for row in initial {
        if let Some(first) = row["initial_members"].as_array().and_then(|v| v.first()) {
            let region = integer(&row, "region_id")?;
            source(
                &mut sources,
                &durable,
                integer(&row, "group_id")?,
                region,
                "initial_population",
                region.to_string(),
                Some(point(first)?),
            );
        }
    }
    for row in planted {
        let payload = &row["group_payload"];
        if payload["key"].get(0).and_then(Value::as_i64) != Some(scope[0])
            || payload["key"].get(1).and_then(Value::as_i64) != Some(scope[1])
        {
            continue;
        }
        let p = point(&row["resource"])?;
        source(
            &mut sources,
            &durable,
            payload["key"][2]
                .as_i64()
                .ok_or_else(|| anyhow!("Invalid planted group identity"))?,
            terrain.region(p)?,
            "planting",
            row["source_key"]
                .as_str()
                .map(str::to_owned)
                .unwrap_or_else(|| row["source_key"].to_string()),
            Some(p),
        );
    }
    for row in arches {
        source(
            &mut sources,
            &durable,
            integer(&row, "group_id")?,
            integer(&row, "region_id")?,
            "archmonster_birth",
            row["spawn_id"]
                .as_str()
                .map(str::to_owned)
                .unwrap_or_else(|| row["spawn_id"].to_string()),
            None,
        );
    }
    for row in environmental {
        source(
            &mut sources,
            &durable,
            integer(&row, "group_id")?,
            integer(&row, "region_id")?,
            "environmental_birth",
            format!(
                "{}:{}",
                row["instance_id"]
                    .as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| row["instance_id"].to_string()),
                integer(&row, "group_ordinal")?
            ),
            None,
        );
    }
    for row in genesis {
        let outcome = &row["outcome"];
        let valid: HashSet<_> = outcome["scopes"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|s| {
                let a = s.as_array()?;
                if a.len() != 3
                    || a[0].as_i64() != Some(scope[0])
                    || a[1].as_i64() != Some(scope[1])
                {
                    return None;
                }
                Some([scope[0], scope[1], a[2].as_i64()?])
            })
            .collect();
        if valid.len() != 1 {
            continue;
        }
        let region = valid.iter().next().unwrap()[2];
        for group in outcome["created_groups"].as_array().into_iter().flatten() {
            if group["key"][0].as_i64() == Some(scope[0])
                && group["key"][1].as_i64() == Some(scope[1])
            {
                source(
                    &mut sources,
                    &durable,
                    group["key"][2]
                        .as_i64()
                        .ok_or_else(|| anyhow!("Invalid genesis group"))?,
                    region,
                    "genesis_scope",
                    row["id"]
                        .as_str()
                        .map(str::to_owned)
                        .unwrap_or_else(|| row["id"].to_string()),
                    None,
                );
            }
        }
    }
    for row in births {
        reproduction
            .entry(integer(&row, "child_group_id")?)
            .or_insert(row);
    }
    fn resolve(
        gid: i64,
        ancestor: bool,
        homes: &mut HashMap<i64, Home>,
        sources: &HashMap<i64, Home>,
        reproduction: &HashMap<i64, Value>,
        durable: &HashMap<i64, Value>,
        resolving: &mut HashSet<i64>,
        terrain: &TerrainPolicy,
    ) -> Result<Option<Home>> {
        if let Some(home) = homes.get(&gid) {
            return Ok(Some(home.clone()));
        }
        if resolving.contains(&gid) || !durable.contains_key(&gid) {
            return Ok(None);
        }
        resolving.insert(gid);
        let mut resolved = sources.get(&gid).cloned();
        if resolved.is_none() {
            if let Some(birth) = reproduction.get(&gid) {
                let parent = resolve(
                    integer(birth, "parent_group_id")?,
                    true,
                    homes,
                    sources,
                    reproduction,
                    durable,
                    resolving,
                    terrain,
                )?;
                let anchor = point(&birth["child"])?;
                resolved = Some(if let Some(parent) = parent {
                    Home {
                        region: parent.region,
                        kind: "reproduction_parent".to_owned(),
                        key: integer(birth, "parent_group_id")?.to_string(),
                        anchor: Some(anchor),
                        existing: false,
                    }
                } else {
                    Home {
                        region: terrain.region(anchor)?,
                        kind: "reproduction_birth".to_owned(),
                        key: format!(
                            "{}:{}",
                            integer(birth, "monster_id")?,
                            integer(birth, "cycle")?
                        ),
                        anchor: Some(anchor),
                        existing: false,
                    }
                });
            }
        }
        if resolved.is_none() && !ancestor {
            if let Some(member) = durable[&gid]["members"].as_array().and_then(|m| m.first()) {
                let anchor = point(member)?;
                let region = terrain.region(anchor)?;
                eprintln!("Pinned legacy monster home from current position, not historical birth proof: map group={gid} region={region}");
                resolved = Some(Home {
                    region,
                    kind: "legacy_current_fallback".to_owned(),
                    key: "first_ecology_observation".to_owned(),
                    anchor: Some(anchor),
                    existing: false,
                });
            }
        }
        resolving.remove(&gid);
        if let Some(home) = &resolved {
            homes.insert(gid, home.clone());
        }
        Ok(resolved)
    }
    for gid in &requested {
        resolve(
            *gid,
            false,
            &mut homes,
            &sources,
            &reproduction,
            &durable,
            &mut HashSet::new(),
            &terrain,
        )?;
    }
    let mut client = ctx.db.get().await?;
    let transaction = client.transaction().await?;
    for (gid, home) in homes
        .iter()
        .filter(|(gid, h)| !h.existing && durable.contains_key(gid))
    {
        let region = i32::try_from(home.region)?;
        let anchor = home.anchor.map(|p| json!(p));
        transaction.execute("INSERT INTO monster_group_birth_homes(map_id,instance_id,group_id,region_id,source_kind,source_key,anchor) VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING",&[&map,&scope[1],gid,&region,&home.kind,&home.key,&anchor]).await?;
    }
    let ids: Vec<i64> = requested.into_iter().collect();
    let rows=transaction.query("SELECT group_id,region_id FROM monster_group_birth_homes WHERE map_id=$1 AND instance_id=$2 AND group_id=ANY($3)",&[&map,&scope[1],&ids]).await?;
    let result = rows
        .into_iter()
        .map(|r| (r.get::<_, i64>(0), r.get::<_, i32>(1) as i64))
        .collect();
    transaction.commit().await?;
    Ok(result)
}

pub async fn birth_destinations(
    ctx: &Context,
    scope: [i64; 2],
    parent: &Value,
    groups: &[Value],
    players: &[Value],
    home: Option<i64>,
    child_reference: i64,
) -> Result<Vec<Point>> {
    let indexed = load_geometry(ctx, scope[0]).await?;
    let terrain = terrain_policy(ctx, scope[0], scope[1]).await?;
    let radius = physical_radius(ctx, child_reference).await?;
    let client = ctx.db.get().await?;
    let map = i32::try_from(scope[0])?;
    let mut blocked: HashSet<[i64; 2]> = client
        .query(
            "SELECT x,y FROM planted_resources WHERE map_id=$1 AND instance_id=$2",
            &[&map, &scope[1]],
        )
        .await?
        .into_iter()
        .map(|row| [row.get::<_, i32>(0) as i64, row.get::<_, i32>(1) as i64])
        .collect();
    drop(client);
    for player in players {
        let p = point(player)?;
        blocked.insert([p[0], p[1]]);
    }
    for group in groups.iter().filter(|g| living(g)) {
        for member in members(group)? {
            let p = point(member)?;
            blocked.insert([p[0], p[1]]);
        }
    }
    eligible_birth_cells(&indexed, &terrain, point(parent)?, &blocked, home, radius)
}











struct WanderBatch<'a> {
    epoch: &'a str,
    scope: [i64; 2],
    configuration: &'a Value,
    moves: Vec<Value>,
    moved_members: usize,
    packet_bytes: usize,
}
impl<'a> WanderBatch<'a> {
    fn new(epoch: &'a str, scope: [i64; 2], configuration: &'a Value) -> Self {
        Self {
            epoch,
            scope,
            configuration,
            moves: Vec::new(),
            moved_members: 0,
            packet_bytes: 0,
        }
    }
    fn payload(&self) -> Value {
        json!({"kind":"wander_bulk","world_epoch":self.epoch,"scope":self.scope,"configuration":self.configuration,"moves":self.moves})
    }
    fn append(&mut self, group_id: i64, roster: &[Value], plan: &MovePlan) -> Result<bool> {
        if self.moves.len() >= 8 || plan.packets.is_empty() {
            return Ok(false);
        }
        let changed = roster
            .iter()
            .zip(&plan.members)
            .filter(|(a, b)| point(a).ok() != point(b).ok())
            .count();
        let bytes: usize = plan
            .packets
            .iter()
            .map(|packet| {
                packet[1]
                    .as_str()
                    .map(|s| s.len() / 2 + 6)
                    .unwrap_or(usize::MAX)
            })
            .sum();
        if self.moved_members + changed > 40 || self.packet_bytes + bytes > 64 * 1024 {
            return Ok(false);
        }
        let mut row = json!({"group_id":group_id,"expected_members":roster,"moved_members":plan.members,"packets":plan.packets});
        if plan.dispersal {
            row["dispersal"] = json!(true);
        }
        if plan.overlap_escape {
            row["overlap_escape"] = json!(true);
        }
        self.moves.push(row);
        if crate::protocol::canonical_bytes(&self.payload())?.len() > 224 * 1024 {
            self.moves.pop();
            return Ok(false);
        }
        self.moved_members += changed;
        self.packet_bytes += bytes;
        Ok(true)
    }
}

pub async fn prepare_scope_wander(
    ctx: &Context,
    snapshot: &Value,
    scope: [i64; 2],
    groups: &[Value],
    configuration: &Value,
    homes: &HashMap<i64, i64>,
) -> Result<Option<Value>> {
    let radius = integer(configuration, "radius")?;
    let min_steps = usize::try_from(integer(configuration, "min_steps")?)?;
    let max_steps = usize::try_from(integer(configuration, "max_steps")?)?;
    let probability = configuration["move_probability"]
        .as_f64()
        .ok_or_else(|| anyhow!("Invalid movement probability"))?;
    ensure!(
        (1..=1000).contains(&radius)
            && min_steps >= 1
            && min_steps <= max_steps
            && max_steps <= 255
            && (0.0..=1.0).contains(&probability),
        "Invalid monster wander policy"
    );
    let epoch = snapshot["world_epoch"]
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow!("Missing ecology epoch"))?;
    let players: Vec<Point> = snapshot["players"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing ecology players"))?
        .iter()
        .filter(|p| {
            p.get("_ecology_active") != Some(&Value::Bool(false))
                && p["map_id"].as_i64() == Some(scope[0])
                && p.get("instance_id").and_then(Value::as_i64).unwrap_or(0) == scope[1]
        })
        .map(point)
        .collect::<Result<_>>()?;
    if players.is_empty() {
        return Ok(None);
    }
    let excluded: HashSet<i64> = snapshot["excluded_ids"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing excluded actors"))?
        .iter()
        .map(|v| v.as_i64().ok_or_else(|| anyhow!("Invalid excluded actor")))
        .collect::<Result<_>>()?;
    let live: Vec<Value> = groups.iter().filter(|g| living(g)).cloned().collect();
    let tick = snapshot["domain_planning_tick"].as_u64().unwrap_or(0);
    let mut visible = visible_groups(groups, &players, radius, tick)?;
    if visible.is_empty() {
        return Ok(None);
    }
    let (mut scope_occupied, overlapping) = scope_occupancy(&live, &players)?;
    visible.sort_by_key(|g| !overlapping.contains(&group_id(g).unwrap_or(i64::MIN)));
    let indexed = load_geometry(ctx, scope[0]).await?;
    let terrain = terrain_policy(ctx, scope[0], scope[1]).await?;
    let allow = snapshot
        .get("allow_wander")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let mut batch = WanderBatch::new(epoch, scope, configuration);
    let deadline = Instant::now() + Duration::from_millis(25);
    for group in visible {
        if Instant::now() >= deadline {
            break;
        }
        let roster = members(group)?;
        let _identities = roster
            .iter()
            .map(|m| integer(m, "id"))
            .collect::<Result<Vec<_>>>()?;
        if !autonomous_roster(roster, &excluded)?
            || batch.moved_members + roster.len() > 40
        {
            continue;
        }
        let gid = group_id(group)?;
        let overlap = overlapping.contains(&gid);
        if !wander_admitted(overlap, allow, probability, rand::random::<f64>) {
            continue;
        }
        let own: HashSet<_> = member_points(roster)?.into_iter().collect();
        let occupied: HashSet<_> = scope_occupied.difference(&own).copied().collect();
        let home = homes.get(&gid).copied();
        let mut radii = Vec::new();
        for reference in roster
            .iter()
            .map(|m| integer(m, "ref"))
            .collect::<Result<BTreeSet<_>>>()?
        {
            radii.push(physical_radius(ctx, reference).await?);
        }
        radii.sort();
        radii.dedup();
        let inside = |p| terrain.home_allowed(home, p, &radii);
        let habitat = |p| terrain.habitat(p);
        let allowed = |p| habitat(p) && inside(p);
        let result = {
            let mut rng = rand::rng();
            if let Some(home) = home.filter(|_| {
                roster
                    .iter()
                    .any(|m| point(m).map(|p| !inside(p)).unwrap_or(true))
            }) {
                homing_path(
                    roster,
                    &players,
                    &indexed,
                    &occupied,
                    radius,
                    min_steps,
                    max_steps,
                    &terrain.authority,
                    home,
                    &radii,
                    &inside,
                    &habitat,
                    &mut rng,
                )?
            } else {
                group_path(
                    roster, &players, &live, &indexed, &occupied, radius, min_steps, max_steps,
                    &allowed, &mut rng,
                )?
            }
        };
        let Some(plan) = result else { continue };
        if !batch.append(gid, roster, &plan)? {
            continue;
        }
        scope_occupied.retain(|p| !own.contains(p));
        for member in batch.moves.last().unwrap()["moved_members"]
            .as_array()
            .unwrap()
        {
            scope_occupied.insert(point(member)?);
        }
        if batch.moves.len() >= 8 {
            break;
        }
    }
    if batch.moves.is_empty() {
        Ok(None)
    } else {
        Ok(Some(batch.payload()))
    }
}



async fn movement_allowed(ctx: &Context, scope: [i64; 2], movement: &Value) -> Result<bool> {
    let (gid, expected, moved, paths) = validate_move(movement)?;
    let terrain = terrain_policy(ctx, scope[0], scope[1]).await?;
    if scope[1] != 0 || !terrain.tracked() {
        return Ok(true);
    }
    let group = json!({"group_id":gid,"members":expected});
    let homes = ensure_homes(ctx, scope, &[group]).await?;
    let Some(home) = homes.get(&gid).copied() else {
        return Ok(false);
    };
    let indexed = load_geometry(ctx, scope[0]).await?;
    let mut radii = Vec::new();
    for m in &expected {
        let r = physical_radius(ctx, integer(m, "ref")?).await?;
        if !radii.contains(&r) {
            radii.push(r);
        }
    }
    radii.sort();
    radii.dedup();
    queued_movement_allowed(&indexed, &terrain, home, &radii, &expected, &moved, &paths)
}

// The async wrapper loads immutable authority; this kernel checks every actual
// native path step without doing database or catalog I/O.

async fn reproduction_allowed(ctx: &Context, proposal: &Value) -> Result<bool> {
    let scope = proposal_scope(proposal)?;
    let terrain = terrain_policy(ctx, scope[0], scope[1]).await?;
    if scope[1] != 0 || !terrain.tracked() {
        return Ok(true);
    }
    let expected = proposal["expected_members"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing reproduction roster"))?;
    let gid = integer(&proposal["ticket"], "group_id")?;
    let homes = ensure_homes(ctx, scope, &[json!({"group_id":gid,"members":expected})]).await?;
    let Some(home) = homes.get(&gid).copied() else {
        return Ok(false);
    };
    let destination = array_point(&proposal["destination"])?;
    let radius = if let Some(child) = proposal.get("child").filter(|c| !c.is_null()) {
        if point(child)? != destination {
            return Ok(false);
        }
        physical_radius(ctx, integer(child, "ref")?).await?
    } else {
        0
    };
    queued_reproduction_allowed(
        &terrain,
        home,
        destination,
        proposal.get("child").filter(|child| !child.is_null()),
        radius,
    )
}


async fn validate_inner(ctx: &Context, row: &Value) -> Result<bool> {
    if row["domain"].as_str() != Some("mobs") {
        return Ok(true);
    }
    let proposal = &row["payload"];
    match proposal["kind"].as_str() {
        Some("wander_bulk") => {
            let scope = proposal_scope(proposal)?;
            for movement in proposal["moves"]
                .as_array()
                .ok_or_else(|| anyhow!("Missing wander moves"))?
            {
                if !movement_allowed(ctx, scope, movement).await? {
                    return Ok(false);
                }
            }
            Ok(true)
        }
        Some("wander") => {
            let mut move_row = serde_json::Map::new();
            for key in ["group_id", "expected_members", "moved_members", "packets"] {
                move_row.insert(
                    key.to_owned(),
                    proposal
                        .get(key)
                        .ok_or_else(|| anyhow!("Missing wander field"))?
                        .clone(),
                );
            }
            movement_allowed(ctx, proposal_scope(proposal)?, &Value::Object(move_row)).await
        }
        Some("reproduction") => reproduction_allowed(ctx, proposal).await,
        Some("lifecycle_bulk") => {
            for operation in proposal["operations"]
                .as_array()
                .ok_or_else(|| anyhow!("Missing lifecycle operations"))?
            {
                if operation["kind"].as_str() == Some("reproduction")
                    && !reproduction_allowed(ctx, operation).await?
                {
                    return Ok(false);
                }
            }
            Ok(true)
        }
        _ => Ok(true),
    }
}
pub async fn validate_proposal(ctx: &Context, row: &Value) -> Result<bool> {
    match validate_inner(ctx, row).await {
        Ok(valid) => Ok(valid),
        Err(error) => {
            if error
                .chain()
                .any(|e| e.is::<tokio_postgres::Error>() || e.is::<deadpool_postgres::PoolError>())
            {
                Err(error)
            } else {
                Ok(false)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{rngs::StdRng, SeedableRng};

    fn actor(id: i64, point: Point) -> Value {
        json!({"id":id,"ref":5525,"x":point[0],"y":point[1],"z":point[2],"level":1})
    }
    fn graph(cells: &[Point], edges: &[(Point, Point)]) -> Geometry {
        geometry(&json!({"cells":cells,"edges":edges})).unwrap()
    }

    #[test]
    fn native_direction_height_and_wire_header_match_client_layout() {
        let packet = movement_packet(-7, &[[-5, 7, -1], [-4, 6, 14]]).unwrap();
        assert_eq!(
            hex::encode(packet),
            "fffffffffffffff9fffffffb00000007ffff010f"
        );
        for (direction, delta) in DIRECTIONS.iter().enumerate() {
            let packet = movement_packet(-1, &[[0, 0, 0], [delta[0], delta[1], 0]]).unwrap();
            assert_eq!(packet[19], (direction as u8) << 5);
        }
        assert_eq!(
            movement_packet(-1, &[[1, 2, 3], [1, 1, -13]]).unwrap()[19],
            0xf0
        );
        assert!(movement_packet(1, &[[0, 0, 0], [1, 0, 0]]).is_err());
        assert!(movement_packet(-1, &[[0, 0, 0], [2, 0, 0]]).is_err());
        assert!(movement_packet(-1, &[[0, 0, 0], [1, 0, 16]]).is_err());
        assert!(!native_step(-1, [0, 0, 0], [0, 0, 0]));
    }

    #[test]
    fn ordinary_path_moves_the_whole_roster_on_actual_directed_edges() {
        let cells = [
            [0, 0, 0],
            [1, 0, 0],
            [2, 0, 0],
            [0, 1, 0],
            [1, 1, 0],
            [2, 1, 0],
        ];
        let indexed = graph(
            &cells,
            &[
                (cells[0], cells[1]),
                (cells[1], cells[2]),
                (cells[3], cells[4]),
                (cells[4], cells[5]),
            ],
        );
        let roster = [actor(-1, cells[0]), actor(-2, cells[3])];
        let result = ordinary_path(
            &roster,
            &[[10, 10, 0]],
            &indexed,
            &HashSet::new(),
            20,
            2,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1),
        )
        .unwrap()
        .unwrap();
        assert_eq!(point(&result.members[0]).unwrap(), cells[2]);
        assert_eq!(point(&result.members[1]).unwrap(), cells[5]);
        assert_eq!(result.members[0]["level"], 1);
        assert_eq!(result.packets.len(), 2);
        for packet in result.packets {
            let (_, _, path) = decode_packet(&packet).unwrap();
            assert_eq!(path.len(), 2);
        }
    }

    #[test]
    fn overlap_escape_matches_distinct_endpoints_without_teleporting() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let c = [0, 1, 0];
        let indexed = graph(&[a, b, c], &[(a, b), (a, c)]);
        let roster = vec![actor(-1, a), actor(-2, a)];
        let groups = [json!({"status":"available","members":roster})];
        let result = group_path(
            &roster,
            &[a],
            &groups,
            &indexed,
            &HashSet::new(),
            20,
            1,
            3,
            &|_| true,
            &mut StdRng::seed_from_u64(2),
        )
        .unwrap()
        .unwrap();
        assert!(result.overlap_escape);
        assert!(!result.dispersal);
        let endpoints: HashSet<_> = member_points(&result.members)
            .unwrap()
            .into_iter()
            .collect();
        assert_eq!(endpoints, HashSet::from([b, c]));
        assert_eq!(result.packets.len(), 2);
    }

    #[test]
    fn homing_strictly_decreases_directed_home_distance_and_respects_actors() {
        let cells = [[0, 0, 0], [1, 0, 0], [2, 0, 0]];
        let indexed = graph(&cells, &[(cells[0], cells[1]), (cells[1], cells[2])]);
        let inside = |p: Point| p == cells[2];
        let roster = [actor(-1, cells[0])];
        let result = homing_path(
            &roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            1,
            1,
            "fixture-home-forward",
            7,
            &[0],
            &inside,
            &|_| true,
            &mut StdRng::seed_from_u64(3),
        )
        .unwrap()
        .unwrap();
        assert_eq!(point(&result.members[0]).unwrap(), cells[1]);
        assert!(homing_path(
            &roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::from([cells[1]]),
            20,
            1,
            1,
            "fixture-home-forward",
            7,
            &[0],
            &inside,
            &|_| true,
            &mut StdRng::seed_from_u64(3)
        )
        .unwrap()
        .is_none());
        let reversed_home = |p: Point| p == cells[0];
        assert!(homing_path(
            &[actor(-1, cells[2])],
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            1,
            1,
            "fixture-home-unreachable",
            7,
            &[0],
            &reversed_home,
            &|_| true,
            &mut StdRng::seed_from_u64(3)
        )
        .unwrap()
        .is_none());
        assert!(distance_field_cache_bytes() <= FIELD_CACHE_BYTES);
    }

    #[test]
    fn terrain_uses_negative_floor_grid_exact_height_and_physical_footprints() {
        let policy = TerrainPolicy {
            regions: HashMap::from([([0, 0], 1), ([-1, 0], 2)]),
            surfaces: HashMap::from([([0, 0, 0], 1), ([-1, 0, 0], 2), ([3, 0, 0], -1)]),
            has_map: true,
            outdoor: true,
            authority: "fixture-territory".to_owned(),
        };
        assert_eq!(policy.region([-1, 0, 0]).unwrap(), 2);
        assert!(policy.home_allowed(Some(1), [0, 0, 0], &[0]));
        assert!(!policy.home_allowed(Some(1), [0, 0, 0], &[1]));
        assert!(policy.habitat([0, 0, 0]));
        assert!(!policy.habitat([0, 0, 1]));
        assert!(policy.certified_unassigned([3, 0, 0]));
        assert!(policy.region([3, 0, 0]).is_err());
        assert_eq!(footprint([5, 5, -1], -1).unwrap(), vec![[5, 5, -1]]);
        assert_eq!(footprint([5, 5, -1], 1).unwrap().len(), 9);
        assert!(footprint([0, 0, 0], 128).is_err());
    }

    #[test]
    fn queued_movement_bytes_must_match_roster_and_have_complete_actor_coverage() {
        let before = actor(-1, [0, 0, 0]);
        let after = actor(-1, [1, 0, 0]);
        let packet = json!([
            13852,
            hex::encode(movement_packet(-1, &[[0, 0, 0], [1, 0, 0]]).unwrap())
        ]);
        let mut movement = json!({"group_id":1,"expected_members":[before],"moved_members":[after],"packets":[packet]});
        assert!(validate_move(&movement).is_ok());
        movement["moved_members"][0]["x"] = json!(2);
        assert!(validate_move(&movement).is_err());
        movement["moved_members"][0]["x"] = json!(1);
        movement["dispersal"] = json!(true);
        movement["overlap_escape"] = json!(true);
        assert!(validate_move(&movement).is_err());
        let mut packet = movement["packets"][0].clone();
        packet[1] = json!("00");
        assert!(decode_packet(&packet).is_err());
    }

    #[test]
    fn geometry_never_invents_unexported_or_reverse_edges() {
        let indexed = graph(&[[0, 0, 0], [1, 0, 0]], &[([0, 0, 0], [1, 0, 0])]);
        assert!(indexed.edges.contains(&([0, 0, 0], [1, 0, 0])));
        assert!(!indexed.edges.contains(&([1, 0, 0], [0, 0, 0])));
        assert!(geometry(&json!({"cells":[[0,0,0]],"edges":[[[0,0,0],[1,0,0]]]})).is_err());
        assert!(array_point(&json!([i64::MAX, 0, 0])).is_err());
    }

    #[test]
    fn shared_spatial_cache_requires_a_sealed_generation_and_exact_source() {
        assert!(spatial_cache_key("source", None, 1134).is_none());
        let key = spatial_cache_key("source", Some("generation-a"), 1134).unwrap();
        assert_ne!(
            Some(key.clone()),
            spatial_cache_key("source", Some("generation-b"), 1134)
        );
        assert_ne!(
            Some(key.clone()),
            spatial_cache_key("other-source", Some("generation-a"), 1134)
        );
        assert_ne!(
            Some(key),
            spatial_cache_key("source", Some("generation-a"), 1135)
        );
    }

    #[test]
    fn typed_geometry_matches_value_rules_and_shares_its_edge_index() {
        let data = json!({"map_id":1134,"cells":[[0,0,0],[1,0,0],[1,0,0],[0,1,-1]],"edges":[[[0,0,0],[1,0,0]],[[0,0,0],[1,0,0]],[[1,0,0],[0,1,-1]]],"ignored_metadata":{"opaque":"native source metadata"}});
        let raw = serde_json::to_vec(&data).unwrap();
        let typed = geometry_bytes(&raw, 1134).unwrap();
        let old = geometry(&data).unwrap();
        assert_eq!(typed.cells, old.cells);
        assert_eq!(typed.digest, old.digest);
        assert_eq!(typed.adjacent.as_ref(), old.adjacent.as_ref());
        assert!(Arc::ptr_eq(&typed.adjacent, &typed.edges.adjacent));
        assert!(typed.edges.contains(&([0, 0, 0], [1, 0, 0])));
        assert!(!typed.edges.contains(&([1, 0, 0], [0, 0, 0])));
        assert!(geometry_bytes(&raw, 1135).is_err());
        assert!(geometry_charge(&typed) < GEOMETRY_CACHE_BYTES);
    }

    #[test]
    fn typed_terrain_preserves_first_surface_negative_grid_and_scripted_headers() {
        let territories=serde_json::to_vec(&json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":1134,"regions":[{"region_id":1,"cells":[[0,0]]},{"region_id":2,"cells":[[-1,0]]}]},{"map_id":1388,"regions":[]}]})).unwrap();
        let ecology = serde_json::to_vec(
            &json!([{"map_id":1134,"regions":[{"region_id":1}]},{"map_id":1388,"regions":[]}]),
        )
        .unwrap();
        let surfaces =
            serde_json::to_vec(&json!({"cells":[[0,0,0,0,0,1],[0,0,0,0,0,2],[-1,0,0,0,0,2]]}))
                .unwrap();
        let terrain =
            terrain_bytes(&territories, &ecology, Some(&surfaces), 1134, 0, "rev").unwrap();
        assert_eq!(terrain.region([0, 0, 0]).unwrap(), 1);
        assert_eq!(terrain.region([-1, 0, 0]).unwrap(), 2);
        assert!(!terrain.habitat([4, 4, 0]));
        assert!(terrain.habitat([0, 0, 0]));
        assert!(terrain_charge(&terrain) < TERRAIN_CACHE_BYTES);
        let scripted = terrain_bytes(&territories, &ecology, None, 1388, 0, "rev").unwrap();
        assert!(scripted.habitat([4, 4, 0]));
        let private = terrain_bytes(&territories, &ecology, None, 1134, 9, "rev").unwrap();
        assert!(private.habitat([4, 4, 0]));
    }

    #[test]
    fn cyclic_native_path_never_returns_roster_to_its_start() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let indexed = graph(&[a, b], &[(a, b), (b, a)]);
        let roster = [actor(-1, a)];
        let plan = ordinary_path(
            &roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            3,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(7),
        )
        .unwrap()
        .unwrap();
        assert_eq!(point(&plan.members[0]).unwrap(), b);
        assert_eq!(decode_packet(&plan.packets[0]).unwrap().2, vec![b]);
    }

    #[test]
    fn player_other_group_and_own_overlap_escape_even_when_wandering_is_disabled() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let c = [0, 1, 0];
        let indexed = graph(&[a, b, c], &[(a, b), (a, c)]);
        for mode in 0..3 {
            let roster = if mode == 2 {
                vec![actor(-1, a), actor(-2, a)]
            } else {
                vec![actor(-1, a)]
            };
            let mut groups = vec![json!({"group_id":1,"status":"available","members":roster})];
            let players = if mode == 0 {
                vec![a]
            } else {
                vec![[10, 10, 0]]
            };
            if mode == 1 {
                groups.push(json!({"group_id":2,"status":"available","members":[actor(-3,a)]}));
            }
            let (occupied, overlapping) = scope_occupancy(&groups, &players).unwrap();
            assert!(overlapping.contains(&1));
            assert!(wander_admitted(true, false, 0.0, || panic!(
                "Overlap must not sample ordinary movement probability"
            )));
            assert!(!wander_admitted(false, false, 1.0, || panic!(
                "Disabled ordinary movement must not sample"
            )));
            assert!(!wander_admitted(false, true, 0.0, || 0.0));
            let own: HashSet<_> = member_points(&roster).unwrap().into_iter().collect();
            let blocked = occupied.difference(&own).copied().collect();
            let plan = group_path(
                &roster,
                &players,
                &groups,
                &indexed,
                &blocked,
                20,
                1,
                3,
                &|_| true,
                &mut StdRng::seed_from_u64(mode),
            )
            .unwrap()
            .unwrap();
            assert!(plan.overlap_escape);
            let external = external_cells(&roster, &players, &groups).unwrap();
            assert!(
                overlap_count(&plan.members, &external).unwrap()
                    < overlap_count(&roster, &external).unwrap()
            );
            for packet in &plan.packets {
                let (_, origin, path) = decode_packet(packet).unwrap();
                let mut p = origin;
                for d in path {
                    assert!(indexed.edges.contains(&(p, d)));
                    p = d;
                }
            }
        }
    }

    #[test]
    fn occupied_and_unexported_steps_wait_instead_of_teleporting() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let indexed = graph(&[a, b], &[(a, b)]);
        let roster = [actor(-1, a)];
        assert!(ordinary_path(
            &roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::from([b]),
            20,
            3,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
        assert!(ordinary_path(
            &[actor(-1, b)],
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            3,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
        assert_eq!(point(&roster[0]).unwrap(), a);
    }

    #[test]
    fn fighting_and_living_cells_block_but_defeated_history_does_not() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let c = [2, 0, 0];
        let d = [3, 0, 0];
        let groups = vec![
            json!({"group_id":1,"status":"available","members":[actor(-1,a)]}),
            json!({"group_id":2,"status":"fighting","members":[actor(-2,b)]}),
            json!({"group_id":3,"status":"available","members":[actor(-3,c)]}),
            json!({"group_id":4,"status":"defeated","members":[actor(-4,d)]}),
        ];
        let (occupied, overlapping) = scope_occupancy(&groups, &[]).unwrap();
        assert_eq!(occupied, HashSet::from([a, b, c]));
        assert!(overlapping.is_empty());
        let roster = members(&groups[0]).unwrap();
        let external = external_cells(roster, &[], &groups).unwrap();
        assert_eq!(external, HashSet::from([b, c]));
        let indexed = graph(&[a, b, c, d], &[(a, b), (a, d)]);
        assert!(ordinary_path(
            roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::from([b, c]),
            20,
            1,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
        // A defeated actor at a real adjacent native destination does not reserve it.
        let dead = [0, 1, 0];
        let indexed = graph(&[a, dead], &[(a, dead)]);
        assert!(ordinary_path(
            roster,
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            1,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_some());
    }

    #[test]
    fn defeated_groups_never_become_dispersion_neighbors() {
        let origin = [0, 0, 0];
        let groups = [
            json!({"status":"available","members":[actor(-1,origin)]}),
            json!({"status":"defeated","members":[actor(-2,[1,0,0])]}),
            json!({"status":"fighting","members":[actor(-3,[3,0,0])]}),
        ];
        assert_eq!(nearest_group(origin, -1, &groups).unwrap(), Some([3, 0, 0]));
        assert_eq!(nearest_group(origin, -1, &groups[..2]).unwrap(), None);
    }

    #[test]
    fn visible_group_rotation_preserves_one_position_stride_and_reaches_the_end() {
        let groups: Vec<_> = (1..=1000)
            .map(|gid| {
                let x = (gid % 50) * 10;
                let y = (gid / 50) * 10;
                let roster: Vec<_> = (0..5)
                    .map(|j| actor(-(gid * 10 + j + 1), [x, y + j, 0]))
                    .collect();
                json!({"group_id":gid,"status":"available","members":roster})
            })
            .collect();
        let ids = |tick| {
            visible_groups(&groups, &[[250, 100, 0]], 1000, tick)
                .unwrap()
                .into_iter()
                .take(8)
                .map(|g| group_id(g).unwrap())
                .collect::<Vec<_>>()
        };
        assert_eq!(ids(0), (1..=8).collect::<Vec<_>>());
        assert_eq!(ids(124), (125..=132).collect::<Vec<_>>());
        assert_eq!(ids(999), vec![1000, 1, 2, 3, 4, 5, 6, 7]);
        let twelve = &groups[..12];
        let first: Vec<_> = visible_groups(twelve, &[[250, 100, 0]], 1000, 0)
            .unwrap()
            .into_iter()
            .take(8)
            .map(|g| group_id(g).unwrap())
            .collect();
        let next: Vec<_> = visible_groups(twelve, &[[250, 100, 0]], 1000, 1)
            .unwrap()
            .into_iter()
            .take(8)
            .map(|g| group_id(g).unwrap())
            .collect();
        assert_eq!(first, (1..=8).collect::<Vec<_>>());
        assert_eq!(next, (2..=9).collect::<Vec<_>>());
    }

    #[test]
    fn native_habitat_rejection_blocks_both_birth_and_walk() {
        let a = [0, 0, 0];
        let b = [1, 0, 0];
        let indexed = graph(&[a, b], &[(a, b)]);
        let mut terrain = TerrainPolicy {
            regions: HashMap::from([([0, 0], 1)]),
            surfaces: HashMap::from([(a, 1)]),
            has_map: true,
            outdoor: true,
            authority: "fixture-habitat".to_owned(),
        };
        assert!(
            eligible_birth_cells(&indexed, &terrain, a, &HashSet::new(), None, 0)
                .unwrap()
                .is_empty()
        );
        assert!(ordinary_path(
            &[actor(-1, a)],
            &[[10, 0, 0]],
            &indexed,
            &HashSet::new(),
            20,
            1,
            &|p| terrain.habitat(p),
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
        terrain.surfaces.insert(b, 1);
        assert_eq!(
            eligible_birth_cells(&indexed, &terrain, a, &HashSet::new(), None, 0).unwrap(),
            vec![b]
        );
        assert!(
            eligible_birth_cells(&indexed, &terrain, a, &HashSet::from([[1, 0]]), None, 0)
                .unwrap()
                .is_empty()
        );
    }

    fn translated(roster: &[Value]) -> MovePlan {
        let paths: Vec<_> = roster
            .iter()
            .map(|m| {
                let p = point(m).unwrap();
                vec![p, [p[0] + 1, p[1], p[2]]]
            })
            .collect();
        path_result(roster, &paths).unwrap()
    }
    #[test]
    fn wander_batch_rejects_ninth_group_and_forty_first_member_without_partial_state() {
        let policy = json!({"move_probability":1.0,"radius":20,"min_steps":1,"max_steps":3,"interval_seconds":2.0});
        let mut batch = WanderBatch::new("epoch", [1134, 0], &policy);
        for gid in 1..=8 {
            let roster = [actor(-gid, [0, gid, 0])];
            assert!(batch.append(gid, &roster, &translated(&roster)).unwrap());
        }
        let before = batch.payload();
        let roster = [actor(-9, [0, 9, 0])];
        assert!(!batch.append(9, &roster, &translated(&roster)).unwrap());
        assert_eq!(before, batch.payload());
        assert_eq!(batch.moved_members, 8);
        let mut batch = WanderBatch::new("epoch", [1134, 0], &policy);
        for gid in 1..=4 {
            let roster: Vec<_> = (0..10)
                .map(|j| actor(-(gid * 10 + j + 1), [0, gid * 10 + j, 0]))
                .collect();
            assert!(batch.append(gid, &roster, &translated(&roster)).unwrap());
        }
        assert_eq!(batch.moved_members, 40);
        let before = batch.payload();
        let roster = [actor(-99, [0, 99, 0])];
        assert!(!batch.append(5, &roster, &translated(&roster)).unwrap());
        assert_eq!(before, batch.payload());
    }

    #[test]
    fn wander_batch_rejects_oversized_wire_and_python_ascii_json_envelopes_atomically() {
        let policy = json!({"move_probability":1.0,"radius":20,"min_steps":1,"max_steps":3,"interval_seconds":2.0});
        let mut batch = WanderBatch::new("epoch", [1134, 0], &policy);
        let roster = [actor(-1, [0, 0, 0])];
        let mut plan = translated(&roster);
        plan.packets[0][1] = json!("00".repeat(64 * 1024));
        assert!(!batch.append(1, &roster, &plan).unwrap());
        assert_eq!(
            (batch.moves.len(), batch.moved_members, batch.packet_bytes),
            (0, 0, 0)
        );
        let mut large = actor(-1, [0, 0, 0]);
        large["name"] = json!("é".repeat(20_000));
        let roster = [large];
        let plan = translated(&roster);
        assert!(
            serde_json::to_vec(&json!({"expected":roster,"moved":plan.members}))
                .unwrap()
                .len()
                < 224 * 1024
        );
        assert!(!batch.append(1, &roster, &plan).unwrap());
        assert_eq!(
            (batch.moves.len(), batch.moved_members, batch.packet_bytes),
            (0, 0, 0)
        );
    }
}

#[cfg(test)]
#[path = "legacy_home_contract.rs"]
mod legacy_home_contract;

#[cfg(test)]
#[path = "legacy_wander_contract.rs"]
mod legacy_wander_contract;

#[cfg(test)]
#[path = "cohesion_contract.rs"]
mod cohesion_contract;
