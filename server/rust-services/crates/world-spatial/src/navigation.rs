//! Exploration route identity, scene partition schedules, and spatial admission.
//!
//! Quest, inventory and dungeon progression adapters supply their already
//! authorized cell sets. These kernels do not introduce general terrain or mob
//! collision restrictions into ordinary client-owned walking animation.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

type Point = [i64; 3];
type Region = [i64; 2];
type Result<T> = std::result::Result<T, String>;
const MAX_HANDLES: usize = 100_000;
const MAX_SCENE_STEPS: usize = 256;

fn error(message: &str) -> String {
    message.to_owned()
}

fn integer(value: &Value) -> Result<i64> {
    value
        .as_i64()
        .ok_or_else(|| error("Expected an integral navigation coordinate"))
}

fn numeric_integer(value: &Value) -> Option<i64> {
    value.as_i64().or_else(|| {
        value
            .as_f64()
            .filter(|n| {
                n.is_finite()
                    && n.fract() == 0.0
                    && *n >= i64::MIN as f64
                    && *n < -(i64::MIN as f64)
            })
            .map(|n| n as i64)
    })
}

fn point(value: &Value) -> Result<Point> {
    let values = if let Some(row) = value.as_array() {
        if row.len() != 3 {
            return Err(error("Invalid navigation point width"));
        }
        [&row[0], &row[1], &row[2]]
    } else {
        [&value["x"], &value["y"], &value["z"]]
    };
    Ok([
        integer(values[0])?,
        integer(values[1])?,
        integer(values[2])?,
    ])
}

fn region(value: &Value) -> Result<Region> {
    let row = value
        .as_array()
        .filter(|r| r.len() == 2)
        .ok_or_else(|| error("Invalid navigation region"))?;
    Ok([integer(&row[0])?, integer(&row[1])?])
}

fn points(value: &Value) -> Result<BTreeSet<Point>> {
    value
        .as_array()
        .ok_or_else(|| error("Missing navigation points"))?
        .iter()
        .map(point)
        .collect()
}

fn regions(value: &Value) -> Result<BTreeSet<Region>> {
    value
        .as_array()
        .ok_or_else(|| error("Missing navigation regions"))?
        .iter()
        .map(region)
        .collect()
}

fn walk(request: &Value, verify_endpoint: bool) -> Result<Vec<Point>> {
    let mut current = point(&request["start_position"])?;
    let steps = request["steps"]
        .as_array()
        .ok_or_else(|| error("Missing navigation steps"))?;
    let mut result = Vec::with_capacity(steps.len() + 1);
    result.push(current);
    for step in steps {
        for (index, key) in ["dx", "dy", "dz"].into_iter().enumerate() {
            current[index] = current[index]
                .checked_add(integer(&step[key])?)
                .ok_or_else(|| error("Navigation coordinate overflow"))?;
        }
        result.push(current);
    }
    if verify_endpoint && current != point(&request["end_position"])? {
        return Err(error("Route endpoint mismatch"));
    }
    Ok(result)
}

fn chunk(position: &Value) -> Result<Region> {
    let (x, y) = if let Some(row) = position.as_array() {
        if row.len() < 2 {
            return Err(error("Invalid scene position"));
        }
        (&row[0], &row[1])
    } else {
        (&position["x"], &position["y"])
    };
    fn axis(value: &Value) -> Result<i64> {
        if let Some(value) = value.as_i64() {
            return Ok(value.div_euclid(18));
        }
        let value = value
            .as_f64()
            .filter(|n| n.is_finite())
            .ok_or_else(|| error("Invalid scene coordinate"))?;
        let divided = (value / 18.0).floor();
        if divided < i64::MIN as f64 || divided >= -(i64::MIN as f64) {
            return Err(error("Scene coordinate overflow"));
        }
        Ok(divided as i64)
    }
    Ok([axis(x)?, axis(y)?])
}

fn neighborhood(center: Region) -> Result<BTreeSet<Region>> {
    let mut result = BTreeSet::new();
    for dx in -1_i64..=1 {
        for dy in -1_i64..=1 {
            result.insert([
                center[0]
                    .checked_add(dx)
                    .ok_or_else(|| error("Scene coordinate overflow"))?,
                center[1]
                    .checked_add(dy)
                    .ok_or_else(|| error("Scene coordinate overflow"))?,
            ]);
        }
    }
    Ok(result)
}

