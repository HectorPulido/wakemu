//! Once-per-empty-episode redistribution and bounded certified-surface cleanup.
//! Plans retain original physical reservations so independently retried chunks are safe.
use super::mob_geometry::{self, Geometry, Point};
use crate::Context;
use anyhow::{anyhow, ensure, Context as _, Result};
use rand::{seq::SliceRandom, Rng, SeedableRng};
use serde_json::{json, Value};
use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};
const MAX_CHUNK_GROUPS: usize = 8;
const MAX_CHUNK_BYTES: usize = 224 * 1024;
fn int(v: &Value, key: &str) -> Result<i64> {
    v[key]
        .as_i64()
        .ok_or_else(|| anyhow!("Invalid idle distribution {key}"))
}
fn members(v: &Value) -> Result<&Vec<Value>> {
    v["members"]
        .as_array()
        .context("Invalid idle group members")
}
fn scope(v: &Value) -> Result<[i64; 2]> {
    let a = v["scope"].as_array().context("Missing idle scope")?;
    ensure!(a.len() == 2, "Invalid idle scope");
    Ok([
        a[0].as_i64().context("Invalid idle map")?,
        a[1].as_i64().context("Invalid idle instance")?,
    ])
}
fn episode<'a>(
    epoch: &'a str,
    scope: [i64; 2],
    generation: i64,
) -> Result<(&'a str, i32, i64, i64)> {
    ensure!(
        !epoch.is_empty() && scope[1] == 0 && generation >= 0,
        "Invalid idle episode"
    );
    Ok((epoch, i32::try_from(scope[0])?, scope[1], generation))
}
async fn radii(ctx: &Context, groups: &[Value]) -> Result<HashMap<i64, i64>> {
    let mut refs = BTreeSet::new();
    for group in groups {
        for m in members(group)? {
            refs.insert(int(m, "ref")?);
        }
    }
    let mut out = HashMap::new();
    for reference in refs {
        out.insert(
            reference,
            mob_geometry::physical_radius(ctx, reference).await?,
        );
    }
    Ok(out)
}
fn physical(member: &Value, at: Option<Point>, radii: &HashMap<i64, i64>) -> Result<Vec<Point>> {
    mob_geometry::footprint(
        at.unwrap_or(mob_geometry::point(member)?),
        *radii
            .get(&int(member, "ref")?)
            .context("Missing native physical radius")?,
    )
}
fn compact(
    anchor: Point,
    members: &[Value],
    adjacent: &HashMap<Point, Vec<Point>>,
    blocked: &HashSet<Point>,
    native: &HashSet<Point>,
    radii: &HashMap<i64, i64>,
) -> Result<Option<Vec<Point>>> {
    let mut own: HashSet<Point> = physical(&members[0], Some(anchor), radii)?
        .into_iter()
        .collect();
    if !own.is_subset(native) || !own.is_disjoint(blocked) {
        return Ok(None);
    }
    if members.len() == 1 {
        return Ok(Some(vec![anchor]));
    }
    if members.len() > 128 {
        return Ok(None);
    }
    let mut queue = VecDeque::from([anchor]);
    let mut visited = HashSet::from([anchor]);
    let mut candidates = Vec::new();
    while let Some(cell) = queue.pop_front() {
        candidates.push(cell);
        for dest in adjacent.get(&cell).into_iter().flatten() {
            if visited.contains(dest)
                || !native.contains(dest)
                || (dest[0] - anchor[0]).abs().max((dest[1] - anchor[1]).abs()) > 4
            {
                continue;
            }
            if visited.len() >= 128 {
                break;
            }
            visited.insert(*dest);
            queue.push_back(*dest);
        }
    }
    let mut result = vec![anchor];
    for member in &members[1..] {
        let mut selected = None;
        for cell in &candidates {
            let footprint: HashSet<_> = physical(member, Some(*cell), radii)?.into_iter().collect();
            if footprint.is_subset(native)
                && footprint.is_disjoint(blocked)
                && footprint.is_disjoint(&own)
            {
                own.extend(footprint);
                selected = Some(*cell);
                break;
            }
        }
        if let Some(cell) = selected {
            result.push(cell)
        } else {
            return Ok(None);
        }
    }
    Ok(Some(result))
}
async fn plan(
    ctx: &Context,
    map: i64,
    groups: &[Value],
    geometry: &Geometry,
    reserved: HashSet<Point>,
    homes: &HashMap<i64, i64>,
) -> Result<Vec<Value>> {
    ensure!(
        groups.len() <= 4096,
        "Idle monster planning budget exceeds its bound"
    );
    let living: Vec<Value> = groups
        .iter()
        .filter(|g| g["status"] != "defeated")
        .cloned()
        .collect();
    let radii = radii(ctx, &living).await?;
    let mut candidates: Vec<Value> = living
        .iter()
        .filter(|g| {
            g["status"] == "available"
                && g["members"].as_array().is_some_and(|m| !m.is_empty())
                && homes
                    .get(&g["group_id"].as_i64().unwrap_or(0))
                    .is_some_and(|h| *h > 0)
        })
        .cloned()
        .collect();
    let mut rng = rand::rngs::StdRng::from_os_rng();
    candidates.shuffle(&mut rng);
    candidates.truncate(4096.min(groups.len().max(1)));
    if candidates.is_empty() {
        return Ok(vec![]);
    }
    let wanted: HashSet<i64> = candidates
        .iter()
        .map(|g| homes[&g["group_id"].as_i64().unwrap()])
        .collect();
    let mut home_cells: HashMap<i64, Vec<Point>> = wanted.iter().map(|h| (*h, vec![])).collect();
    let cells: BTreeSet<Point> = geometry.cells.iter().copied().collect();
    let terrain = mob_geometry::terrain_policy(ctx, map, 0).await?;
    for cell in cells {
        match terrain.region(cell) {
            Ok(home) => {
                if let Some(points) = home_cells.get_mut(&home) {
                    points.push(cell);
                }
            }
            Err(_) => continue,
        }
    }
    let home_native: HashMap<i64, HashSet<Point>> = home_cells
        .iter()
        .map(|(h, p)| (*h, p.iter().copied().collect()))
        .collect();
    let mut originals: HashMap<Point, usize> = HashMap::new();
    for group in &living {
        for member in members(group)? {
            for cell in physical(member, None, &radii)? {
                *originals.entry(cell).or_default() += 1;
            }
        }
    }
    let mut blocked: HashSet<Point> = originals
        .keys()
        .copied()
        .chain(reserved.iter().copied())
        .collect();
    let mut targets = HashSet::new();
    let mut totals: HashMap<i64, usize> = HashMap::new();
    for group in &candidates {
        *totals.entry(homes[&int(group, "group_id")?]).or_default() += members(group)?.len();
    }
    let mut cumulative: HashMap<i64, usize> = HashMap::new();
    let mut moves = Vec::new();
    let adjacent: HashMap<Point, Vec<Point>> = geometry
        .adjacent
        .iter()
        .map(|(p, points)| {
            let mut points = points.clone();
            points.sort();
            points.dedup();
            (*p, points)
        })
        .collect();
    for group in candidates {
        let group_id = int(&group, "group_id")?;
        let home = homes[&group_id];
        let available = &home_cells[&home];
        if available.is_empty() {
            continue;
        }
        let expected = members(&group)?;
        let accumulated = cumulative.entry(home).or_default();
        let mut lower = *accumulated * available.len() / totals[&home];
        *accumulated += expected.len();
        let upper = (lower + 1)
            .max(*accumulated * available.len() / totals[&home])
            .min(available.len());
        lower = lower.min(upper - 1);
        let mut own: HashMap<Point, usize> = HashMap::new();
        for member in expected {
            for cell in physical(member, None, &radii)? {
                *own.entry(cell).or_default() += 1;
            }
        }
        let released: HashSet<Point> = own
            .iter()
            .filter(|(cell, count)| {
                originals.get(*cell) == Some(*count)
                    && !reserved.contains(*cell)
                    && !targets.contains(*cell)
            })
            .map(|(cell, _)| *cell)
            .collect();
        for cell in &released {
            blocked.remove(cell);
        }
        let mut chosen = None;
        let mut tried = HashSet::new();
        for attempt in 0..12 {
            let index = if attempt < 6 {
                rng.random_range(lower..upper)
            } else {
                rng.random_range(0..available.len())
            };
            let anchor = available[index];
            if !tried.insert(anchor) {
                continue;
            }
            chosen = compact(
                anchor,
                expected,
                &adjacent,
                &blocked,
                &home_native[&home],
                &radii,
            )?;
            if chosen.is_some() {
                break;
            }
        }
        let Some(destinations) = chosen else {
            blocked.extend(released);
            continue;
        };
        let mut moved = expected.clone();
        for (member, p) in moved.iter_mut().zip(destinations) {
            for (key, n) in ["x", "y", "z"].into_iter().zip(p) {
                member[key] = json!(n);
            }
        }
        let mut actual = HashSet::new();
        for member in &moved {
            actual.extend(physical(member, None, &radii)?);
        }
        targets.extend(actual.iter().copied());
        blocked.extend(released);
        blocked.extend(actual);
        if expected
            .iter()
            .zip(&moved)
            .any(|(a, b)| ["x", "y", "z"].iter().any(|k| a[*k] != b[*k]))
        {
            moves.push(
                json!({"group_id":group_id,"expected_members":expected,"moved_members":moved}),
            );
        }
    }
    Ok(moves)
}
fn validate_move(m: &Value, scope: [i64; 2]) -> Result<()> {
    let expected = m["expected_members"]
        .as_array()
        .context("Missing idle expected members")?;
    let moved = m["moved_members"]
        .as_array()
        .context("Missing idle moved members")?;
    int(m, "group_id")?;
    ensure!(
        !expected.is_empty() && expected.len() == moved.len(),
        "Invalid idle distribution group"
    );
    for (old, new) in expected.iter().zip(moved) {
        let mut a = old.as_object().context("Invalid idle member")?.clone();
        let mut b = new.as_object().context("Invalid idle member")?.clone();
        for k in ["x", "y", "z"] {
            int(new, k)?;
            a.remove(k);
            b.remove(k);
        }
        ensure!(a == b, "Idle distribution may only change positions");
        ensure!(
            [int(old, "map_id")?, int(old, "instance_id")?] == scope,
            "Foreign idle member"
        );
    }
    Ok(())
}
async fn reservations(
    ctx: &Context,
    map: i32,
    instance: i64,
    groups: &[Value],
) -> Result<Vec<Value>> {
    let existing: HashSet<i64> = groups
        .iter()
        .map(|g| int(g, "group_id"))
        .collect::<Result<_>>()?;
    let db = ctx.db.get().await?;
    let rows=db.query("SELECT group_payload FROM planting_growth_outbox WHERE published=FALSE AND group_payload IS NOT NULL AND (resource->>'map_id')::integer=$1 AND (resource->>'instance_id')::bigint=$2 UNION ALL SELECT group_payload FROM planting_receipts WHERE published=FALSE AND success AND group_payload IS NOT NULL AND (resource->>'map_id')::integer=$1 AND (resource->>'instance_id')::bigint=$2",&[&map,&instance]).await?;
    let mut unique: HashMap<i64, Value> = HashMap::new();
    for row in rows {
        let group: Value = row.get(0);
        let key = group["key"]
            .as_array()
            .context("Invalid planted group reservation")?;
        ensure!(
            key.len() == 3
                && key[0].as_i64() == Some(map as i64)
                && key[1].as_i64() == Some(instance),
            "Foreign planted group reservation"
        );
        let id = key[2]
            .as_i64()
            .context("Invalid reservation group identity")?;
        let roster = members(&group)?;
        ensure!(
            !roster.is_empty() && roster.iter().all(Value::is_object),
            "Invalid planted reservation roster"
        );
        if existing.contains(&id) {
            continue;
        }
        if let Some(old) = unique.get(&id) {
            ensure!(
                old["members"] == group["members"],
                "Conflicting planted group reservations"
            );
        } else {
            unique.insert(id, group);
        }
    }
    Ok(unique.into_values().collect())
}
async fn freeze(
    ctx: &Context,
    epoch: &str,
    scope: [i64; 2],
    generation: i64,
    moves: &[Value],
) -> Result<i64> {
    let (_, map, instance, generation) = episode(epoch, scope, generation)?;
    let mut chunk = 0i32;
    let mut size = 0usize;
    let mut count = 0;
    let mut prepared = Vec::new();
    let mut seen = HashSet::new();
    for (ordinal, m) in moves.iter().enumerate() {
        validate_move(m, scope)?;
        ensure!(seen.insert(int(m, "group_id")?), "Repeated idle group");
        let bytes = serde_json::to_string(m)?
            .chars()
            .map(|c| {
                if c.is_ascii() {
                    1
                } else if c as u32 <= 0xffff {
                    6
                } else {
                    12
                }
            })
            .sum::<usize>();
        if bytes > MAX_CHUNK_BYTES {
            prepared.push((
                ordinal as i32,
                chunk,
                m,
                "skipped",
                Some("group_byte_budget"),
            ));
            continue;
        }
        if count > 0 && (count == MAX_CHUNK_GROUPS || size + bytes > MAX_CHUNK_BYTES) {
            chunk += 1;
            size = 0;
            count = 0;
        }
        prepared.push((ordinal as i32, chunk, m, "pending", None));
        size += bytes;
        count += 1;
    }
    let pending = prepared.iter().any(|r| r.3 == "pending");
    let status = if pending { "pending" } else { "completed" };
    let finished = !pending;
    let mut client = ctx.db.get().await?;
    let db = client.transaction().await?;
    let row=db.query_opt("INSERT INTO monster_idle_distribution_runs(world_epoch,map_id,instance_id,empty_generation,status,finished_at) VALUES($1,$2,$3,$4,$5,CASE WHEN $6 THEN clock_timestamp() END) ON CONFLICT DO NOTHING RETURNING id",&[&epoch,&map,&instance,&generation,&status,&finished]).await?;
    let id = if let Some(row) = row {
        let id: i64 = row.get(0);
        for (ordinal, chunk, m, status, reason) in prepared {
            let done = status != "pending";
            let group = int(m, "group_id")?;
            db.execute("INSERT INTO monster_idle_distribution_moves(run_id,ordinal,chunk_index,group_id,expected_members,moved_members,status,reason,finished_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,CASE WHEN $9 THEN clock_timestamp() END)",&[&id,&ordinal,&chunk,&group,&m["expected_members"],&m["moved_members"],&status,&reason,&done]).await?;
        }
        id
    } else {
        db.query_one("SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=$1 AND map_id=$2 AND instance_id=$3 AND empty_generation=$4",&[&epoch,&map,&instance,&generation]).await?.get(0)
    };
    db.commit().await?;
    Ok(id)
}
async fn pending(
    ctx: &Context,
    epoch: &str,
    scope: [i64; 2],
    generation: i64,
    limit: usize,
) -> Result<Vec<Value>> {
    let (_, map, instance, generation) = episode(epoch, scope, generation)?;
    ensure!((1..=256).contains(&limit), "Invalid idle proposal limit");
    let db = ctx.db.get().await?;
    let limit = limit as i64;
    Ok(db.query("SELECT r.id,m.chunk_index FROM monster_idle_distribution_runs r JOIN monster_idle_distribution_moves m ON m.run_id=r.id WHERE r.world_epoch=$1 AND r.map_id=$2 AND r.instance_id=$3 AND r.empty_generation=$4 AND r.status='pending' AND m.status='pending' GROUP BY r.id,m.chunk_index ORDER BY m.chunk_index LIMIT $5",&[&epoch,&map,&instance,&generation,&limit]).await?.into_iter().map(|r|json!({"kind":"idle_distribution","world_epoch":epoch,"scope":scope,"empty_generation":generation,"run_id":r.get::<_,i64>(0),"chunk_index":r.get::<_,i32>(1)})).collect())
}
pub async fn read_chunk(ctx: &Context, p: &Value) -> Result<Vec<Value>> {
    let scope = scope(p)?;
    let epoch = p["world_epoch"]
        .as_str()
        .context("Missing idle world epoch")?;
    let (_, map, instance, generation) = episode(epoch, scope, int(p, "empty_generation")?)?;
    let run = int(p, "run_id")?;
    let chunk = i32::try_from(int(p, "chunk_index")?)?;
    let db = ctx.db.get().await?;
    Ok(db.query("SELECT jsonb_build_object('group_id',m.group_id,'expected_members',m.expected_members,'moved_members',m.moved_members) FROM monster_idle_distribution_moves m JOIN monster_idle_distribution_runs r ON r.id=m.run_id WHERE r.id=$1 AND r.world_epoch=$2 AND r.map_id=$3 AND r.instance_id=$4 AND r.empty_generation=$5 AND r.status='pending' AND m.chunk_index=$6 AND m.status='pending' ORDER BY m.ordinal",&[&run,&epoch,&map,&instance,&generation,&chunk]).await?.into_iter().map(|r|r.get(0)).collect())
}
pub async fn home_chunk_allowed(ctx: &Context, p: &Value) -> Result<bool> {
    let scope = scope(p)?;
    let planned = read_chunk(ctx, p).await?;
    let groups: Vec<Value> = planned
        .iter()
        .map(|m| json!({"group_id":m["group_id"],"members":m["expected_members"]}))
        .collect();
    let homes = mob_geometry::ensure_homes(ctx, scope, &groups).await?;
    let terrain = mob_geometry::terrain_policy(ctx, scope[0], scope[1]).await?;
    for m in planned {
        let Some(home) = homes.get(&int(&m, "group_id")?) else {
            return Ok(false);
        };
        for member in m["moved_members"]
            .as_array()
            .context("Missing idle moved roster")?
        {
            let radius = mob_geometry::physical_radius(ctx, int(member, "ref")?).await?;
            if !terrain.home_allowed(Some(*home), mob_geometry::point(member)?, &[radius]) {
                return Ok(false);
            }
        }
    }
    Ok(true)
}
async fn cancel(ctx: &Context, epoch: &str, scope: [i64; 2], generation: i64) -> Result<()> {
    let (_, map, instance, generation) = episode(epoch, scope, generation)?;
    let mut client = ctx.db.get().await?;
    let db = client.transaction().await?;
    if let Some(row)=db.query_opt("SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=$1 AND map_id=$2 AND instance_id=$3 AND empty_generation=$4 FOR UPDATE",&[&epoch,&map,&instance,&generation]).await?{let id:i64=row.get(0);db.execute("UPDATE monster_idle_distribution_moves SET status='cancelled',finished_at=clock_timestamp() WHERE run_id=$1 AND status='pending'",&[&id]).await?;db.execute("UPDATE monster_idle_distribution_runs SET status='cancelled',finished_at=clock_timestamp() WHERE id=$1 AND status='pending'",&[&id]).await?;}
    db.commit().await?;
    Ok(())
}
pub async fn validate_idle_proposal(ctx: &Context, p: &Value) -> Result<bool> {
    let scope = scope(p)?;
    let planned = read_chunk(ctx, p).await?;
    let mut groups = Vec::new();
    for m in &planned {
        validate_move(m, scope)?;
        groups.push(json!({"group_id":m["group_id"],"members":m["moved_members"]}));
    }
    let map = i32::try_from(scope[0])?;
    let db = ctx.db.get().await?;
    let living:Vec<Value>=db.query("SELECT to_jsonb(g) FROM combat_groups g WHERE map_id=$1 AND instance_id=$2 AND status!='defeated'",&[&map,&scope[1]]).await?.into_iter().map(|r|r.get(0)).collect();
    drop(db);
    let reserved = reservations(ctx, map, scope[1], &living).await?;
    groups.extend(living);
    groups.extend(reserved);
    let radii = radii(ctx, &groups).await?;
    let geometry = mob_geometry::load_geometry(ctx, scope[0]).await?;
    let native: HashSet<Point> = geometry.cells.iter().copied().collect();
    for m in &planned {
        let mut occupied = HashSet::new();
        for member in m["moved_members"]
            .as_array()
            .context("Invalid idle moved roster")?
        {
            let actual: HashSet<_> = physical(member, None, &radii)?.into_iter().collect();
            ensure!(
                actual.is_subset(&native) && actual.is_disjoint(&occupied),
                "Idle distribution leaves native terrain or overlaps"
            );
            occupied.extend(actual);
        }
    }
    home_chunk_allowed(ctx, p).await
}
pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!((1..=256).contains(&limit), "Invalid idle preparation limit");
    let epoch = snapshot["world_epoch"]
        .as_str()
        .context("Missing idle world epoch")?;
    let mut proposals = Vec::new();
    for empty in snapshot
        .get("empty_scopes")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let scope = [int(empty, "map_id")?, int(empty, "instance_id")?];
        if scope[1] != 0 {
            continue;
        }
        let generation = int(empty, "empty_generation")?;
        let (_, map, instance, generation) = episode(epoch, scope, generation)?;
        let db = ctx.db.get().await?;
        let exists=db.query_opt("SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=$1 AND map_id=$2 AND instance_id=$3 AND empty_generation=$4",&[&epoch,&map,&instance,&generation]).await?.is_some();
        let groups: Vec<Value> = if exists {
            vec![]
        } else {
            db.query("SELECT to_jsonb(g) FROM combat_groups g WHERE map_id=$1 AND instance_id=$2 ORDER BY group_id",&[&map,&instance]).await?.into_iter().map(|r|r.get(0)).collect()
        };
        drop(db);
        if !exists {
            let reserved = reservations(ctx, map, instance, &groups).await?;
            let prepared = async {
                let living: Vec<Value> = groups
                    .iter()
                    .filter(|g| g["status"] != "defeated")
                    .cloned()
                    .collect();
                let homes = mob_geometry::ensure_homes(ctx, scope, &living).await?;
                let radii = radii(ctx, &reserved).await?;
                let mut occupied = HashSet::new();
                for group in reserved {
                    for member in members(&group)? {
                        occupied.extend(physical(member, None, &radii)?);
                    }
                }
                let geometry = mob_geometry::load_geometry(ctx, scope[0]).await?;
                plan(ctx, scope[0], &groups, &geometry, occupied, &homes).await
            }
            .await;
            match prepared {
                Ok(moves) => {
                    freeze(ctx, epoch, scope, generation, &moves).await?;
                }
                Err(error) => {
                    if error.downcast_ref::<tokio_postgres::Error>().is_some()
                        || error
                            .downcast_ref::<deadpool_postgres::PoolError>()
                            .is_some()
                    {
                        return Err(error);
                    }
                    eprintln!("Idle distribution planning deferred for scope {scope:?} episode {generation}: {error:#}");
                    continue;
                }
            }
        }
        for proposal in pending(ctx, epoch, scope, generation, limit - proposals.len()).await? {
            if !home_chunk_allowed(ctx, &proposal).await? {
                cancel(ctx, epoch, scope, generation).await?;
                break;
            }
            proposals.push(proposal);
        }
        if proposals.len() >= limit {
            break;
        }
    }
    Ok(proposals)
}
/// Match World's flattened (map, region) registry, not document map headers.
/// Scripted maps may have a catalogue header with no ecological territories.
fn cleanup_maps(catalog: &Value) -> Result<Vec<i32>> {
    let mut maps = BTreeSet::new();
    for world in catalog
        .as_array()
        .context("Invalid native ecology regions")?
    {
        for region in world["regions"]
            .as_array()
            .context("Invalid native ecology territories")?
        {
            let region_id = i32::try_from(int(region, "region_id")?)?;
            let map_id = i32::try_from(int(world, "map_id")?)?;
            ensure!(
                map_id > 0 && region_id > 0,
                "Invalid native ecology territory identity"
            );
            maps.insert(map_id);
        }
    }
    Ok(maps.into_iter().collect())
}

