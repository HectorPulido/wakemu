//! Shared native spatial geometry, path codecs and occupancy certificates.
//! Database reads, durable commits and socket publication stay in adapters.
use anyhow::{anyhow, ensure, Context as _, Result};
use rand::{seq::SliceRandom, Rng};
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

pub type Point = [i64; 3];
pub const COHESION: i64 = 4;
pub const DISPERSION: i64 = 12;
pub const MAX_FIELD_CELLS: usize = 65536;
pub const MAX_HOME_DISTANCE: u16 = 1024;
pub const FIELD_CACHE_BYTES: usize = 8 * 1024 * 1024;
pub const DIRECTIONS: [[i64; 2]; 8] = [
    [1, -1],
    [1, 0],
    [1, 1],
    [0, 1],
    [-1, 1],
    [-1, 0],
    [-1, -1],
    [0, -1],
];

/// Directed edge membership shares the adjacency allocation; retaining a second
/// full set of six-coordinate edges more than doubles large-map index storage.
pub struct DirectedEdges {
    pub adjacent: Arc<HashMap<Point, Vec<Point>>>,
}
impl DirectedEdges {
    pub fn contains(&self, edge: &(Point, Point)) -> bool {
        self.adjacent
            .get(&edge.0)
            .is_some_and(|destinations| destinations.binary_search(&edge.1).is_ok())
    }
    pub fn iter(&self) -> impl Iterator<Item = (Point, Point)> + '_ {
        self.adjacent.iter().flat_map(|(origin, destinations)| {
            destinations
                .iter()
                .map(move |destination| (*origin, *destination))
        })
    }
}

pub struct Geometry {
    pub cells: Vec<Point>,
    pub edges: DirectedEdges,
    pub adjacent: Arc<HashMap<Point, Vec<Point>>>,
    pub digest: [u8; 32],
}

#[derive(Deserialize)]
pub struct GeometryDocument {
    map_id: i32,
    cells: Vec<[i32; 3]>,
    edges: Vec<[[i32; 3]; 2]>,
}

pub fn native_point(point: [i32; 3]) -> Result<Point> {
    checked_point([
        i64::from(point[0]),
        i64::from(point[1]),
        i64::from(point[2]),
    ])
}

/// Decode only the native coordinate arrays. A 17MB map must never become a
/// several-hundred-MB serde_json::Value tree before building its spatial index.
pub fn geometry_bytes(raw: &[u8], expected_map: i32) -> Result<Geometry> {
    let document: GeometryDocument = serde_json::from_slice(raw)?;
    ensure!(
        document.map_id == expected_map,
        "Combat map export identity differs"
    );
    let cells = document
        .cells
        .into_iter()
        .map(native_point)
        .collect::<Result<Vec<_>>>()?;
    let mut cells = cells;
    cells.sort_unstable();
    cells.dedup();
    let mut adjacent = HashMap::new();
    for [origin, destination] in document.edges {
        add_native_edge(
            &cells,
            &mut adjacent,
            native_point(origin)?,
            native_point(destination)?,
        )?;
    }
    finish_geometry(cells, adjacent)
}

pub fn add_native_edge(
    cells: &[Point],
    adjacent: &mut HashMap<Point, Vec<Point>>,
    origin: Point,
    destination: Point,
) -> Result<()> {
    ensure!(
        cells.binary_search(&origin).is_ok() && cells.binary_search(&destination).is_ok(),
        "Native edge leaves exported geometry"
    );
    adjacent.entry(origin).or_default().push(destination);
    Ok(())
}

pub fn finish_geometry(
    mut cells: Vec<Point>,
    mut adjacent: HashMap<Point, Vec<Point>>,
) -> Result<Geometry> {
    cells.shrink_to_fit();
    for destinations in adjacent.values_mut() {
        destinations.sort_unstable();
        destinations.dedup();
        destinations.shrink_to_fit();
    }
    adjacent.shrink_to_fit();
    let mut digest = Sha256::new();
    for point in &cells {
        for coordinate in point {
            digest.update(coordinate.to_be_bytes());
        }
    }
    digest.update([0xff]);
    for origin in &cells {
        for destination in adjacent.get(origin).into_iter().flatten() {
            for coordinate in origin.iter().chain(destination.iter()) {
                digest.update(coordinate.to_be_bytes());
            }
        }
    }
    let adjacent = Arc::new(adjacent);
    Ok(Geometry {
        cells,
        edges: DirectedEdges {
            adjacent: Arc::clone(&adjacent),
        },
        adjacent,
        digest: digest.finalize().into(),
    })
}