#[derive(Default)]
struct Scene {
    identity: Option<Region>,
    pending: Vec<(f64, BTreeSet<Region>)>,
    last_regions: BTreeSet<Region>,
}

impl Scene {
    fn clear(&mut self) {
        *self = Self::default();
    }

    fn add_pending(&mut self, due: f64, regions: BTreeSet<Region>) {
        if let Some((_, existing)) = self.pending.iter_mut().find(|(time, _)| *time == due) {
            existing.extend(regions);
        } else {
            self.pending.push((due, regions));
        }
    }

    fn arm(&mut self, identity: Region, steps: &[Value], now: f64) -> Result<()> {
        if !(1..=MAX_SCENE_STEPS).contains(&steps.len()) || !now.is_finite() {
            return Err(error("Invalid accepted scene movement schedule"));
        }
        let centers = steps.iter().map(chunk).collect::<Result<Vec<_>>>()?;
        let mut relevant = BTreeSet::new();
        for center in &centers {
            relevant.extend(neighborhood(*center)?);
        }
        let mut retained = Vec::new();
        if self.identity == Some(identity) {
            for (due, regions) in &self.pending {
                let selected = regions
                    .intersection(&relevant)
                    .copied()
                    .collect::<BTreeSet<_>>();
                if !selected.is_empty() {
                    retained.push((
                        if *due <= now {
                            due.min(now.floor())
                        } else {
                            *due
                        },
                        selected,
                    ));
                }
            }
        }
        self.pending.clear();
        for (due, regions) in retained {
            self.add_pending(due, regions);
        }
        self.identity = Some(identity);
        let destination = neighborhood(*centers.last().expect("nonempty scene route"))?;
        let ticks = ((steps.len() as f64 * 0.5) + 3.0).ceil() as usize;
        for tick in 1..=ticks {
            let elapsed = tick as f64;
            let index = ((elapsed / 0.5) as usize)
                .saturating_sub(1)
                .min(centers.len() - 1);
            let mut regions = neighborhood(centers[index])?;
            regions.extend(&destination);
            self.add_pending(now.ceil() + elapsed, regions);
        }
        Ok(())
    }

    fn poll(&mut self, identity: Region, now: f64) -> Result<BTreeSet<Region>> {
        if !now.is_finite() {
            return Err(error("Invalid scene poll clock"));
        }
        self.last_regions.clear();
        if self.identity != Some(identity) {
            self.clear();
            return Ok(BTreeSet::new());
        }
        let mut pending = Vec::new();
        for (due, regions) in self.pending.drain(..) {
            if due <= now {
                self.last_regions.extend(regions);
            } else {
                pending.push((due, regions));
            }
        }
        self.pending = pending;
        Ok(self.last_regions.clone())
    }

    fn state(&self) -> Value {
        json!({"identity":self.identity,"pending":self.pending,"last_regions":self.last_regions})
    }
}

#[derive(Default)]
pub struct NavigationState {
    next_handle: u64,
    routes: HashMap<u64, BTreeSet<Point>>,
    scenes: HashMap<u64, Scene>,
}

impl NavigationState {
    pub fn new() -> Self {
        Self::default()
    }

    fn allocate(&mut self) -> Result<u64> {
        if self.routes.len() + self.scenes.len() >= MAX_HANDLES {
            return Err(error("Navigation handle capacity reached"));
        }
        self.next_handle = self
            .next_handle
            .checked_add(1)
            .ok_or_else(|| error("Navigation handle space exhausted"))?;
        Ok(self.next_handle)
    }

    fn handle(args: &Value) -> Result<u64> {
        args["handle"]
            .as_u64()
            .filter(|id| *id > 0)
            .ok_or_else(|| error("Invalid navigation handle"))
    }