struct ScanState {
    epoch: String,
    at: Instant,
    cursor: (i32, i64),
}
static SCAN: OnceLock<Mutex<Option<ScanState>>> = OnceLock::new();
/// Exact unassigned planting surfaces are deletion evidence; unknown data never is.
pub async fn prepare_cleanup(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    if snapshot.get("planning_tick").is_none() {
        return Ok(vec![]);
    }
    ensure!(
        (1..=256).contains(&limit),
        "Invalid cleanup preparation limit"
    );
    let epoch = snapshot["world_epoch"]
        .as_str()
        .filter(|s| !s.is_empty())
        .context("Missing cleanup world epoch")?;
    let now = Instant::now();
    let mut cursor = {
        let guard = SCAN
            .get_or_init(|| Mutex::new(None))
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        match guard.as_ref() {
            Some(s) if s.epoch == epoch => {
                if now.duration_since(s.at) < Duration::from_secs(60) {
                    return Ok(vec![]);
                }
                s.cursor
            }
            _ => (-1, i64::MIN),
        }
    };
    let regions = ctx.catalog.document("ecology-regions.json").await?;
    let maps = cleanup_maps(&regions)?;
    let excluded: HashSet<i64> = snapshot
        .get("excluded_ids")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|v| v.as_i64().context("Invalid cleanup exclusion"))
        .collect::<Result<_>>()?;
    let db = ctx.db.get().await?;
    let rows=db.query("SELECT to_jsonb(g) FROM combat_groups g WHERE instance_id=0 AND status='available' AND map_id=ANY($1) AND NOT EXISTS(SELECT 1 FROM environmental_owned_groups o WHERE (o.map_id,o.world_instance_id,o.group_id)=(g.map_id,g.instance_id,g.group_id)) AND NOT EXISTS(SELECT 1 FROM developer_item_test_groups t WHERE (t.map_id,t.instance_id,t.group_id)=(g.map_id,g.instance_id,g.group_id)) AND (map_id,group_id)>($2,$3) ORDER BY map_id,group_id LIMIT 512",&[&maps,&cursor.0,&cursor.1]).await?;
    drop(db);
    let mut examined = 0usize;
    let mut proposals = Vec::new();
    for row in rows {
        let group: Value = row.get(0);
        examined += 1;
        let map = i32::try_from(int(&group, "map_id")?)?;
        cursor = (map, int(&group, "group_id")?);
        let mut bad = Vec::new();
        // Catalog lookup errors mean absence of certified evidence, never guessed deletion.
        for member in members(&group)? {
            let id = int(member, "id")?;
            if excluded.contains(&id) {
                continue;
            }
            let point = mob_geometry::point(member)?;
            let coordinates = (
                i32::try_from(point[0]),
                i32::try_from(point[1]),
                i16::try_from(point[2]),
            );
            if let (Ok(x), Ok(y), Ok(z)) = coordinates {
                match ctx.catalog.surface_region(map, x, y, z).await {
                    Ok(-1) => bad.push(id),
                    Ok(_) => {}
                    Err(error)
                        if error.downcast_ref::<tokio_postgres::Error>().is_some()
                            || error
                                .downcast_ref::<deadpool_postgres::PoolError>()
                                .is_some() =>
                    {
                        return Err(error)
                    }
                    Err(_) => {} // Unknown native surfaces never certify removal.
                }
            }
        }
        if !bad.is_empty() {
            proposals.push(json!({"kind":"cleanup_unassigned","world_epoch":epoch,"scope":[map,0],"group_id":group["group_id"],"expected_members":group["members"],"actor_ids":bad}));
            if proposals.len() >= limit {
                break;
            }
        }
    }
    if examined < 512 && proposals.len() < limit {
        cursor = (-1, i64::MIN)
    }
    *SCAN
        .get()
        .unwrap()
        .lock()
        .unwrap_or_else(|e| e.into_inner()) = Some(ScanState {
        epoch: epoch.to_owned(),
        at: now,
        cursor,
    });
    Ok(proposals)
}

#[cfg(test)]
mod cleanup_scope_tests {
    use super::cleanup_maps;
    use serde_json::json;

    #[test]
    fn cleanup_excludes_scripted_map_headers_without_ecological_regions() {
        let native = json!([
            {"map_id":1388,"regions":[]},
            {"map_id":1387,"regions":[]},
            {"map_id":1134,"regions":[{"region_id":79001},{"region_id":79201}]}
        ]);
        assert_eq!(cleanup_maps(&native).unwrap(), vec![1134]);
        assert!(cleanup_maps(&json!([{"map_id":1388,"regions":[]}]))
            .unwrap()
            .is_empty());
    }

    #[test]
    fn cleanup_requires_valid_territory_records_before_authorizing_a_map() {
        assert!(cleanup_maps(&json!([{"map_id":1134,"regions":[{}]}])).is_err());
        assert!(cleanup_maps(&json!([{"map_id":1134,"regions":[{"region_id":0}]}])).is_err());
    }
}

#[cfg(test)]
#[path = "cleanup_contract.rs"]
mod cleanup_contract;