pub fn point(member: &Value) -> Result<Point> {
    checked_point([
        integer(member, "x")?,
        integer(member, "y")?,
        integer(member, "z")?,
    ])
}
pub fn checked_point(point: Point) -> Result<Point> {
    i32::try_from(point[0])?;
    i32::try_from(point[1])?;
    i16::try_from(point[2])?;
    Ok(point)
}
pub fn integer(value: &Value, key: &str) -> Result<i64> {
    value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Missing exact monster {key}"))
}
pub fn array_point(value: &Value) -> Result<Point> {
    let row = value
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native coordinate"))?;
    ensure!(row.len() == 3, "Invalid native coordinate width");
    checked_point([
        row[0].as_i64().ok_or_else(|| anyhow!("Invalid native x"))?,
        row[1].as_i64().ok_or_else(|| anyhow!("Invalid native y"))?,
        row[2].as_i64().ok_or_else(|| anyhow!("Invalid native z"))?,
    ])
}
pub fn geometry(value: &Value) -> Result<Geometry> {
    let mut cells = value["cells"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing native walk cells"))?
        .iter()
        .map(array_point)
        .collect::<Result<Vec<_>>>()?;
    cells.sort_unstable();
    cells.dedup();
    let mut adjacent = HashMap::new();
    for raw in value["edges"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing native directed edges"))?
    {
        let edge = raw
            .as_array()
            .filter(|edge| edge.len() == 2)
            .ok_or_else(|| anyhow!("Invalid native directed edge width"))?;
        add_native_edge(
            &cells,
            &mut adjacent,
            array_point(&edge[0])?,
            array_point(&edge[1])?,
        )?;
    }
    finish_geometry(cells, adjacent)
}

pub fn footprint(position: Point, radius: i64) -> Result<Vec<Point>> {
    ensure!(
        (-128..=127).contains(&radius),
        "Invalid native signed-byte physical radius"
    );
    if radius <= 0 {
        return Ok(vec![position]);
    }
    let mut cells = Vec::with_capacity(((2 * radius + 1) * (2 * radius + 1)) as usize);
    for dx in -radius..=radius {
        for dy in -radius..=radius {
            cells.push([position[0] + dx, position[1] + dy, position[2]]);
        }
    }
    Ok(cells)
}

pub fn movement_packet(actor: i64, path: &[Point]) -> Result<Vec<u8>> {
    ensure!(
        actor < 0 && !path.is_empty(),
        "Invalid native NPC movement identity"
    );
    let mut deltas = Vec::new();
    for pair in path.windows(2) {
        if pair[0] == pair[1] {
            continue;
        }
        let dx = pair[1][0] - pair[0][0];
        let dy = pair[1][1] - pair[0][1];
        let dz = pair[1][2] - pair[0][2];
        let direction = DIRECTIONS
            .iter()
            .position(|p| *p == [dx, dy])
            .ok_or_else(|| anyhow!("Invalid native NPC direction"))?;
        ensure!((-16..=15).contains(&dz), "Invalid native NPC height delta");
        deltas.push(((direction as u8) << 5) | ((dz & 31) as u8));
    }
    ensure!(
        deltas.len() <= 255,
        "Native NPC path exceeds unsigned-byte steps"
    );
    let start = path[0];
    let x = i32::try_from(start[0])?;
    let y = i32::try_from(start[1])?;
    let z = i16::try_from(start[2])?;
    let mut bytes = Vec::with_capacity(19 + deltas.len());
    bytes.extend(actor.to_be_bytes());
    bytes.extend(x.to_be_bytes());
    bytes.extend(y.to_be_bytes());
    bytes.extend(z.to_be_bytes());
    bytes.push(deltas.len() as u8);
    bytes.extend(deltas);
    Ok(bytes)
}
pub fn decode_packet(packet: &Value) -> Result<(i64, Point, Vec<Point>)> {
    let row = packet
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native packet"))?;
    ensure!(
        row.len() == 2 && row[0].as_i64() == Some(13852),
        "Invalid native movement opcode"
    );
    let bytes = hex::decode(
        row[1]
            .as_str()
            .ok_or_else(|| anyhow!("Invalid movement bytes"))?,
    )?;
    ensure!(
        bytes.len() >= 19 && bytes.len() == 19 + bytes[18] as usize,
        "Invalid native movement length"
    );
    let actor = i64::from_be_bytes(bytes[0..8].try_into()?);
    let origin = [
        i32::from_be_bytes(bytes[8..12].try_into()?) as i64,
        i32::from_be_bytes(bytes[12..16].try_into()?) as i64,
        i16::from_be_bytes(bytes[16..18].try_into()?) as i64,
    ];
    let mut current = origin;
    let mut cells = Vec::with_capacity(bytes[18] as usize);
    for delta in &bytes[19..] {
        let d = DIRECTIONS[(delta >> 5) as usize];
        let z = (delta & 31) as i64;
        current = [
            current[0] + d[0],
            current[1] + d[1],
            current[2] + if z >= 16 { z - 32 } else { z },
        ];
        cells.push(current);
    }
    Ok((actor, origin, cells))
}
pub fn distance(a: Point, b: Point) -> i64 {
    (a[0] - b[0]).pow(2) + (a[1] - b[1]).pow(2)
}
pub fn chebyshev(a: Point, b: Point) -> i64 {
    (a[0] - b[0]).abs().max((a[1] - b[1]).abs())
}
pub fn near(members: &[Point], players: &[Point], radius: i64) -> bool {
    members
        .iter()
        .any(|m| players.iter().any(|p| chebyshev(*m, *p) <= radius))
}
pub fn shifted(origin: Point, delta: Point) -> Point {
    [
        origin[0] + delta[0],
        origin[1] + delta[1],
        origin[2] + delta[2],
    ]
}
pub fn member_points(members: &[Value]) -> Result<Vec<Point>> {
    members.iter().map(point).collect()
}
pub fn living(group: &Value) -> bool {
    group["status"].as_str() != Some("defeated")
}
pub fn members(group: &Value) -> Result<&Vec<Value>> {
    group["members"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing monster group roster"))
}
pub fn external_cells(
    own: &[Value],
    players: &[Point],
    groups: &[Value],
) -> Result<HashSet<Point>> {
    let own_id = own.first().and_then(|m| m["id"].as_i64());
    let mut result: HashSet<_> = players.iter().copied().collect();
    for group in groups.iter().filter(|g| living(g)) {
        let roster = members(group)?;
        if roster.first().and_then(|m| m["id"].as_i64()) == own_id {
            continue;
        }
        for member in roster {
            result.insert(point(member)?);
        }
    }
    Ok(result)
}
pub fn overlap_count(members: &[Value], external: &HashSet<Point>) -> Result<usize> {
    let points = member_points(members)?;
    let mut counts = HashMap::new();
    for p in &points {
        *counts.entry(*p).or_insert(0) += 1;
    }
    Ok(points
        .iter()
        .filter(|p| counts[*p] > 1 || external.contains(*p))
        .count())
}
pub fn nearest_group(origin: Point, own: i64, groups: &[Value]) -> Result<Option<Point>> {
    let mut entries = Vec::new();
    for group in groups.iter().filter(|group| living(group)) {
        if let Some(member) = members(group)?.first() {
            entries.push((Some(integer(member, "id")?), point(member)?));
        }
    }
    Ok(nearest_entries(origin, &entries, Some(own)))
}

#[derive(Clone)]
pub struct MovePlan {
    pub members: Vec<Value>,
    pub packets: Vec<Value>,
    pub dispersal: bool,
    pub overlap_escape: bool,
}
pub fn path_result(members: &[Value], paths: &[Vec<Point>]) -> Result<MovePlan> {
    let mut moved = members.to_vec();
    let mut packets = Vec::new();
    for (member, path) in moved.iter_mut().zip(paths) {
        let end = *path.last().ok_or_else(|| anyhow!("Empty native path"))?;
        member["x"] = json!(end[0]);
        member["y"] = json!(end[1]);
        member["z"] = json!(end[2]);
        if path[0] != end {
            packets.push(json!([
                13852,
                hex::encode(movement_packet(integer(member, "id")?, path)?)
            ]));
        }
    }
    Ok(MovePlan {
        members: moved,
        packets,
        dispersal: false,
        overlap_escape: false,
    })
}
pub fn choose<R: Rng + ?Sized>(
    mut candidates: Vec<Vec<Point>>,
    rng: &mut R,
    away: Option<Point>,
    origin: Point,
) -> Option<Vec<Point>> {
    if let Some(target) = away {
        let farther: Vec<_> = candidates
            .iter()
            .filter(|c| distance(c[0], target) > distance(origin, target))
            .cloned()
            .collect();
        if !farther.is_empty() {
            candidates = farther;
        }
    }
    if candidates.is_empty() {
        None
    } else {
        Some(candidates.swap_remove(rng.random_range(0..candidates.len())))
    }
}
pub fn native_step(actor: i64, origin: Point, destination: Point) -> bool {
    origin != destination && movement_packet(actor, &[origin, destination]).is_ok()
}
pub fn rigid_step<R: Rng + ?Sized>(
    members: &[Value],
    origins: &[Point],
    players: &[Point],
    geometry: &Geometry,
    blocked: &HashSet<Point>,
    radius: i64,
    allowed: &impl Fn(Point) -> bool,
    away: Option<Point>,
    rng: &mut R,
) -> Result<Option<Vec<Point>>> {
    if !near(origins, players, radius) {
        return Ok(None);
    }
    let mut candidates = Vec::new();
    for destination in geometry.adjacent.get(&origins[0]).into_iter().flatten() {
        let delta = [
            destination[0] - origins[0][0],
            destination[1] - origins[0][1],
            destination[2] - origins[0][2],
        ];
        let ds: Vec<_> = origins.iter().map(|o| shifted(*o, delta)).collect();
        if ds.iter().copied().collect::<HashSet<_>>().len()
            < origins.iter().copied().collect::<HashSet<_>>().len()
            || ds
                .iter()
                .any(|p| blocked.contains(p) || players.contains(p) || !allowed(*p))
        {
            continue;
        }
        if origins
            .iter()
            .zip(&ds)
            .any(|(a, b)| !geometry.edges.contains(&(*a, *b)))
        {
            continue;
        }
        if members
            .iter()
            .zip(origins)
            .zip(&ds)
            .any(|((m, a), b)| !native_step(integer(m, "id").unwrap_or(0), *a, *b))
        {
            continue;
        }
        candidates.push(ds);
    }
    Ok(choose(candidates, rng, away, origins[0]))
}
pub fn ordinary_path<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    geometry: &Geometry,
    blocked: &HashSet<Point>,
    radius: i64,
    steps: usize,
    allowed: &impl Fn(Point) -> bool,
    away: Option<Point>,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    let mut paths: Vec<_> = member_points(members)?
        .into_iter()
        .map(|p| vec![p])
        .collect();
    let mut moved = false;
    for _ in 0..steps {
        let origins: Vec<_> = paths.iter().map(|p| *p.last().unwrap()).collect();
        let mut occupied = blocked.clone();
        for path in &paths {
            occupied.extend(path[..path.len() - 1].iter().copied());
        }
        let Some(ds) = rigid_step(
            members, &origins, players, geometry, &occupied, radius, allowed, away, rng,
        )?
        else {
            break;
        };
        for (path, d) in paths.iter_mut().zip(ds) {
            path.push(d);
        }
        moved = true;
    }
    if moved {
        Ok(Some(path_result(members, &paths)?))
    } else {
        Ok(None)
    }
}
pub fn flexible_step<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    geometry: &Geometry,
    blocked: &HashSet<Point>,
    allowed: &impl Fn(Point) -> bool,
    away: Option<Point>,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    let origins = member_points(members)?;
    let mut occupied = blocked.clone();
    occupied.extend(players.iter().copied());
    occupied.extend(origins.iter().copied());
    let mut candidates = Vec::new();
    for leader in geometry.adjacent.get(&origins[0]).into_iter().flatten() {
        let delta = [
            leader[0] - origins[0][0],
            leader[1] - origins[0][1],
            leader[2] - origins[0][2],
        ];
        let ds: Vec<_> = origins
            .iter()
            .zip(members)
            .map(|(a, m)| {
                let b = shifted(*a, delta);
                if occupied.contains(&b)
                    || !geometry.edges.contains(&(*a, b))
                    || !allowed(b)
                    || !native_step(integer(m, "id").unwrap_or(0), *a, b)
                {
                    *a
                } else {
                    b
                }
            })
            .collect();
        if ds == origins
            || ds.iter().copied().collect::<HashSet<_>>().len()
                < origins.iter().copied().collect::<HashSet<_>>().len()
            || ds.iter().any(|p| chebyshev(*p, ds[0]) > COHESION)
        {
            continue;
        }
        candidates.push(ds);
    }
    let advancing: Vec<_> = candidates
        .iter()
        .filter(|c| c[0] != origins[0])
        .cloned()
        .collect();
    if !advancing.is_empty() {
        candidates = advancing;
    }
    Ok(choose(candidates, rng, away, origins[0])
        .map(|ds| {
            path_result(
                members,
                &origins
                    .iter()
                    .zip(ds)
                    .map(|(a, b)| vec![*a, b])
                    .collect::<Vec<_>>(),
            )
        })
        .transpose()?)
}
pub fn overlap_escape<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    groups: &[Value],
    geometry: &Geometry,
    depth: usize,
    allowed: &impl Fn(Point) -> bool,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    let external = external_cells(members, players, groups)?;
    let original = member_points(members)?;
    let mut routes = Vec::new();
    let mut choices = Vec::new();
    for member in members {
        let origin = point(member)?;
        let mut found = HashMap::from([(origin, vec![origin])]);
        let mut order = vec![origin];
        let mut queue = VecDeque::from([origin]);
        while let Some(cell) = queue.pop_front() {
            let path = found[&cell].clone();
            if path.len() > depth {
                continue;
            }
            let mut adjacent = geometry.adjacent.get(&cell).cloned().unwrap_or_default();
            adjacent.shuffle(rng);
            for d in adjacent {
                if found.contains_key(&d)
                    || !allowed(d)
                    || !native_step(integer(member, "id")?, cell, d)
                {
                    continue;
                }
                let mut path = path.clone();
                path.push(d);
                found.insert(d, path);
                order.push(d);
                queue.push_back(d);
            }
        }
        choices.push(
            order
                .into_iter()
                .filter(|p| !external.contains(p))
                .collect::<Vec<_>>(),
        );
        routes.push(found);
    }
    fn assign(
        actor: usize,
        choices: &[Vec<Point>],
        endpoints: &mut HashMap<Point, usize>,
        assigned: &mut HashMap<usize, Point>,
        visited: &mut HashSet<Point>,
    ) -> bool {
        let mut candidates = choices[actor].clone();
        candidates.sort_by_key(|p| endpoints.contains_key(p));
        for cell in candidates {
            if !visited.insert(cell) {
                continue;
            }
            let previous = endpoints.get(&cell).copied();
            if previous.is_none()
                || assign(previous.unwrap(), choices, endpoints, assigned, visited)
            {
                endpoints.insert(cell, actor);
                assigned.insert(actor, cell);
                return true;
            }
        }
        false
    }
    let mut counts = HashMap::new();
    for p in &original {
        *counts.entry(*p).or_insert(0) += 1;
    }
    let mut order: Vec<_> = (0..members.len()).collect();
    order.sort_by_key(|i| counts[&original[*i]] > 1 || external.contains(&original[*i]));
    let mut endpoints = HashMap::new();
    let mut assigned = HashMap::new();
    for actor in order {
        assign(
            actor,
            &choices,
            &mut endpoints,
            &mut assigned,
            &mut HashSet::new(),
        );
    }
    let paths: Vec<_> = original
        .iter()
        .enumerate()
        .map(|(i, p)| {
            assigned
                .get(&i)
                .map(|end| routes[i][end].clone())
                .unwrap_or_else(|| vec![*p])
        })
        .collect();
    let mut result = path_result(members, &paths)?;
    let before = overlap_count(members, &external)?;
    if !result.packets.is_empty()
        && before > 0
        && overlap_count(&result.members, &external)? < before
    {
        result.overlap_escape = true;
        Ok(Some(result))
    } else {
        Ok(None)
    }
}
pub fn dispersal_path<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    groups: &[Value],
    geometry: &Geometry,
    target: Point,
    radius: i64,
    steps: usize,
    allowed: &impl Fn(Point) -> bool,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    let original = member_points(members)?;
    let cohesion = original
        .iter()
        .map(|p| chebyshev(*p, original[0]))
        .max()
        .unwrap_or(0)
        .max(COHESION);
    let mut paths: Vec<_> = original.iter().map(|p| vec![*p]).collect();
    let external = external_cells(members, players, groups)?;
    let mut last_clear = None;
    for _ in 0..steps {
        let origins: Vec<_> = paths.iter().map(|p| *p.last().unwrap()).collect();
        if !near(&origins, players, radius) {
            break;
        }
        let mut candidates = Vec::new();
        for b in geometry.adjacent.get(&origins[0]).into_iter().flatten() {
            if distance(*b, target) <= distance(origins[0], target) {
                continue;
            }
            let delta = [
                b[0] - origins[0][0],
                b[1] - origins[0][1],
                b[2] - origins[0][2],
            ];
            let ds: Vec<_> = origins
                .iter()
                .map(|a| {
                    let p = shifted(*a, delta);
                    if geometry.edges.contains(&(*a, p)) && allowed(p) {
                        p
                    } else {
                        *a
                    }
                })
                .collect();
            if ds[0] != *b
                || ds.iter().any(|p| chebyshev(*p, *b) > cohesion)
                || members.iter().zip(&origins).zip(&ds).any(|((m, a), d)| {
                    *a != *d && !native_step(integer(m, "id").unwrap_or(0), *a, *d)
                })
            {
                continue;
            }
            candidates.push(ds);
        }
        let Some(ds) = choose(candidates, rng, None, origins[0]) else {
            break;
        };
        for (path, d) in paths.iter_mut().zip(ds) {
            path.push(d);
        }
        let result = path_result(members, &paths)?;
        if overlap_count(&result.members, &external)? == 0 {
            last_clear = Some(paths.clone());
        }
    }
    last_clear.map(|p| path_result(members, &p)).transpose()
}
pub fn group_path<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    groups: &[Value],
    geometry: &Geometry,
    occupied: &HashSet<Point>,
    radius: i64,
    min_steps: usize,
    max_steps: usize,
    allowed: &impl Fn(Point) -> bool,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    if members.is_empty() || players.is_empty() || radius <= 0 {
        return Ok(None);
    }
    let origins = member_points(members)?;
    if !near(&origins, players, radius) {
        return Ok(None);
    }
    let external = external_cells(members, players, groups)?;
    if overlap_count(members, &external)? > 0 {
        return overlap_escape(
            members,
            players,
            groups,
            geometry,
            max_steps.min(3),
            allowed,
            rng,
        );
    }
    let mut away = None;
    if rng.random::<f64>() < 0.5 {
        away = nearest_group(origins[0], integer(&members[0], "id")?, groups)?;
        if let Some(target) = away {
            let steps = rng.random_range(min_steps..=max_steps);
            if let Some(mut result) = dispersal_path(
                members, players, groups, geometry, target, radius, steps, allowed, rng,
            )? {
                if distance(point(&result.members[0])?, target) > distance(origins[0], target) {
                    result.dispersal = true;
                    return Ok(Some(result));
                }
            }
        }
    }
    if origins
        .iter()
        .all(|p| chebyshev(*p, origins[0]) <= COHESION)
    {
        let steps = rng.random_range(min_steps..=max_steps);
        if let Some(result) = ordinary_path(
            members, players, geometry, occupied, radius, steps, allowed, away, rng,
        )? {
            return Ok(Some(result));
        }
        if members.len() == 1 {
            return Ok(None);
        }
        return flexible_step(members, players, geometry, occupied, allowed, away, rng);
    }
    let mut blocked = occupied.clone();
    blocked.extend(players.iter().copied());
    blocked.extend(origins.iter().copied());
    let mut paths: Vec<_> = origins.iter().map(|p| vec![*p]).collect();
    let mut any = false;
    for i in 1..members.len() {
        let a = origins[i];
        if chebyshev(a, origins[0]) <= COHESION {
            continue;
        }
        let mut choices: Vec<_> = geometry
            .adjacent
            .get(&a)
            .into_iter()
            .flatten()
            .copied()
            .filter(|p| {
                !blocked.contains(p)
                    && chebyshev(*p, origins[0]) < chebyshev(a, origins[0])
                    && allowed(*p)
            })
            .collect();
        choices.sort_by_key(|p| (chebyshev(*p, origins[0]), *p));
        if let Some(b) = choices.first() {
            if !native_step(integer(&members[i], "id")?, a, *b) {
                continue;
            }
            blocked.remove(&a);
            blocked.insert(*b);
            paths[i].push(*b);
            any = true;
        }
    }
    if any {
        Ok(Some(path_result(members, &paths)?))
    } else {
        Ok(None)
    }
}