    pub fn call(&mut self, operation: &str, args: &Value) -> Result<Value> {
        let operation = operation.strip_prefix("navigation.").unwrap_or(operation);
        match operation {
            "route_new" => {
                let position = point(&args["position"])?;
                let handle = self.allocate()?;
                self.routes.insert(handle, BTreeSet::from([position]));
                Ok(json!({"handle":handle}))
            }
            "route_key" => Ok(json!(point(&args["position"])?)),
            "route_points" => Ok(json!(self
                .routes
                .get(&Self::handle(args)?)
                .ok_or_else(|| error("Unknown movement route"))?)),
            "route_validate" => {
                let route = self
                    .routes
                    .get(&Self::handle(args)?)
                    .ok_or_else(|| error("Unknown movement route"))?;
                let request = &args["request"];
                if !route.contains(&point(&request["start_position"])?) {
                    return Err(error("Route starts outside the previous approved path"));
                }
                Ok(json!(walk(request, true)?
                    .into_iter()
                    .collect::<BTreeSet<_>>()))
            }
            "route_commit" => {
                let approved = points(&args["points"])?;
                let route = self
                    .routes
                    .get_mut(&Self::handle(args)?)
                    .ok_or_else(|| error("Unknown movement route"))?;
                *route = approved;
                Ok(Value::Null)
            }
            "route_drop" => Ok(json!(self.routes.remove(&Self::handle(args)?).is_some())),
            "scene_new" => {
                let handle = self.allocate()?;
                self.scenes.insert(handle, Scene::default());
                Ok(json!({"handle":handle}))
            }
            "scene_state" => Ok(self
                .scenes
                .get(&Self::handle(args)?)
                .ok_or_else(|| error("Unknown scene schedule"))?
                .state()),
            "scene_clear" => {
                self.scenes
                    .get_mut(&Self::handle(args)?)
                    .ok_or_else(|| error("Unknown scene schedule"))?
                    .clear();
                Ok(Value::Null)
            }
            "scene_arm" | "scene_poll" => {
                let identity = [integer(&args["map_id"])?, integer(&args["instance_id"])?];
                let now = args["now"]
                    .as_f64()
                    .ok_or_else(|| error("Invalid scene clock"))?;
                let scene = self
                    .scenes
                    .get_mut(&Self::handle(args)?)
                    .ok_or_else(|| error("Unknown scene schedule"))?;
                if operation == "scene_arm" {
                    let steps = args["steps"]
                        .as_array()
                        .ok_or_else(|| error("Missing scene route"))?;
                    scene.arm(identity, steps, now)?;
                    Ok(Value::Null)
                } else {
                    Ok(json!({"regions":scene.poll(identity, now)?}))
                }
            }
            "scene_drop" => Ok(json!(self.scenes.remove(&Self::handle(args)?).is_some())),
            "chunk" => Ok(json!(chunk(&args["position"])?)),
            "neighborhood" => Ok(json!(neighborhood(region(&args["center"])?)?)),
            "normalize_regions" => Ok(json!(regions(&args["regions"])?)),
            "select_chunk" => {
                let center = region(&args["center"])?;
                let positions = args["positions"]
                    .as_array()
                    .ok_or_else(|| error("Missing scene object positions"))?;
                let mut selected = Vec::new();
                for (index, position) in positions.iter().enumerate() {
                    if chunk(position)? == center {
                        selected.push(index);
                    }
                }
                Ok(json!(selected))
            }
            "approach" => {
                let approved = self
                    .routes
                    .get(&Self::handle(args)?)
                    .ok_or_else(|| error("Unknown movement route"))?;
                Ok(json!(approach(approved, args)))
            }
            "blocked_columns" => blocked_columns(args),
            "allowed_cells" => allowed_cells(args),
            "closed_doors" => closed_doors(args),
            "directed_path" | "topology_register" | "topology_lookup" => {
                immutable_call(operation, args)
            }
            "optional_cells" => optional_cells(args),
            "locked_scene" => locked_scene(args),
            "boat_path" => boat_path(args),
            _ => Err(error("Unknown navigation operation")),
        }
    }
}

fn approach(approved: &BTreeSet<Point>, args: &Value) -> bool {
    let character = &args["character"];
    let source = &args["source"];
    let actual_instance = match character.get("instance_id") {
        None => Some(0),
        Some(value) => value.as_i64(),
    };
    if actual_instance != args["instance_id"].as_i64()
        || character.get("map_id") != args.get("map_id")
        || source.get("map_id") != args.get("map_id")
    {
        return false;
    }
    let mask = source
        .get("approach_mask")
        .map(Value::as_i64)
        .unwrap_or(Some(0));
    let Some(mask) = mask.filter(|m| (0..=32767).contains(m)) else {
        return false;
    };
    if mask != 0 {
        if !source["approach_orientation"]
            .as_i64()
            .is_some_and(|n| (0..8).contains(&n))
        {
            return false;
        }
        let mut candidates = BTreeSet::new();
        if let Some(rows) = source.get("approach_positions") {
            let Some(rows) = rows.as_array() else {
                return false;
            };
            for row in rows {
                let p = [
                    numeric_integer(&row["x"]),
                    numeric_integer(&row["y"]),
                    numeric_integer(&row["z"]),
                ];
                let [Some(x), Some(y), Some(z)] = p else {
                    return false;
                };
                candidates.insert([x, y, z]);
            }
        }
        if approved.iter().any(|p| candidates.contains(p)) {
            return true;
        }
        if approved.is_empty() {
            let p = [
                numeric_integer(&character["x"]),
                numeric_integer(&character["y"]),
                numeric_integer(&character["z"]),
            ];
            if let [Some(x), Some(y), Some(z)] = p {
                return candidates.contains(&[x, y, z]);
            }
        }
        false
    } else {
        let (Some(x), Some(y)) = (numeric_integer(&source["x"]), numeric_integer(&source["y"]))
        else {
            return false;
        };
        approved.iter().any(|p| p[0] == x && p[1] == y)
            || (approved.is_empty()
                && numeric_integer(&character["x"]) == Some(x)
                && numeric_integer(&character["y"]) == Some(y))
    }
}