#[derive(Hash, PartialEq, Eq, Clone)]
pub struct FieldKey {
    geometry: [u8; 32],
    authority: String,
    home: i64,
    radii: Vec<i64>,
}
pub struct Fields {
    values: VecDeque<(FieldKey, Arc<HashMap<Point, u16>>, usize)>,
    bytes: usize,
}
static FIELDS: OnceLock<Mutex<Fields>> = OnceLock::new();

/// Resident distance-field allocation, exposed for cache-budget diagnostics.
pub fn distance_field_cache_bytes() -> usize {
    FIELDS
        .get()
        .map(|cache| cache.lock().unwrap_or_else(|e| e.into_inner()).bytes)
        .unwrap_or(0)
}

pub fn distance_field(
    geometry: &Geometry,
    authority: &str,
    home: i64,
    radii: &[i64],
    inside: &impl Fn(Point) -> bool,
) -> Arc<HashMap<Point, u16>> {
    let key = FieldKey {
        geometry: geometry.digest,
        authority: authority.to_owned(),
        home,
        radii: radii.to_vec(),
    };
    let cache = FIELDS.get_or_init(|| {
        Mutex::new(Fields {
            values: VecDeque::new(),
            bytes: 0,
        })
    });
    if !authority.is_empty() {
        let mut guard = cache.lock().unwrap_or_else(|p| p.into_inner());
        if let Some(i) = guard.values.iter().position(|v| v.0 == key) {
            let row = guard.values.remove(i).unwrap();
            let result = row.1.clone();
            guard.values.push_back(row);
            return result;
        }
    }
    let mut reverse: HashMap<Point, Vec<Point>> = HashMap::new();
    let mut cells = BTreeSet::new();
    for (origin, destination) in geometry.edges.iter() {
        reverse.entry(destination).or_default().push(origin);
        cells.insert(origin);
        cells.insert(destination);
    }
    let mut distances = HashMap::new();
    let mut queue = VecDeque::new();
    for p in cells {
        if inside(p) {
            distances.insert(p, 0u16);
            queue.push_back(p);
            if distances.len() >= MAX_FIELD_CELLS {
                break;
            }
        }
    }
    while let Some(p) = queue.pop_front() {
        let d = distances[&p];
        if d >= MAX_HOME_DISTANCE {
            continue;
        }
        for a in reverse.get(&p).into_iter().flatten() {
            if distances.len() >= MAX_FIELD_CELLS || distances.contains_key(a) {
                continue;
            }
            distances.insert(*a, d + 1);
            queue.push_back(*a);
        }
    }
    // HashMap's usable capacity excludes its spare buckets and control bytes.
    // Charge those as well, plus the key/Arc/deque bookkeeping.
    let buckets = distances.capacity().saturating_mul(8).div_ceil(7);
    let bytes = buckets
        .saturating_mul(std::mem::size_of::<(Point, u16)>() + 1)
        .saturating_add(key.authority.capacity())
        .saturating_add(key.radii.capacity() * std::mem::size_of::<i64>())
        .saturating_add(256);
    let result = Arc::new(distances);
    if !authority.is_empty() && bytes <= FIELD_CACHE_BYTES {
        let mut guard = cache.lock().unwrap_or_else(|p| p.into_inner());
        if let Some(index) = guard.values.iter().position(|row| row.0 == key) {
            let duplicate = guard.values.remove(index).unwrap();
            guard.bytes -= duplicate.2;
        }
        while guard.bytes + bytes > FIELD_CACHE_BYTES {
            if let Some(row) = guard.values.pop_front() {
                guard.bytes -= row.2;
            } else {
                break;
            }
        }
        guard.bytes += bytes;
        guard.values.push_back((key, result.clone(), bytes));
    }
    result
}
pub fn homing_path<R: Rng + ?Sized>(
    members: &[Value],
    players: &[Point],
    geometry: &Geometry,
    occupied: &HashSet<Point>,
    radius: i64,
    min_steps: usize,
    max_steps: usize,
    authority: &str,
    home: i64,
    radii: &[i64],
    inside: &impl Fn(Point) -> bool,
    habitat: &impl Fn(Point) -> bool,
    rng: &mut R,
) -> Result<Option<MovePlan>> {
    let origins = member_points(members)?;
    if origins.is_empty() || players.is_empty() || !near(&origins, players, radius) {
        return Ok(None);
    }
    let distances = distance_field(geometry, authority, home, radii, inside);
    if origins.iter().all(|p| distances.get(p) == Some(&0)) {
        return Ok(None);
    }
    let mut paths: Vec<_> = origins.iter().map(|p| vec![*p]).collect();
    let mut external = occupied.clone();
    external.extend(players.iter().copied());
    let cohesion = origins
        .iter()
        .map(|p| chebyshev(*p, origins[0]))
        .max()
        .unwrap_or(0)
        .max(COHESION);
    for _ in 0..rng.random_range(min_steps..=max_steps) {
        let current: Vec<_> = paths.iter().map(|p| *p.last().unwrap()).collect();
        if !near(&current, players, radius) {
            break;
        }
        let mut blocked = external.clone();
        for path in &paths {
            blocked.extend(path.iter().copied());
        }
        let mut selected = None;
        for _ in 0..4 {
            let mut ds = Vec::new();
            let mut reserved = HashSet::new();
            for (member, origin) in members.iter().zip(&current) {
                let mut choices = Vec::new();
                if let Some(before) = distances.get(origin) {
                    for destination in geometry.adjacent.get(origin).into_iter().flatten() {
                        let Some(after) = distances.get(destination) else {
                            continue;
                        };
                        if (if *before == 0 {
                            *after != 0
                        } else {
                            *after >= *before
                        }) || blocked.contains(destination)
                            || reserved.contains(destination)
                            || !habitat(*destination)
                            || !native_step(integer(member, "id")?, *origin, *destination)
                        {
                            continue;
                        }
                        choices.push(*destination);
                    }
                }
                let destination = if choices.is_empty() {
                    *origin
                } else {
                    choices[rng.random_range(0..choices.len())]
                };
                ds.push(destination);
                reserved.insert(destination);
            }
            if ds == current
                || ds.iter().copied().collect::<HashSet<_>>().len()
                    < current.iter().copied().collect::<HashSet<_>>().len()
                || ds.iter().any(|p| chebyshev(*p, ds[0]) > cohesion)
            {
                continue;
            }
            selected = Some(ds);
            break;
        }
        let Some(ds) = selected else { break };
        for (path, d) in paths.iter_mut().zip(ds) {
            path.push(d);
        }
    }
    if !paths.iter().any(|p| p[0] != *p.last().unwrap()) {
        return Ok(None);
    }
    let endpoints: HashSet<_> = paths.iter().map(|p| *p.last().unwrap()).collect();
    if endpoints.len() != members.len() || endpoints.iter().any(|p| external.contains(p)) {
        return Ok(None);
    }
    Ok(Some(path_result(members, &paths)?))
}

/// Compact per-pass lookup, avoiding an asynchronous catalogue read per step.
pub struct TerrainPolicy {
    pub regions: HashMap<[i64; 2], i64>,
    pub surfaces: HashMap<Point, i64>,
    pub has_map: bool,
    pub outdoor: bool,
    pub authority: String,
}
impl TerrainPolicy {
    pub fn tracked(&self) -> bool {
        self.has_map
    }
    pub fn certified_unassigned(&self, p: Point) -> bool {
        self.surfaces.get(&p) == Some(&-1)
    }
    pub fn region(&self, p: Point) -> Result<i64> {
        let grid = [p[0].div_euclid(18), p[1].div_euclid(18)];
        let region = *self
            .regions
            .get(&grid)
            .ok_or_else(|| anyhow!("Unknown native map territory at position"))?;
        if let Some(surface) = self.surfaces.get(&p) {
            ensure!(
                *surface == region,
                "Monster birth territory and native surface disagree"
            );
        }
        Ok(region)
    }
    pub fn habitat(&self, p: Point) -> bool {
        !self.outdoor || self.surfaces.contains_key(&p)
    }
    pub fn home_allowed(&self, home: Option<i64>, p: Point, radii: &[i64]) -> bool {
        let Some(home) = home else { return true };
        radii.iter().all(|r| {
            footprint(p, *r)
                .map(|cells| cells.into_iter().all(|c| self.region(c).ok() == Some(home)))
                .unwrap_or(false)
        })
    }
}
#[derive(Deserialize)]
pub struct TerritoryDocument {
    schema_version: i64,
    grid_size: i64,
    maps: Vec<TerritoryMap>,
}
#[derive(Deserialize)]
pub struct TerritoryMap {
    map_id: i64,
    regions: Vec<TerritoryRegion>,
}
#[derive(Deserialize)]
pub struct TerritoryRegion {
    region_id: i64,
    cells: Vec<[i64; 2]>,
}
#[derive(Deserialize)]
pub struct EcologyMap {
    map_id: i64,
    regions: Vec<serde::de::IgnoredAny>,
}
#[derive(Deserialize)]
pub struct PlantingDocument {
    cells: Vec<[i64; 6]>,
}