pub fn blocked_columns(args: &Value) -> Result<Value> {
    let blocked = regions(&args["blocked"])?;
    let path = walk(&args["request"], false)?;
    for p in path.iter().skip(1) {
        if args["exclude_start_point"].as_bool() == Some(true) && p == &path[0] {
            continue;
        }
        if blocked.contains(&[p[0], p[1]]) {
            return Err(args
                .get("error")
                .and_then(Value::as_str)
                .unwrap_or("Movement crosses an occupied native column")
                .to_owned());
        }
    }
    Ok(json!(path.last().expect("route has start")))
}

pub fn allowed_cells(args: &Value) -> Result<Value> {
    let allowed = points(&args["cells"])?;
    let path = walk(&args["request"], false)?;
    if !allowed.contains(&path[0]) {
        return Err(args
            .get("start_error")
            .and_then(Value::as_str)
            .unwrap_or("Movement starts outside admitted native terrain")
            .to_owned());
    }
    if path.iter().skip(1).any(|p| !allowed.contains(p)) {
        return Err(args
            .get("step_error")
            .and_then(Value::as_str)
            .unwrap_or("Movement leaves admitted native terrain")
            .to_owned());
    }
    Ok(json!(path.last().expect("route has start")))
}

pub fn closed_doors(args: &Value) -> Result<Value> {
    let blocked = points(&args["blocked"])?;
    let path = walk(&args["request"], false)?;
    for pair in path.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        if blocked.contains(&b) {
            return Err(error("Movement crosses a closed ordinary door"));
        }
        if b[0].abs_diff(a[0]) == 1 && b[1].abs_diff(a[1]) == 1 {
            for z in [a[2], b[2]] {
                if blocked.contains(&[b[0], a[1], z]) || blocked.contains(&[a[0], b[1], z]) {
                    return Err(error("Diagonal movement crosses a closed ordinary door"));
                }
            }
        }
    }
    Ok(json!(path.last().expect("route has start")))
}

struct Topology {
    graph: Arc<crate::geometry::Geometry>,
    allowed: Option<BTreeSet<Point>>,
}

impl Topology {
    fn contains(&self, p: &Point) -> bool {
        match &self.allowed {
            Some(cells) => cells.contains(p),
            None => self.graph.cells.binary_search(p).is_ok(),
        }
    }
}

#[derive(Default)]
struct TopologyCache {
    rows: VecDeque<(String, String, Arc<Topology>, usize)>,
    bytes: usize,
}
static TOPOLOGIES: OnceLock<Mutex<TopologyCache>> = OnceLock::new();
const TOPOLOGY_CACHE_BYTES: usize = 64 * 1024 * 1024;

fn topology_lookup(authority: &str) -> Option<String> {
    let mut cache = TOPOLOGIES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    let index = cache.rows.iter().position(|r| r.0 == authority)?;
    let row = cache.rows.remove(index)?;
    let key = row.1.clone();
    cache.rows.push_back(row);
    Some(key)
}

fn topology_key(key: &str) -> Result<Arc<Topology>> {
    let mut cache = TOPOLOGIES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    let index = cache
        .rows
        .iter()
        .position(|r| r.1 == key)
        .ok_or_else(|| error("Navigation topology handle expired"))?;
    let row = cache.rows.remove(index).expect("present topology");
    let topology = Arc::clone(&row.2);
    cache.rows.push_back(row);
    Ok(topology)
}