pub fn terrain_bytes(
    territory_raw: &[u8],
    ecology_raw: &[u8],
    surface_raw: Option<&[u8]>,
    map_id: i64,
    instance_id: i64,
    revision: &str,
) -> Result<TerrainPolicy> {
    let territories: TerritoryDocument = serde_json::from_slice(territory_raw)?;
    ensure!(
        territories.schema_version == 1 && territories.grid_size == 18,
        "Unsupported native territory cell catalogue"
    );
    let mut regions = HashMap::new();
    let mut has_map = false;
    for map in territories.maps {
        if map.map_id != map_id {
            continue;
        }
        has_map = true;
        for region in map.regions {
            ensure!(region.region_id > 0, "Invalid native home territory");
            for point in region.cells {
                ensure!(
                    regions.insert(point, region.region_id).is_none(),
                    "Overlapping native territory grid cells"
                );
            }
        }
    }
    regions.shrink_to_fit();
    let ecology: Vec<EcologyMap> = serde_json::from_slice(ecology_raw)?;
    // Python REGIONS is flattened over actual territories. A scripted map with
    // only an empty header does not acquire an outdoor habitat restriction.
    let outdoor = instance_id == 0
        && ecology
            .iter()
            .any(|map| map.map_id == map_id && !map.regions.is_empty());
    let mut surfaces = HashMap::new();
    if let Some(raw) = surface_raw {
        let document: PlantingDocument = serde_json::from_slice(raw)?;
        for row in document.cells {
            let point = checked_point([row[0], row[1], row[2]])?;
            surfaces.entry(point).or_insert(row[5]);
        }
    }
    surfaces.shrink_to_fit();
    Ok(TerrainPolicy {
        regions,
        surfaces,
        has_map,
        outdoor,
        authority: format!("{revision}:{map_id}"),
    })
}

pub fn group_id(group: &Value) -> Result<i64> {
    group
        .get("group_id")
        .and_then(Value::as_i64)
        .or_else(|| group["key"].get(2).and_then(Value::as_i64))
        .ok_or_else(|| anyhow!("Missing monster group identity"))
}

pub fn eligible_birth_cells(
    indexed: &Geometry,
    terrain: &TerrainPolicy,
    parent: Point,
    blocked: &HashSet<[i64; 2]>,
    home: Option<i64>,
    radius: i64,
) -> Result<Vec<Point>> {
    Ok(indexed
        .adjacent
        .get(&parent)
        .into_iter()
        .flatten()
        .copied()
        .filter(|p| {
            !blocked.contains(&[p[0], p[1]])
                && terrain.home_allowed(home, *p, &[radius])
                && terrain.habitat(*p)
        })
        .collect())
}

pub fn visible_groups<'a>(
    groups: &'a [Value],
    players: &[Point],
    radius: i64,
    tick: u64,
) -> Result<Vec<&'a Value>> {
    let mut visible = Vec::new();
    for group in groups
        .iter()
        .filter(|g| g["status"].as_str() == Some("available"))
    {
        if near(&member_points(members(group)?)?, players, radius) {
            visible.push(group);
        }
    }
    if !visible.is_empty() {
        let start = (tick % visible.len() as u64) as usize;
        visible.rotate_left(start);
    }
    Ok(visible)
}

pub fn autonomous_roster(roster: &[Value], excluded: &HashSet<i64>) -> Result<bool> {
    if roster.is_empty()
        || roster
            .iter()
            .any(|m| m["id"].as_i64().is_some_and(|id| excluded.contains(&id)))
    {
        return Ok(false);
    }
    let mut fixed = false;
    for member in roster {
        if member.get("fixed_actor_placement").is_some() {
            placement_direction(member)?;
            fixed = true;
        }
    }
    Ok(!fixed)
}

pub fn wander_admitted(
    overlap: bool,
    allow_wander: bool,
    probability: f64,
    draw: impl FnOnce() -> f64,
) -> bool {
    overlap || (allow_wander && draw() < probability)
}

pub fn scope_occupancy(
    groups: &[Value],
    players: &[Point],
) -> Result<(HashSet<Point>, HashSet<i64>)> {
    let mut occupied = HashSet::new();
    let mut counts = HashMap::new();
    for group in groups.iter().filter(|g| living(g)) {
        for member in members(group)? {
            let p = point(member)?;
            occupied.insert(p);
            *counts.entry(p).or_insert(0usize) += 1;
        }
    }
    let player_cells: HashSet<_> = players.iter().copied().collect();
    let mut overlapping = HashSet::new();
    for group in groups.iter().filter(|g| living(g)) {
        if members(group)?.iter().any(|member| {
            point(member)
                .map(|p| counts[&p] > 1 || player_cells.contains(&p))
                .unwrap_or(false)
        }) {
            overlapping.insert(group_id(group)?);
        }
    }
    Ok((occupied, overlapping))
}

pub fn proposal_scope(proposal: &Value) -> Result<[i64; 2]> {
    let scope = proposal["scope"]
        .as_array()
        .filter(|s| s.len() == 2)
        .ok_or_else(|| anyhow!("Invalid movement scope"))?;
    Ok([
        scope[0]
            .as_i64()
            .ok_or_else(|| anyhow!("Invalid movement map"))?,
        scope[1]
            .as_i64()
            .ok_or_else(|| anyhow!("Invalid movement instance"))?,
    ])
}

pub fn validate_move(
    move_row: &Value,
) -> Result<(i64, Vec<Value>, Vec<Value>, HashMap<i64, Vec<Point>>)> {
    let object = move_row
        .as_object()
        .ok_or_else(|| anyhow!("Invalid wander fields"))?;
    let fields = ["group_id", "expected_members", "moved_members", "packets"];
    ensure!(
        fields.iter().all(|f| object.contains_key(*f))
            && object
                .keys()
                .all(|k| fields.contains(&k.as_str()) || k == "dispersal" || k == "overlap_escape"),
        "Invalid wander fields"
    );
    ensure!(
        !(object.contains_key("dispersal") && object.contains_key("overlap_escape")),
        "Conflicting movement certificates"
    );
    for key in ["dispersal", "overlap_escape"] {
        if let Some(v) = object.get(key) {
            ensure!(v == true, "Invalid movement certificate");
        }
    }
    let id = integer(move_row, "group_id")?;
    let expected = move_row["expected_members"]
        .as_array()
        .filter(|m| !m.is_empty())
        .ok_or_else(|| anyhow!("Invalid expected roster"))?;
    let moved = move_row["moved_members"]
        .as_array()
        .ok_or_else(|| anyhow!("Invalid moved roster"))?;
    ensure!(expected.len() == moved.len(), "Movement roster changed");
    let mut ids = HashSet::new();
    let mut changed = HashSet::new();
    let mut before = HashMap::new();
    let mut after = HashMap::new();
    for (a, b) in expected.iter().zip(moved) {
        let actor = integer(a, "id")?;
        ensure!(
            ids.insert(actor) && integer(b, "id")? == actor,
            "Movement actor identity changed"
        );
        let origin = point(a)?;
        let destination = point(b)?;
        before.insert(actor, origin);
        after.insert(actor, destination);
        if origin != destination {
            changed.insert(actor);
        }
    }
    ensure!(
        !changed.is_empty() && changed.len() <= 40,
        "Invalid moved member count"
    );
    let packets = move_row["packets"]
        .as_array()
        .filter(|p| !p.is_empty())
        .ok_or_else(|| anyhow!("Missing wander packets"))?;
    let mut paths = HashMap::new();
    let mut bytes = 0;
    for packet in packets {
        let (actor, origin, cells) = decode_packet(packet)?;
        ensure!(
            changed.contains(&actor)
                && !paths.contains_key(&actor)
                && before.get(&actor) == Some(&origin)
                && after.get(&actor) == cells.last(),
            "Movement bytes do not match roster CAS"
        );
        bytes += packet[1].as_str().unwrap().len() / 2 + 6;
        paths.insert(actor, cells);
    }
    ensure!(
        bytes <= 64 * 1024 && paths.keys().copied().collect::<HashSet<_>>() == changed,
        "Incomplete or oversized movement packet set"
    );
    Ok((id, expected.clone(), moved.clone(), paths))
}

pub fn queued_movement_allowed(
    indexed: &Geometry,
    terrain: &TerrainPolicy,
    home: i64,
    radii: &[i64],
    expected: &[Value],
    moved: &[Value],
    paths: &HashMap<i64, Vec<Point>>,
) -> Result<bool> {
    let inside = |p| terrain.home_allowed(Some(home), p, radii);
    let mut distances = None;
    let moved_by_id: HashMap<_, _> = moved
        .iter()
        .map(|m| Ok((integer(m, "id")?, point(m)?)))
        .collect::<Result<_>>()?;
    for member in expected {
        let actor = integer(&member, "id")?;
        let origin = point(&member)?;
        let Some(path) = paths.get(&actor) else {
            continue;
        };
        let returning = !inside(origin);
        if returning && distances.is_none() {
            distances = Some(distance_field(
                indexed,
                &terrain.authority,
                home,
                radii,
                &inside,
            ));
        }
        let mut previous = origin;
        let mut arrived = !returning;
        for destination in path {
            if !indexed.edges.contains(&(previous, *destination)) {
                return Ok(false);
            }
            if arrived {
                if !inside(*destination) {
                    return Ok(false);
                }
            } else {
                let field = distances.as_ref().unwrap();
                let Some(before) = field.get(&previous) else {
                    return Ok(false);
                };
                let Some(after) = field.get(destination) else {
                    return Ok(false);
                };
                if after >= before {
                    return Ok(false);
                }
                arrived = inside(*destination);
            }
            previous = *destination;
        }
        if moved_by_id.get(&actor) != Some(&previous) {
            return Ok(false);
        }
    }
    Ok(true)
}

pub fn queued_reproduction_allowed(
    terrain: &TerrainPolicy,
    home: i64,
    destination: Point,
    child: Option<&Value>,
    radius: i64,
) -> Result<bool> {
    if let Some(child) = child {
        if point(child)? != destination {
            return Ok(false);
        }
    }
    let radius = if child.is_some() { radius } else { 0 };
    Ok(terrain.home_allowed(Some(home), destination, &[radius]))
}

pub fn placement_direction(member: &Value) -> Result<u8> {
    let Some(row) = member.get("fixed_actor_placement") else {
        return Ok(3);
    };
    let reference = row["reference"]
        .as_i64()
        .context("Missing exact fixed actor reference")?;
    let direction = row["direction"]
        .as_i64()
        .context("Missing exact fixed actor direction")?;
    let cell = row["cell"].as_array().context("Invalid fixed actor cell")?;
    let source = &row["source"];
    let digest = source["sha256"]
        .as_str()
        .context("Missing fixed actor source SHA")?;
    ensure!(
        reference > 0
            && row["reference"] == member["ref"]
            && (0..=7).contains(&direction)
            && cell.len() == 3
            && cell.iter().all(|v| v.as_i64().is_some())
            && ["x", "y", "z"]
                .iter()
                .enumerate()
                .all(|(i, key)| member[*key] == cell[i])
            && matches!(
                source["kind"].as_str(),
                Some("original_native_marker" | "authorized_native_content_reconstruction")
            )
            && source["uri"]
                .as_str()
                .is_some_and(|uri| !uri.trim().is_empty())
            && digest.len() == 64
            && digest
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
        "Fixed actor placement lacks matching native terrain/source authority"
    );
    Ok(direction as u8)
}

// Immutable source indexes are bounded independently of actor/session state.
// Handles are cache keys: callers refill from their pinned catalog on eviction.
const INDEX_CACHE_BYTES: usize = 64 * 1024 * 1024;
const INDEX_CACHE_ENTRIES: usize = 256;
#[derive(Clone)]
enum IndexData {
    Graph(Arc<Geometry>),
    Neighbors(Arc<Vec<(Option<i64>, Point)>>),
    Habitats(Arc<HashSet<i64>>),
    Surfaces(Arc<Vec<Point>>),
}
#[derive(Default)]
struct IndexCache {
    entries: VecDeque<(String, IndexData, usize)>,
    bytes: usize,
}
static INDEXES: OnceLock<Mutex<IndexCache>> = OnceLock::new();
fn retain_index(key: String, data: IndexData, bytes: usize) -> Result<String> {
    let bytes = bytes.saturating_add(key.capacity()).saturating_add(256);
    ensure!(
        bytes <= INDEX_CACHE_BYTES,
        "Spatial index exceeds native cache budget"
    );
    let mut cache = INDEXES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    if let Some(i) = cache.entries.iter().position(|row| row.0 == key) {
        let old = cache.entries.remove(i).unwrap();
        cache.entries.push_back(old);
        return Ok(key);
    }
    while cache.bytes + bytes > INDEX_CACHE_BYTES || cache.entries.len() >= INDEX_CACHE_ENTRIES {
        if let Some(old) = cache.entries.pop_front() {
            cache.bytes -= old.2;
        } else {
            break;
        }
    }
    cache.bytes += bytes;
    cache.entries.push_back((key.clone(), data, bytes));
    Ok(key)
}
fn lookup_index(key: &str) -> Result<IndexData> {
    let mut cache = INDEXES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    let i = cache
        .entries
        .iter()
        .position(|row| row.0 == key)
        .ok_or_else(|| anyhow!("Spatial geometry handle expired"))?;
    let row = cache.entries.remove(i).unwrap();
    let result = row.1.clone();
    cache.entries.push_back(row);
    Ok(result)
}
fn index_key(kind: &str, authority: &str, raw: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(kind);
    digest.update([0]);
    digest.update(authority);
    digest.update([0]);
    digest.update(raw);
    hex::encode(digest.finalize())
}
fn graph_charge(graph: &Geometry) -> usize {
    graph.cells.capacity() * std::mem::size_of::<Point>()
        + graph.adjacent.capacity() * 8 / 7 * (std::mem::size_of::<(Point, Vec<Point>)>() + 1)
        + graph
            .adjacent
            .values()
            .map(|v| v.capacity() * std::mem::size_of::<Point>())
            .sum::<usize>()
}
fn value_array<'a>(data: &'a Value, name: &str) -> Result<&'a Vec<Value>> {
    data[name]
        .as_array()
        .ok_or_else(|| anyhow!("Missing spatial {name}"))
}
fn value_players(data: &Value) -> Result<Vec<Point>> {
    value_array(data, "players")?.iter().map(point).collect()
}
fn stable_rosters(expected: &[Value], moved: &[Value]) -> bool {
    !expected.is_empty()
        && expected.len() == moved.len()
        && expected
            .iter()
            .zip(moved)
            .all(|(a, b)| a.get("id") == b.get("id"))
}
fn nearest_entries(
    origin: Point,
    entries: &[(Option<i64>, Point)],
    own: Option<i64>,
) -> Option<Point> {
    entries
        .iter()
        .filter(|(id, p)| {
            (if let Some(own) = own {
                *id != Some(own)
            } else {
                *p != origin
            }) && chebyshev(*p, origin) <= DISPERSION
        })
        .min_by_key(|(id, p)| (distance(*p, origin), *p, id.unwrap_or(0)))
        .map(|(_, p)| *p)
}
pub fn separating_movement(expected: &[Value], moved: &[Value], groups: &[Value]) -> Result<bool> {
    if !stable_rosters(expected, moved) {
        return Ok(false);
    }
    let origin = point(&expected[0])?;
    let own = integer(&expected[0], "id")?;
    let Some(other) = nearest_group(origin, own, groups)? else {
        return Ok(false);
    };
    Ok(distance(point(&moved[0])?, other) > distance(origin, other))
}
pub fn valid_dispersal_path(
    expected: &[Value],
    moved: &[Value],
    paths: &HashMap<i64, Vec<Point>>,
    groups: &[Value],
) -> Result<bool> {
    if !separating_movement(expected, moved, groups)? {
        return Ok(false);
    }
    let origin = point(&expected[0])?;
    let actor = integer(&expected[0], "id")?;
    let Some(other) = nearest_group(origin, actor, groups)? else {
        return Ok(false);
    };
    let Some(path) = paths.get(&actor).filter(|p| !p.is_empty()) else {
        return Ok(false);
    };
    let mut previous = distance(origin, other);
    for p in path {
        let next = distance(*p, other);
        if next <= previous {
            return Ok(false);
        }
        previous = next;
    }
    Ok(true)
}
pub fn path_cells_by_actor(packets: &[Value]) -> Result<HashMap<i64, Vec<Point>>> {
    let mut paths = HashMap::new();
    for packet in packets {
        let (actor, _, cells) = decode_packet(packet)?;
        paths.insert(actor, cells);
    }
    Ok(paths)
}
pub fn path_cells(packets: &[Value]) -> Result<HashSet<Point>> {
    let mut cells = HashSet::new();
    for packet in packets {
        let (_, _, path) = decode_packet(packet)?;
        cells.extend(path);
    }
    Ok(cells)
}
fn json_points(cells: impl IntoIterator<Item = Point>) -> Value {
    let cells: BTreeSet<_> = cells.into_iter().collect();
    json!(cells)
}
fn paths_value(data: &Value) -> Result<HashMap<i64, Vec<Point>>> {
    value_array(data, "paths")?
        .iter()
        .map(|row| {
            let row = row
                .as_array()
                .filter(|r| r.len() == 2)
                .ok_or_else(|| anyhow!("Invalid spatial path pair"))?;
            let actor = row[0]
                .as_i64()
                .ok_or_else(|| anyhow!("Invalid spatial actor"))?;
            let cells = row[1]
                .as_array()
                .ok_or_else(|| anyhow!("Invalid spatial path"))?
                .iter()
                .map(array_point)
                .collect::<Result<_>>()?;
            Ok((actor, cells))
        })
        .collect()
}
fn validate_bulk_move_json(row: &Value) -> Result<Value> {
    let (gid, expected, moved, paths) = validate_move(row)?;
    let mut bytes = 0usize;
    let mut cells = HashSet::new();
    for packet in row["packets"].as_array().unwrap() {
        bytes += packet[1].as_str().unwrap().len() / 2 + 6;
        let (_, _, path) = decode_packet(packet)?;
        cells.extend(path);
    }
    let changed = paths.len();
    Ok(
        json!({"group_id":gid,"expected":expected,"moved":moved,"packets":row["packets"],
        "cells":json_points(cells),"moved_count":changed,"packet_bytes":bytes,
        "dispersal":row.get("dispersal").and_then(Value::as_bool).unwrap_or(false),
        "overlap_escape":row.get("overlap_escape").and_then(Value::as_bool).unwrap_or(false)}),
    )
}