/// Immutable geometry work bypasses the actor Engine mutex in the FFI owner.
pub fn immutable_call(operation: &str, args: &Value) -> Result<Value> {
    match operation.strip_prefix("navigation.").unwrap_or(operation) {
        "topology_lookup" => {
            let authority = args["authority"]
                .as_str()
                .ok_or_else(|| error("Missing navigation topology authority"))?;
            Ok(json!({"key":topology_lookup(authority)}))
        }
        "topology_register" => {
            let authority = args["authority"]
                .as_str()
                .filter(|s| !s.is_empty() && s.len() <= 1024)
                .ok_or_else(|| error("Missing navigation topology authority"))?;
            let graph_key =
                crate::geometry::register_graph(args, authority).map_err(|e| e.to_string())?;
            let graph = crate::geometry::lookup_graph(&graph_key).map_err(|e| e.to_string())?;
            let allowed = match args.get("allowed_cells") {
                Some(value) => {
                    let cells = points(value)?;
                    if !cells.iter().all(|p| graph.cells.binary_search(p).is_ok()) {
                        return Err(error("Navigation admitted cells leave native geometry"));
                    }
                    Some(cells)
                }
                None => None,
            };
            let mut digest = Sha256::new();
            digest.update(authority.as_bytes());
            digest.update([0]);
            digest.update(graph.digest);
            if let Some(cells) = &allowed {
                digest.update([1]);
                for p in cells {
                    for c in p {
                        digest.update(c.to_be_bytes());
                    }
                }
            } else {
                digest.update([0]);
            }
            let key = hex::encode(digest.finalize());
            // Charge shared graph allocations too: a topology may outlive a graph-cache eviction.
            let bytes = graph.cells.capacity() * 24
                + graph.adjacent.capacity() * 128
                + graph
                    .adjacent
                    .values()
                    .map(|v| v.capacity() * 24)
                    .sum::<usize>()
                + allowed.as_ref().map_or(0, |v| v.len() * 96)
                + authority.len()
                + 512;
            if bytes > TOPOLOGY_CACHE_BYTES {
                return Err(error("Navigation topology exceeds native cache budget"));
            }
            let topology = Arc::new(Topology { graph, allowed });
            let mut cache = TOPOLOGIES
                .get_or_init(Default::default)
                .lock()
                .unwrap_or_else(|e| e.into_inner());
            if let Some(index) = cache.rows.iter().position(|r| r.0 == authority) {
                let old = cache.rows.remove(index).expect("present topology");
                cache.bytes -= old.3;
            }
            while cache.bytes + bytes > TOPOLOGY_CACHE_BYTES || cache.rows.len() >= 256 {
                if let Some(old) = cache.rows.pop_front() {
                    cache.bytes -= old.3;
                } else {
                    break;
                }
            }
            cache.bytes += bytes;
            cache
                .rows
                .push_back((authority.to_owned(), key.clone(), topology, bytes));
            Ok(json!({"key":key}))
        }
        "directed_path" => directed_path(args),
        _ => Err(error("Unknown immutable navigation operation")),
    }
}

pub fn directed_path(args: &Value) -> Result<Value> {
    let topology = if let Some(key) = args["topology_key"].as_str() {
        topology_key(key)?
    } else {
        // Unattested synthetic callers receive an uncached graph, never a stale identity alias.
        let allowed = points(&args["cells"])?;
        let mut all = allowed.clone();
        let mut adjacent: HashMap<Point, Vec<Point>> = HashMap::new();
        for edge in args["edges"]
            .as_array()
            .ok_or_else(|| error("Missing native directed edges"))?
        {
            let edge = edge
                .as_array()
                .filter(|e| e.len() == 2)
                .ok_or_else(|| error("Invalid native directed edge"))?;
            let (a, b) = (point(&edge[0])?, point(&edge[1])?);
            all.insert(a);
            all.insert(b);
            adjacent.entry(a).or_default().push(b);
        }
        let graph = crate::geometry::finish_geometry(all.into_iter().collect(), adjacent)
            .map_err(|e| e.to_string())?;
        Arc::new(Topology {
            graph: Arc::new(graph),
            allowed: Some(allowed),
        })
    };
    let blocked = points(&args["blocked"])?;
    let path = walk(&args["request"], false)?;
    let start = path[0];
    if !topology.contains(&start) || blocked.contains(&start) {
        return Err(error(
            "Dungeon movement starts outside unlocked native terrain",
        ));
    }
    for pair in path.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        if !topology.contains(&b) || blocked.contains(&b) {
            return Err(error("Dungeon movement crosses a locked room gate"));
        }
        if b[0].abs_diff(a[0]) == 1 && b[1].abs_diff(a[1]) == 1 {
            for xy in [[b[0], a[1]], [a[0], b[1]]] {
                if !topology
                    .graph
                    .adjacent
                    .get(&a)
                    .into_iter()
                    .flatten()
                    .any(|middle| {
                        middle[..2] == xy
                            && topology.contains(middle)
                            && !blocked.contains(middle)
                            && topology.graph.edges.contains(&(a, *middle))
                            && topology.graph.edges.contains(&(*middle, b))
                    })
                {
                    return Err(error("Dungeon diagonal bypasses native gate collision"));
                }
            }
        } else if !topology.graph.edges.contains(&(a, b)) {
            return Err(error("Dungeon movement leaves native exploration edges"));
        }
    }
    if *path.last().expect("route has start") != point(&args["request"]["end_position"])? {
        return Err(error("Dungeon movement endpoint mismatch"));
    }
    Ok(json!(path.last().expect("route has start")))
}