pub fn lookup_graph(key: &str) -> Result<Arc<Geometry>> {
    let IndexData::Graph(graph) = lookup_index(key)? else {
        return Err(anyhow!("Wrong spatial index type"));
    };
    Ok(graph)
}
pub fn lookup_points(key: &str) -> Result<Arc<Vec<Point>>> {
    let IndexData::Surfaces(points) = lookup_index(key)? else {
        return Err(anyhow!("Wrong spatial index type"));
    };
    Ok(points)
}
fn register_parsed_graph(graph: Geometry) -> Result<String> {
    let bytes = graph_charge(&graph);
    // Only geometry content determines a graph. Release and policy provenance
    // stay in the caller's authority handle, avoiding duplicate full indexes.
    let key = index_key("graph", "", &graph.digest);
    if lookup_graph(&key).is_ok() {
        return Ok(key);
    }
    retain_index(key, IndexData::Graph(Arc::new(graph)), bytes)
}
pub fn register_geometry(raw: &[u8], map: i32, _authority: &str) -> Result<String> {
    register_parsed_graph(geometry_bytes(raw, map)?)
}
pub fn register_graph(source: &Value, _authority: &str) -> Result<String> {
    register_parsed_graph(geometry(source)?)
}
pub fn register_points(points: &[Value], authority: &str) -> Result<String> {
    let mut parsed: Vec<_> = points.iter().map(array_point).collect::<Result<_>>()?;
    parsed.sort_unstable();
    parsed.dedup();
    parsed.shrink_to_fit();
    let bytes = parsed.capacity() * std::mem::size_of::<Point>();
    let key = index_key("points", authority, &serde_json::to_vec(&parsed)?);
    retain_index(key, IndexData::Surfaces(Arc::new(parsed)), bytes)
}

/// FFI geometry commands never acquire actor/session ownership or perform I/O.
pub fn call(op: &str, data: &Value) -> Result<Value> {
    match op {
        "geometry.point" => Ok(json!(point(&data["actor"])?)),
        "geometry.load" => {
            let raw = data["raw"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing spatial source bytes"))?;
            let map = i32::try_from(integer(data, "map_id")?)?;
            let authority = data["authority"].as_str().unwrap_or("");
            Ok(json!({"key":register_geometry(raw.as_bytes(),map,authority)?}))
        }
        "geometry.index_graph" => {
            Ok(json!({"key":register_graph(data,data["authority"].as_str().unwrap_or(""))?}))
        }
        "geometry.index_points" => Ok(
            json!({"key":register_points(value_array(data,"points")?,data["authority"].as_str().unwrap_or(""))?}),
        ),
        "geometry.index_edges" => {
            let edges = value_array(data, "edges")?;
            let mut points = BTreeSet::new();
            for edge in edges {
                let row = edge
                    .as_array()
                    .filter(|v| v.len() == 2)
                    .ok_or_else(|| anyhow!("Invalid native directed edge"))?;
                points.insert(array_point(&row[0])?);
                points.insert(array_point(&row[1])?);
            }
            let source = json!({"cells":points,"edges":edges});
            Ok(json!({"key":register_graph(&source, "")?}))
        }
        "geometry.edge_contains" | "geometry.adjacent" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing spatial index key"))?;
            let IndexData::Graph(graph) = lookup_index(key)? else {
                return Err(anyhow!("Wrong spatial index type"));
            };
            let origin = array_point(&data["origin"])?;
            if op == "geometry.edge_contains" {
                Ok(json!(graph
                    .edges
                    .contains(&(origin, array_point(&data["destination"])?))))
            } else {
                Ok(json!(graph
                    .adjacent
                    .get(&origin)
                    .cloned()
                    .unwrap_or_default()))
            }
        }
        "geometry.neighbor_index" => {
            let groups = value_array(data, "groups")?;
            let mut entries = Vec::new();
            for g in groups.iter().filter(|g| living(g)) {
                if let Some(m) = members(g)?.first() {
                    entries.push((m.get("id").and_then(Value::as_i64), point(m)?));
                }
            }
            let bytes = entries.capacity() * std::mem::size_of::<(Option<i64>, Point)>();
            let key = index_key("neighbors", "", &serde_json::to_vec(&entries)?);
            Ok(json!({"key":retain_index(key,IndexData::Neighbors(Arc::new(entries)),bytes)?}))
        }
        "geometry.nearest_group" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing spatial index key"))?;
            let IndexData::Neighbors(entries) = lookup_index(key)? else {
                return Err(anyhow!("Wrong spatial index type"));
            };
            Ok(json!(nearest_entries(
                array_point(&data["origin"])?,
                &entries,
                data.get("exclude_id").and_then(Value::as_i64)
            )))
        }
        "geometry.separating_movement" => Ok(json!(separating_movement(
            value_array(data, "expected")?,
            value_array(data, "moved")?,
            value_array(data, "groups")?
        )?)),
        "geometry.external_cells"
        | "geometry.overlap_count"
        | "geometry.has_overlap"
        | "geometry.clear_destination" => {
            let own = value_array(data, "members")?;
            let players = value_players(data)?;
            let groups = value_array(data, "groups")?;
            let external = external_cells(own, &players, groups)?;
            match op {
                "geometry.external_cells" => Ok(json_points(external)),
                _ => {
                    let count = overlap_count(own, &external)?;
                    Ok(if op == "geometry.overlap_count" {
                        json!(count)
                    } else {
                        json!(if op == "geometry.clear_destination" {
                            count == 0
                        } else {
                            count > 0
                        })
                    })
                }
            }
        }
        "geometry.overlap_escape_valid" => {
            let expected = value_array(data, "expected")?;
            let moved = value_array(data, "moved")?;
            if !stable_rosters(expected, moved) {
                return Ok(json!(false));
            }
            let groups = value_array(data, "groups")?;
            let players = value_players(data)?;
            let before = overlap_count(expected, &external_cells(expected, &players, groups)?)?;
            let after = overlap_count(moved, &external_cells(moved, &players, groups)?)?;
            Ok(json!(before > 0 && after < before))
        }
        "geometry.paths_allowed" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing spatial index key"))?;
            let graph = lookup_graph(key)?;
            let expected: HashMap<_, _> = value_array(data, "expected")?
                .iter()
                .map(|m| Ok((integer(m, "id")?, point(m)?)))
                .collect::<Result<_>>()?;
            let limit = usize::try_from(integer(data, "max_steps")?)?;
            for (actor, path) in paths_value(data)? {
                let Some(mut origin) = expected.get(&actor).copied() else {
                    return Ok(json!(false));
                };
                if path.len() > limit {
                    return Ok(json!(false));
                }
                for destination in path {
                    if !graph.edges.contains(&(origin, destination)) {
                        return Ok(json!(false));
                    }
                    origin = destination;
                }
            }
            Ok(json!(true))
        }
        "geometry.path_cells" => Ok(json_points(path_cells(value_array(data, "packets")?)?)),
        "geometry.path_cells_by_actor" => {
            let paths = path_cells_by_actor(value_array(data, "packets")?)?;
            let mut rows: Vec<_> = paths.into_iter().collect();
            rows.sort_unstable_by_key(|row| row.0);
            Ok(json!(rows))
        }
        "geometry.validate_bulk_move" => validate_bulk_move_json(&data["move"]),
        "geometry.valid_dispersal_path" => Ok(json!(valid_dispersal_path(
            value_array(data, "expected")?,
            value_array(data, "moved")?,
            &paths_value(data)?,
            value_array(data, "groups")?
        )?)),
        "geometry.path_occupied" => {
            let own = value_array(data, "members")?;
            let ids: HashSet<_> = own
                .iter()
                .map(|m| integer(m, "id"))
                .collect::<Result<_>>()?;
            let mut occupied: HashSet<_> = value_players(data)?.into_iter().collect();
            for g in value_array(data, "groups")?.iter().filter(|g| living(g)) {
                for member in members(g)? {
                    if !ids.contains(&integer(member, "id")?) {
                        occupied.insert(point(member)?);
                    }
                }
            }
            Ok(json!(
                !path_cells(value_array(data, "packets")?)?.is_disjoint(&occupied)
            ))
        }
        "geometry.load_habitats" => {
            let raw = data["raw"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing habitat catalog"))?;
            let maps: Vec<EcologyMap> = serde_json::from_str(raw)?;
            let maps: HashSet<_> = maps
                .into_iter()
                .filter(|m| !m.regions.is_empty())
                .map(|m| m.map_id)
                .collect();
            let bytes = maps.capacity() * 16;
            let key = index_key(
                "habitats",
                data["authority"].as_str().unwrap_or(""),
                raw.as_bytes(),
            );
            Ok(json!({"key":retain_index(key,IndexData::Habitats(Arc::new(maps)),bytes)?}))
        }
        "geometry.habitat_tracked" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing habitat catalog key"))?;
            let IndexData::Habitats(maps) = lookup_index(key)? else {
                return Err(anyhow!("Wrong spatial index type"));
            };
            Ok(json!(
                integer(data, "instance_id")? == 0 && maps.contains(&integer(data, "map_id")?)
            ))
        }
        "geometry.load_surfaces" => {
            let raw = data["raw"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing planting surfaces"))?;
            let source: PlantingDocument = serde_json::from_str(raw)?;
            let mut points: Vec<_> = source
                .cells
                .into_iter()
                .map(|r| checked_point([r[0], r[1], r[2]]))
                .collect::<Result<_>>()?;
            points.sort_unstable();
            points.dedup();
            points.shrink_to_fit();
            let bytes = points.capacity() * std::mem::size_of::<Point>();
            let key = index_key(
                "surfaces",
                data["authority"].as_str().unwrap_or(""),
                raw.as_bytes(),
            );
            Ok(json!({"key":retain_index(key,IndexData::Surfaces(Arc::new(points)),bytes)?}))
        }
        "geometry.surface_paths_allowed" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing planting surface key"))?;
            let points = lookup_points(key)?;
            Ok(json!(paths_value(data)?
                .values()
                .flatten()
                .all(|point| points.binary_search(point).is_ok())))
        }
        "geometry.surface_exists" => {
            let key = data["key"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing planting surface key"))?;
            let IndexData::Surfaces(points) = lookup_index(key)? else {
                return Err(anyhow!("Wrong spatial index type"));
            };
            Ok(json!(points
                .binary_search(&array_point(&data["point"])?)
                .is_ok()))
        }
        _ => Err(anyhow!("Unknown native geometry operation: {op}")),
    }
}

#[cfg(test)]
mod world_guard_tests {
    use super::*;

    fn actor(id: i64, p: Point) -> Value {
        json!({"id":id,"x":p[0],"y":p[1],"z":p[2]})
    }

    #[test]
    fn packet_paths_preserve_heights_duplicates_and_reject_malformed_frames() {
        let bytes = movement_packet(-1, &[[0, 0, 10], [1, 0, -6], [1, 1, 9]]).unwrap();
        let packet = json!([13852, hex::encode(bytes)]);
        assert_eq!(
            path_cells_by_actor(&[packet.clone()]).unwrap()[&-1],
            [[1, 0, -6], [1, 1, 9]]
        );
        assert_eq!(path_cells(&[packet.clone(), packet]).unwrap().len(), 2);
        for bad in [json!([1, ""]), json!([13852, "00"]), json!([13852, "zz"])] {
            assert!(path_cells(&[bad]).is_err());
        }
    }

    #[test]
    fn graph_registration_reuses_semantic_content_and_keeps_isolated_cells() {
        let a = json!({"cells":[[0,0,0],[1,0,0],[9,9,0]],"edges":[[[0,0,0],[1,0,0]]]});
        let b = json!({"cells":[[9,9,0],[1,0,0],[0,0,0]],"edges":[[[0,0,0],[1,0,0]]],"allowed_cells":[[1,0,0]]});
        let first = register_graph(&a, "release-a").unwrap();
        let second = register_graph(&b, "release-b").unwrap();
        assert_eq!(first, second);
        assert!(Arc::ptr_eq(
            &lookup_graph(&first).unwrap(),
            &lookup_graph(&second).unwrap()
        ));
        assert!(lookup_graph(&first).unwrap().cells.contains(&[9, 9, 0]));
        let check = |paths: Value, max_steps: i64| {
            call(
                "geometry.paths_allowed",
                &json!({
            "key":first,"expected":[actor(-1,[0,0,0])],"paths":paths,"max_steps":max_steps}),
            )
            .unwrap()
        };
        assert_eq!(check(json!([[-1, [[1, 0, 0]]]]), 1), true);
        assert_eq!(check(json!([[-1, [[1, 0, 0], [0, 0, 0]]]]), 2), false);
        assert_eq!(check(json!([[-1, [[1, 0, 0]]]]), 0), false);
    }

    #[test]
    fn occupancy_checks_every_step_and_ignores_defeated_groups_and_own_members() {
        let packet = json!([
            13852,
            hex::encode(movement_packet(-1, &[[0, 0, 0], [1, 0, 0], [2, 0, 0]]).unwrap())
        ]);
        let input = json!({"packets":[packet],"members":[actor(-1,[0,0,0])],"players":[],
            "groups":[{"status":"defeated","members":[actor(-2,[1,0,0])]},
                      {"status":"alive","members":[actor(-1,[1,0,0])]}]});
        assert_eq!(call("geometry.path_occupied", &input).unwrap(), false);
        let mut blocked = input;
        blocked["players"] = json!([actor(5, [1, 0, 0])]);
        assert_eq!(call("geometry.path_occupied", &blocked).unwrap(), true);
    }

    #[test]
    fn batched_habitat_checks_preserve_exact_height_and_scope_policy() {
        let key = register_points(&[json!([1, 0, 0]), json!([2, 0, 3])], "surfaces").unwrap();
        let allowed = |paths: Value| {
            call(
                "geometry.surface_paths_allowed",
                &json!({"key":key,"paths":paths}),
            )
            .unwrap()
        };
        assert_eq!(
            allowed(json!([[-1, [[1, 0, 0], [2, 0, 3]]], [-2, []]])),
            true
        );
        assert_eq!(allowed(json!([[-1, [[1, 0, 0], [2, 0, 0]]]])), false);
        let habitats = call(
            "geometry.load_habitats",
            &json!({"raw": "[{\"map_id\":1,\"regions\":[{}]},{\"map_id\":2,\"regions\":[]}]"}),
        )
        .unwrap();
        let tracked = |map: i64, instance: i64| {
            call(
                "geometry.habitat_tracked",
                &json!({"key":habitats["key"],"map_id":map,"instance_id":instance}),
            )
            .unwrap()
        };
        assert_eq!(tracked(1, 0), true);
        assert_eq!(tracked(1, 9), false);
        assert_eq!(tracked(2, 0), false);
    }

    #[test]
    fn native_bulk_guard_requires_exact_packet_cas_identity() {
        let packet = json!([
            13852,
            hex::encode(movement_packet(-1, &[[0, 0, 0], [1, 0, 0]]).unwrap())
        ]);
        let row = json!({"group_id":1,"expected_members":[actor(-1,[0,0,0])],
            "moved_members":[actor(-1,[1,0,0])],"packets":[packet]});
        assert_eq!(
            validate_bulk_move_json(&row).unwrap()["cells"],
            json!([[1, 0, 0]])
        );
        let mut bad = row;
        bad["moved_members"][0]["x"] = json!(2);
        assert!(validate_bulk_move_json(&bad).is_err());
    }
}