pub fn optional_cells(args: &Value) -> Result<Value> {
    let blocked = points(&args["optional_cells"])?;
    let path = walk(&args["request"], false)?;
    let mut inside = blocked.contains(&path[0]);
    for p in path.iter().skip(1) {
        let next = blocked.contains(p);
        if next && !inside {
            return Err(error("Optional native access is unresolved"));
        }
        inside = next;
    }
    Ok(Value::Null)
}

pub fn locked_scene(args: &Value) -> Result<Value> {
    let blocked = points(&args["blocked"])?;
    let path = walk(&args["request"], false)?;
    if blocked.contains(&path[0]) {
        return Err(error("Native scene walking starts inside its locked gate"));
    }
    if path.iter().skip(1).any(|p| blocked.contains(p)) {
        return Err(error(
            "Open the native scene entrance before crossing its gate",
        ));
    }
    Ok(Value::Null)
}

pub fn boat_path(args: &Value) -> Result<Value> {
    let rows = args["sources"]
        .as_array()
        .ok_or_else(|| error("Missing Boat source authority"))?;
    let mut sources = HashMap::new();
    for row in rows {
        sources.insert(point(&row["source"])?, points(&row["targets"])?);
    }
    let path = walk(&args["request"], false)?;
    let mut checked = false;
    for pair in path.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        if sources.contains_key(&b) {
            return Err(error(
                "Native Boat arrival is not an ordinary movement destination",
            ));
        }
        if let Some(targets) = sources.get(&a) {
            if !checked {
                let Some(geometry) = args.get("geometry") else {
                    return Ok(json!({"needs_geometry":true}));
                };
                if geometry.get("map_id") != args.get("map_id")
                    || !targets.is_subset(&points(&geometry["cells"])?)
                {
                    return Err(error("Native Boat departure terrain changed"));
                }
                checked = true;
            }
            if !targets.contains(&b) {
                return Err(error(
                    "Movement does not follow an original native Boat departure",
                ));
            }
        }
    }
    Ok(json!({"needs_geometry":false}))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn route(start: Point, steps: Vec<Point>) -> Value {
        let mut end = start;
        let ss = steps
            .iter()
            .map(|d| {
                for i in 0..3 {
                    end[i] += d[i];
                }
                json!({"dx":d[0],"dy":d[1],"dz":d[2]})
            })
            .collect::<Vec<_>>();
        json!({"start_position":{"x":start[0],"y":start[1],"z":start[2]},"end_position":{"x":end[0],"y":end[1],"z":end[2]},"steps":ss})
    }

    #[test]
    fn immutable_topology_keys_include_content_and_admitted_subset() {
        let source = json!({"authority":"navigation-parity-topology", "cells":[[0,0,0],[1,0,0],[9,9,0]],"edges":[[[0,0,0],[1,0,0]]]});
        let first = immutable_call("navigation.topology_register", &source).unwrap()["key"]
            .as_str()
            .unwrap()
            .to_owned();
        assert_eq!(
            immutable_call(
                "topology_lookup",
                &json!({"authority":"navigation-parity-topology"})
            )
            .unwrap()["key"],
            first
        );
        let request = route([0, 0, 0], vec![[1, 0, 0]]);
        assert_eq!(
            directed_path(&json!({"topology_key":first,"request":request,"blocked":[]})).unwrap(),
            json!([1, 0, 0])
        );
        let mut restricted = source.clone();
        restricted["allowed_cells"] = json!([[0, 0, 0], [9, 9, 0]]);
        let second = immutable_call("topology_register", &restricted).unwrap()["key"]
            .as_str()
            .unwrap()
            .to_owned();
        assert_ne!(first, second);
        assert!(
            directed_path(&json!({"topology_key":second,"request":request,"blocked":[]})).is_err()
        );
        assert_eq!(
            directed_path(&json!({"topology_key":first,"request":request,"blocked":[]}))
                .unwrap_err(),
            "Navigation topology handle expired"
        );
        assert_eq!(
            directed_path(
                &json!({"topology_key":second,"request":route([9,9,0],vec![]),"blocked":[]})
            )
            .unwrap(),
            json!([9, 9, 0])
        );
    }

    #[test]
    fn approved_route_redirects_preserve_intermediate_heights_and_reject_abandoned_start() {
        let mut state = NavigationState::new();
        let handle = state
            .call("route_new", &json!({"position":[-12,-8,-1]}))
            .unwrap()["handle"]
            .clone();
        let first = route([-12, -8, -1], vec![[-1, 0, 0]; 5]);
        let approved = state
            .call("route_validate", &json!({"handle":handle,"request":first}))
            .unwrap();
        state
            .call("route_commit", &json!({"handle":handle,"points":approved}))
            .unwrap();
        let next = route([-14, -8, -1], vec![[0, -1, 1]; 2]);
        let approved = state
            .call("route_validate", &json!({"handle":handle,"request":next}))
            .unwrap();
        state
            .call("route_commit", &json!({"handle":handle,"points":approved}))
            .unwrap();
        assert!(state
            .call("route_validate", &json!({"handle":handle,"request":first}))
            .is_err());
    }

    #[test]
    fn rejected_endpoint_never_changes_approved_route() {
        let mut s = NavigationState::new();
        let h = s.call("route_new", &json!({"position":[8,32,-1]})).unwrap()["handle"].clone();
        let before = s.call("route_points", &json!({"handle":h})).unwrap();
        let mut request = route([8, 32, -1], vec![[0, 1, 1]; 6]);
        request["end_position"]["z"] = json!(0);
        assert_eq!(
            s.call("route_validate", &json!({"handle":h,"request":request}))
                .unwrap_err(),
            "Route endpoint mismatch"
        );
        assert_eq!(
            s.call("route_points", &json!({"handle":h})).unwrap(),
            before
        );
    }

    #[test]
    fn partitions_floor_negative_integral_and_fractional_positions() {
        for (x, want) in [(-19, -2), (-18, -1), (-1, -1), (0, 0), (17, 0), (18, 1)] {
            assert_eq!(chunk(&json!([x, x])).unwrap(), [want, want]);
        }
        assert_eq!(chunk(&json!([-18.5, -0.1])).unwrap(), [-2, -1]);
        assert_eq!(neighborhood([0, 0]).unwrap().len(), 9);
    }

    #[test]
    fn scene_deadlines_redirects_scope_and_tail_match_original() {
        let mut scene = Scene::default();
        scene.arm([527, 1], &[json!([-219, -40, 0])], 10.0).unwrap();
        assert!(scene.poll([527, 1], 10.99).unwrap().is_empty());
        assert!(!scene.poll([527, 1], 11.0).unwrap().is_empty());
        assert!(!scene.poll([527, 1], 14.0).unwrap().is_empty());
        assert!(scene.pending.is_empty());
        scene.arm([527, 1], &[json!([0, 0, 0])], 20.0).unwrap();
        assert!(scene.poll([527, 2], 21.0).unwrap().is_empty());
        assert!(scene.identity.is_none());
    }

    #[test]
    fn redirects_keep_due_relevant_regions_and_bounded_future_replays() {
        let mut scene = Scene::default();
        for n in 0..100 {
            scene
                .arm(
                    [527, 0],
                    &[json!([0, 0, 0]), json!([1, 1, 0])],
                    n as f64 / 100.0,
                )
                .unwrap();
        }
        assert!(scene.pending.len() <= 5);
        scene.arm([527, 0], &[json!([0, 0, 0])], 2.1).unwrap();
        assert!(!scene.poll([527, 0], 2.1).unwrap().is_empty());
        scene
            .arm([527, 0], &vec![json!([0, 0, 0]); 256], 3.0)
            .unwrap();
        assert!(scene.pending.len() <= 132);
        assert!(scene.arm([527, 0], &[], 0.0).is_err());
        assert!(scene.arm([527, 0], &[json!([0, 0, 0])], f64::NAN).is_err());
    }

    #[test]
    fn teleporter_masks_and_empty_approved_route_preserve_owned_position_rules() {
        let mut s = NavigationState::new();
        let h = s
            .call("route_new", &json!({"position":[-245,-89,0]}))
            .unwrap()["handle"]
            .clone();
        let mut a = json!({"handle":h,"map_id":527,"instance_id":0,"character":{"map_id":527},"source":{"map_id":527,"x":-245,"y":-90,"approach_mask":1,"approach_orientation":3,"approach_positions":[{"x":-245.0,"y":-89.0,"z":0.0}]}});
        assert_eq!(s.call("approach", &a).unwrap(), json!(true));
        a["source"]["approach_mask"] = json!(true);
        assert_eq!(s.call("approach", &a).unwrap(), json!(false));
        a["source"]["approach_mask"] = json!(1);
        a["source"]["approach_orientation"] = json!(false);
        assert_eq!(s.call("approach", &a).unwrap(), json!(false));
        s.call("route_commit", &json!({"handle":h,"points":[]}))
            .unwrap();
        a["source"]["approach_orientation"] = json!(3);
        a["character"] = json!({"map_id":527,"x":-245,"y":-89,"z":0});
        assert_eq!(s.call("approach", &a).unwrap(), json!(true));
        a["character"]["instance_id"] = json!(9);
        assert_eq!(s.call("approach", &a).unwrap(), json!(false));
    }

    #[test]
    fn ordinary_closed_door_allows_egress_but_rejects_diagonal_corners_at_both_heights() {
        let r = route([0, 0, 0], vec![[1, 1, 1]]);
        for b in [json!([[1, 0, 0]]), json!([[0, 1, 1]]), json!([[1, 1, 1]])] {
            assert!(closed_doors(&json!({"request":r,"blocked":b})).is_err());
        }
        assert_eq!(
            closed_doors(&json!({"request":r,"blocked":[[0,0,0]]})).unwrap(),
            json!([1, 1, 1])
        );
    }

    #[test]
    fn physical_diagonal_requires_both_directed_cardinal_alternatives() {
        let mut a = json!({"request":route([0,0,0],vec![[1,1,1]]),"cells":[[0,0,0],[1,0,1],[0,1,0],[1,1,1]],"blocked":[],"edges":[[[0,0,0],[1,0,1]],[[1,0,1],[1,1,1]],[[0,0,0],[0,1,0]],[[0,1,0],[1,1,1]]]});
        assert_eq!(directed_path(&a).unwrap(), json!([1, 1, 1]));
        a["edges"].as_array_mut().unwrap().pop();
        assert!(directed_path(&a).is_err());
    }

    #[test]
    fn optional_and_column_boundaries_preserve_existing_occupant_egress() {
        assert!(optional_cells(
            &json!({"request":route([1,0,0],vec![[1,0,0]]),"optional_cells":[[1,0,0]]})
        )
        .is_ok());
        assert!(optional_cells(
            &json!({"request":route([0,0,0],vec![[1,0,0]]),"optional_cells":[[1,0,0]]})
        )
        .is_err());
        assert!(blocked_columns(
            &json!({"request":route([1,0,0],vec![[1,0,0]]),"blocked":[[1,0]]})
        )
        .is_ok());
        assert!(blocked_columns(
            &json!({"request":route([0,0,0],vec![[1,0,1]]),"blocked":[[1,0]]})
        )
        .is_err());
    }

    #[test]
    fn source_only_boat_points_never_acquire_an_incoming_edge() {
        let source = json!([{"source":[0,0,0],"targets":[[1,0,0]]}]);
        let geometry = json!({"map_id":1,"cells":[[1,0,0]]});
        assert_eq!(
            boat_path(&json!({"request":route([0,0,0],vec![[1,0,0]]),"sources":source})).unwrap(),
            json!({"needs_geometry":true})
        );
        assert!(boat_path(&json!({"request":route([0,0,0],vec![[1,0,0]]),"sources":source,"map_id":1,"geometry":geometry})).is_ok());
        assert!(
            boat_path(&json!({"request":route([1,0,0],vec![[-1,0,0]]),"sources":source})).is_err()
        );
        assert!(boat_path(&json!({"request":route([0,0,0],vec![[0,1,0]]),"sources":source,"map_id":1,"geometry":geometry})).is_err());
    }
}
