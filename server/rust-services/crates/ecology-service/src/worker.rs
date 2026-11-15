//! Bounded ecology scheduling and durable delivery. World retains mutation authority.
use std::collections::{BTreeMap, HashSet};
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};

use anyhow::{anyhow, bail, Context as _, Result};
use serde::Serialize;
use serde_json::{json, Value};
use tokio::sync::{watch, Mutex, Semaphore};

pub use crate::protocol::validate_query;
use crate::protocol::{proposal, DOMAINS, MAX_BODY_BYTES, MAX_PROPOSALS, SCHEMA_VERSION};
use crate::repository::Repository;
use crate::world_client::WorldClient;
use crate::{planners, protocol, Context};

pub const MAX_PENDING: usize = 4096;
const SOFT_PENDING: usize = 512;
const RESERVED_GROWTH: usize = 16;
const DRAIN_BUDGET: Duration = Duration::from_millis(200);
const MAX_DRAIN_BATCHES: usize = 16;

const STAGE_KEYS: [&str; 11] = [
    "plants",
    "mobs",
    "weather",
    "population",
    "bonuses",
    "interactive",
    "reserved_growth",
    "world_snapshot",
    "queue",
    "world_apply",
    "delivery_validation",
];

#[derive(Clone, Default, Serialize)]
struct StageTiming {
    count: u64,
    last_ms: f64,
    max_ms: f64,
    total_ms: f64,
}

#[derive(Clone, Default, Serialize)]
struct Counters {
    ticks: u64,
    planned: u64,
    delivered: u64,
    stale: u64,
    retries: u64,
    deferred: u64,
}

struct State {
    last_progress: Instant,
    startup_complete: bool,
    last_error: Option<&'static str>,
    domain_errors: BTreeMap<String, &'static str>,
    domain_planning_ticks: BTreeMap<String, u64>,
    stage_timings: BTreeMap<&'static str, StageTiming>,
    last_snapshot: Option<Value>,
    snapshot_at: Option<Instant>,
    enabled: bool,
    counters: Counters,
    pending: usize,
    retry_totals: Value,
    last_tick_seconds: f64,
    last_queue_log: Option<Instant>,
    last_locations: Value,
    last_wander: Option<i64>,
    last_reserved_growth: Option<Instant>,
    last_mobs_now_ms: Option<i64>,
    last_epoch: Option<String>,
}

impl State {
    fn new() -> Self {
        Self {
            last_progress: Instant::now(),
            startup_complete: false,
            last_error: None,
            domain_errors: BTreeMap::new(),
            domain_planning_ticks: BTreeMap::new(),
            stage_timings: BTreeMap::new(),
            last_snapshot: None,
            snapshot_at: None,
            enabled: true,
            counters: Counters::default(),
            pending: 0,
            retry_totals: json!({"attempts": 0, "exhausted": 0}),
            last_tick_seconds: 0.0,
            last_queue_log: None,
            last_locations: json!([]),
            last_wander: None,
            last_reserved_growth: None,
            last_mobs_now_ms: None,
            last_epoch: None,
        }
    }
}

/// External effects of the scheduler. Native execution is statically dispatched;
/// deterministic implementations can exercise the real scheduling boundaries.
pub trait WorkerBackend: Send + Sync + 'static {
    /// Monotonic delivery-budget clock; native execution uses the OS clock.
    fn delivery_now(&self) -> Instant {
        Instant::now()
    }
    fn domains(&self) -> &[&'static str];
    fn has_interactive(&self) -> bool;
    fn has_growth(&self) -> bool;
    fn max_attempts(&self) -> u32;
    fn verify_snapshot(&self, snapshot: &Value) -> Result<()>;
    fn owns_database(&self) -> impl std::future::Future<Output = bool> + Send;
    fn acquire(&self) -> impl std::future::Future<Output = Result<()>> + Send;
    fn assert_owner(&self) -> impl std::future::Future<Output = Result<()>> + Send;
    fn close(&self) -> impl std::future::Future<Output = Result<()>> + Send;
    fn enabled(&self) -> impl std::future::Future<Output = Result<bool>> + Send;
    fn set_enabled(&self, enabled: bool) -> impl std::future::Future<Output = Result<()>> + Send;
    fn expire_exhausted(&self) -> impl std::future::Future<Output = Result<u64>> + Send;
    fn retry_stats(&self) -> impl std::future::Future<Output = Result<Value>> + Send;
    fn queue_summary(&self) -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn dirty(&self) -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn save(
        &self,
        proposals: &[Value],
        dirty: &[Value],
    ) -> impl std::future::Future<Output = Result<Value>> + Send;
    fn pending_count(&self) -> impl std::future::Future<Output = Result<usize>> + Send;
    fn growth_pending_count(&self) -> impl std::future::Future<Output = Result<usize>> + Send;
    fn pending(&self) -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn acknowledge(
        &self,
        results: &[Value],
    ) -> impl std::future::Future<Output = Result<()>> + Send;
    fn query(&self, value: &Value) -> impl std::future::Future<Output = Result<Value>> + Send;
    fn snapshot(&self) -> impl std::future::Future<Output = Result<Value>> + Send;
    fn apply(&self, rows: &[Value])
        -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn prepare(
        &self,
        domain: &str,
        snapshot: &Value,
        limit: usize,
    ) -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn prepare_interactive(
        &self,
        snapshot: &Value,
        limit: usize,
    ) -> impl std::future::Future<Output = Result<Vec<Value>>> + Send;
    fn validate_proposal(
        &self,
        row: &Value,
    ) -> impl std::future::Future<Output = Result<bool>> + Send;
    fn wander_interval(&self) -> impl std::future::Future<Output = Result<f64>> + Send;
}

pub struct NativeBackend {
    context: Arc<Context>,
    repository: Repository,
    client: WorldClient,
}

impl WorkerBackend for NativeBackend {
    fn domains(&self) -> &[&'static str] {
        &DOMAINS
    }
    fn has_interactive(&self) -> bool {
        true
    }
    fn has_growth(&self) -> bool {
        true
    }
    fn max_attempts(&self) -> u32 {
        self.repository.max_attempts()
    }
    fn verify_snapshot(&self, snapshot: &Value) -> Result<()> {
        let generation = self
            .context
            .catalog
            .compiled_generation()
            .context("Native ecology requires a pinned compiled publication")?;
        protocol::catalog_publication(snapshot, self.context.catalog.revision(), Some(generation))?;
        Ok(())
    }
    async fn owns_database(&self) -> bool {
        self.repository.owns_database().await
    }
    async fn acquire(&self) -> Result<()> {
        self.repository.acquire().await
    }
    async fn assert_owner(&self) -> Result<()> {
        self.repository.assert_owner().await
    }
    async fn close(&self) -> Result<()> {
        self.repository.close().await
    }
    async fn enabled(&self) -> Result<bool> {
        self.repository.enabled().await
    }
    async fn set_enabled(&self, enabled: bool) -> Result<()> {
        self.repository.set_enabled(enabled).await
    }
    async fn expire_exhausted(&self) -> Result<u64> {
        self.repository.expire_exhausted().await
    }
    async fn retry_stats(&self) -> Result<Value> {
        self.repository.retry_stats().await
    }
    async fn queue_summary(&self) -> Result<Vec<Value>> {
        self.repository.queue_summary().await
    }
    async fn dirty(&self) -> Result<Vec<Value>> {
        self.repository.dirty().await
    }
    async fn save(&self, proposals: &[Value], dirty: &[Value]) -> Result<Value> {
        self.repository.save(proposals, dirty).await
    }
    async fn pending_count(&self) -> Result<usize> {
        self.repository.pending_count().await
    }
    async fn growth_pending_count(&self) -> Result<usize> {
        self.repository.growth_pending_count().await
    }
    async fn pending(&self) -> Result<Vec<Value>> {
        self.repository.pending().await
    }
    async fn acknowledge(&self, results: &[Value]) -> Result<()> {
        self.repository.acknowledge(results).await
    }
    async fn query(&self, value: &Value) -> Result<Value> {
        self.repository.query(value, &self.context.catalog).await
    }
    async fn snapshot(&self) -> Result<Value> {
        self.client.snapshot().await
    }
    async fn apply(&self, rows: &[Value]) -> Result<Vec<Value>> {
        self.client.apply(rows).await
    }
    async fn prepare(&self, domain: &str, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
        planners::prepare(&self.context, domain, snapshot, limit).await
    }
    async fn prepare_interactive(&self, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
        planners::prepare_interactive(&self.context, snapshot, limit).await
    }
    async fn validate_proposal(&self, row: &Value) -> Result<bool> {
        planners::validate_proposal(&self.context, row).await
    }
    async fn wander_interval(&self) -> Result<f64> {
        planners::wander_interval(&self.context).await
    }
}

/// One scheduler owns each durable ecology queue. Status never waits for I/O.
pub struct Worker<B: WorkerBackend = NativeBackend> {
    backend: Arc<B>,
    interval: Duration,
    state: RwLock<State>,
    tick_gate: Mutex<()>,
    query_gate: Arc<Semaphore>,
}

impl Worker<NativeBackend> {
    pub fn new(
        context: Arc<Context>,
        repository: Repository,
        client: WorldClient,
        interval: Duration,
    ) -> Result<Self> {
        Self::with_backend(
            NativeBackend {
                context,
                repository,
                client,
            },
            interval,
        )
    }
}

impl<B: WorkerBackend> Worker<B> {
    pub fn with_backend(backend: B, interval: Duration) -> Result<Self> {
        if !(Duration::from_millis(100)..=Duration::from_secs(60)).contains(&interval) {
            bail!("Invalid ecology poll interval");
        }
        if backend.domains().is_empty()
            || backend.domains().iter().any(|name| !DOMAINS.contains(name))
            || backend
                .domains()
                .iter()
                .copied()
                .collect::<HashSet<_>>()
                .len()
                != backend.domains().len()
        {
            bail!("Invalid ecology domain registry");
        }
        if !(1..=100).contains(&backend.max_attempts()) {
            bail!("Invalid ecology maximum attempts");
        }
        Ok(Self {
            backend: Arc::new(backend),
            interval,
            state: RwLock::new(State::new()),
            tick_gate: Mutex::new(()),
            query_gate: Arc::new(Semaphore::new(1)),
        })
    }

    /// Exits between ticks; an in-flight transaction finishes its durable boundary.
    pub async fn run(self: Arc<Self>, mut shutdown: watch::Receiver<bool>) {
        loop {
            if *shutdown.borrow() {
                break;
            }
            let result = async {
                if !self.backend.owns_database().await {
                    self.time_stage("queue", self.backend.acquire()).await?;
                }
                self.tick().await
            }
            .await;
            {
                let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
                state.last_error = result.as_ref().err().map(|_| "EcologyWorkerError");
                if result.is_ok() {
                    state.startup_complete = true;
                }
                state.counters.ticks = state.counters.ticks.saturating_add(1);
                state.last_progress = Instant::now();
            }
            tokio::select! {
                _ = tokio::time::sleep(self.interval) => {},
                changed = shutdown.changed() => {
                    if changed.is_err() || *shutdown.borrow() { break; }
                }
            }
        }
        let _ = self.backend.close().await;
    }

    pub async fn tick(&self) -> Result<()> {
        let _tick = self.tick_gate.lock().await;
        let started = Instant::now();
        let delivery_deadline = started + DRAIN_BUDGET;
        self.time_stage("queue", self.backend.assert_owner())
            .await?;
        let log_queue = {
            let state = self.state.read().unwrap_or_else(|e| e.into_inner());
            state
                .last_queue_log
                .is_none_or(|last| last.elapsed() >= Duration::from_secs(30))
        };
        if log_queue {
            let summary = self
                .time_stage("queue", self.backend.queue_summary())
                .await?;
            let counters = self
                .state
                .read()
                .unwrap_or_else(|e| e.into_inner())
                .counters
                .clone();
            println!(
                "{}",
                json!({"event":"ecology_queue_summary", "queues":summary,"counters":counters})
            );
            self.state
                .write()
                .unwrap_or_else(|e| e.into_inner())
                .last_queue_log = Some(Instant::now());
        }
        let enabled = self.time_stage("queue", self.backend.enabled()).await?;
        {
            let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
            state.enabled = enabled;
            if !enabled {
                state.domain_errors.clear();
                return Ok(());
            }
        }
        self.time_stage("queue", self.backend.expire_exhausted())
            .await?;
        let retry_totals = self.time_stage("queue", self.backend.retry_stats()).await?;
        self.state
            .write()
            .unwrap_or_else(|e| e.into_inner())
            .retry_totals = retry_totals;
        // Retry committed work before admitting new work during an outage.
        self.time_stage("queue", self.backend.save(&[], &[]))
            .await?;
        self.drain(delivery_deadline).await?;
        self.update_pending().await?;

        let pending = self.state.read().unwrap_or_else(|e| e.into_inner()).pending;
        if pending >= MAX_PENDING && !self.backend.has_interactive() && !self.backend.has_growth() {
            return Ok(());
        }
        let mut snapshot = self
            .time_stage("world_snapshot", self.backend.snapshot())
            .await?;
        self.backend.verify_snapshot(&snapshot)?;
        match snapshot.get("mode") {
            None => {}
            Some(Value::String(mode)) if mode == "external" => {}
            _ => bail!("World does not authorize external ecology ownership"),
        }
        let dirty = self.time_stage("queue", self.backend.dirty()).await?;
        let tick = self
            .state
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .counters
            .ticks;
        let object = snapshot
            .as_object_mut()
            .context("Invalid ecology snapshot")?;
        object.insert("dirty_scopes".into(), Value::Array(dirty.clone()));
        object.insert("planning_tick".into(), tick.into());
        let epoch = snapshot
            .get("world_epoch")
            .or_else(|| snapshot.get("epoch"))
            .and_then(Value::as_str)
            .context("Missing ecology snapshot epoch")?
            .to_owned();

        // Player intents and monster births have independent reserved admission.
        if self.backend.has_interactive() {
            let interactive = self
                .time_stage(
                    "interactive",
                    self.backend.prepare_interactive(&snapshot, 4),
                )
                .await?;
            let interactive_rows = proposal_rows("plants", interactive, &epoch, 4)?;
            if !interactive_rows.is_empty() {
                self.time_stage("queue", self.backend.save(&interactive_rows, &[]))
                    .await?;
                let ready = self.time_stage("queue", self.backend.pending()).await?;
                if !ready.is_empty() {
                    self.deliver(&ready).await?;
                }
                self.add_planned(interactive_rows.len());
            }
            snapshot["skip_interactive"] = true.into();
            self.update_pending().await?;
        }
        let growth_due = {
            let state = self.state.read().unwrap_or_else(|e| e.into_inner());
            state
                .last_reserved_growth
                .is_none_or(|last| last.elapsed() >= Duration::from_secs(5))
        };
        if self.backend.has_growth() && growth_due {
            self.state
                .write()
                .unwrap_or_else(|e| e.into_inner())
                .last_reserved_growth = Some(Instant::now());
            let pending = self
                .time_stage("queue", self.backend.growth_pending_count())
                .await?;
            let capacity = RESERVED_GROWTH.saturating_sub(pending).min(4);
            if capacity > 0 {
                let growth = self
                    .prepare_scoped(
                        "plants",
                        &mut snapshot,
                        capacity,
                        &[
                            ("skip_interactive", true.into()),
                            ("reserve_monster_births", true.into()),
                        ],
                    )
                    .await?;
                let rows = proposal_rows("plants", growth, &epoch, capacity)?;
                if !rows.is_empty() {
                    self.time_stage("queue", self.backend.save(&rows, &[]))
                        .await?;
                    self.add_planned(rows.len());
                    let ready = self.time_stage("queue", self.backend.pending()).await?;
                    if !ready.is_empty() {
                        self.deliver(&ready).await?;
                    }
                }
            }
            self.update_pending().await?;
        }
        let pending = self.state.read().unwrap_or_else(|e| e.into_inner()).pending;
        if pending >= SOFT_PENDING {
            return Ok(());
        }

        let now_ms = snapshot
            .get("now_ms")
            .and_then(Value::as_i64)
            .filter(|now| *now >= 0)
            .context("Invalid ecology snapshot clock")?;
        let (previous_locations, last_wander) = {
            let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
            if state.last_epoch.as_deref() != Some(epoch.as_str()) {
                state.last_locations = json!([]);
                state.last_wander = None;
                state.last_mobs_now_ms = None;
                state.last_epoch = Some(epoch.clone());
            }
            if state
                .last_mobs_now_ms
                .is_some_and(|previous| now_ms < previous)
            {
                bail!("Ecology snapshot clock moved backwards");
            }
            (state.last_locations.clone(), state.last_wander)
        };
        snapshot["previous_locations"] = previous_locations;
        let cadence = self
            .time_stage("queue", self.backend.wander_interval())
            .await?
            * 1000.0;
        if !cadence.is_finite() || cadence <= 0.0 {
            bail!("Invalid monster wander cadence");
        }
        let allow_wander = last_wander.is_none_or(|last| (now_ms - last) as f64 >= cadence);
        snapshot["allow_wander"] = allow_wander.into();
        let available = MAX_PROPOSALS.min(MAX_PENDING.saturating_sub(pending));
        let mut rows = Vec::with_capacity(available);
        let mut failures = BTreeMap::new();
        let mut mobs_prepared = false;
        let mut visited = 0;
        let domains = self.backend.domains();
        let offset = (tick % domains.len() as u64) as usize;
        for index in 0..domains.len() {
            if rows.len() >= available {
                break;
            }
            let domain = domains[(index + offset) % domains.len()];
            visited += 1;
            let domain_tick = {
                let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
                let slot = state
                    .domain_planning_ticks
                    .entry(domain.to_owned())
                    .or_default();
                let previous = *slot;
                *slot = slot.saturating_add(1);
                previous
            };
            let result = async {
                let prepared = self
                    .prepare_scoped(
                        domain,
                        &mut snapshot,
                        available - rows.len(),
                        &[
                            ("domain_planning_tick", domain_tick.into()),
                            (
                                "skip_monster_births",
                                (domain == "plants" && self.backend.has_growth()).into(),
                            ),
                        ],
                    )
                    .await?;
                proposal_rows(domain, prepared, &epoch, available - rows.len())
            }
            .await;
            match result {
                Ok(candidates) => {
                    rows.extend(candidates);
                    if domain == "mobs" {
                        mobs_prepared = true;
                    }
                }
                Err(_) => {
                    failures.insert(domain.to_owned(), "EcologyPlanningError");
                }
            }
        }
        self.time_stage("queue", self.backend.assert_owner())
            .await?;
        let completed_dirty = if failures.is_empty() && visited == domains.len() {
            dirty
        } else {
            Vec::new()
        };
        self.time_stage("queue", self.backend.save(&rows, &completed_dirty))
            .await?;
        {
            let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
            if mobs_prepared {
                state.last_locations = snapshot
                    .get("locations")
                    .cloned()
                    .unwrap_or_else(|| json!([]));
                state.last_mobs_now_ms = Some(now_ms);
                if allow_wander {
                    state.last_wander = Some(now_ms);
                }
            }
            state.counters.planned = state.counters.planned.saturating_add(rows.len() as u64);
            state.domain_errors = failures;
            state.last_snapshot = Some(snapshot);
            state.snapshot_at = Some(Instant::now());
        }
        if !rows.is_empty() {
            self.time_stage("queue", self.backend.assert_owner())
                .await?;
            self.drain(delivery_deadline).await?;
        }
        self.update_pending().await?;
        self.state
            .write()
            .unwrap_or_else(|e| e.into_inner())
            .last_tick_seconds = started.elapsed().as_secs_f64();
        Ok(())
    }

    async fn prepare_scoped(
        &self,
        domain: &'static str,
        snapshot: &mut Value,
        limit: usize,
        overrides: &[(&str, Value)],
    ) -> Result<Vec<Value>> {
        // Planners borrow the same immutable snapshot. Only tiny scalar flags
        // differ by domain; cloning the whole player/occupancy graph five times
        // would undo the former Python shallow-dict behavior.
        let object = snapshot
            .as_object_mut()
            .context("Invalid ecology snapshot")?;
        let previous: Vec<_> = overrides
            .iter()
            .map(|(key, value)| {
                (
                    (*key).to_owned(),
                    object.insert((*key).to_owned(), value.clone()),
                )
            })
            .collect();
        let stage = if overrides
            .iter()
            .any(|(key, value)| *key == "reserve_monster_births" && value.as_bool() == Some(true))
        {
            "reserved_growth"
        } else {
            domain
        };
        let result = self
            .time_stage(stage, self.backend.prepare(domain, snapshot, limit))
            .await;
        let object = snapshot
            .as_object_mut()
            .expect("Planner has only an immutable snapshot borrow");
        for (key, value) in previous {
            match value {
                Some(value) => {
                    object.insert(key, value);
                }
                None => {
                    object.remove(&key);
                }
            }
        }
        result
    }

    async fn time_stage<T>(
        &self,
        stage: &'static str,
        operation: impl std::future::Future<Output = Result<T>>,
    ) -> Result<T> {
        let started = Instant::now();
        let result = operation.await;
        self.record_stage(stage, started.elapsed());
        result
    }

    fn record_stage(&self, stage: &'static str, elapsed: Duration) {
        // Fixed low-cardinality labels only; never retain IDs, payloads or errors.
        if !STAGE_KEYS.contains(&stage) {
            return;
        }
        let milliseconds = elapsed.as_secs_f64() * 1000.0;
        let mut state = self
            .state
            .write()
            .unwrap_or_else(|error| error.into_inner());
        let timing = state.stage_timings.entry(stage).or_default();
        timing.count = timing.count.saturating_add(1);
        timing.last_ms = milliseconds;
        timing.max_ms = timing.max_ms.max(milliseconds);
        timing.total_ms = (timing.total_ms + milliseconds).min(f64::MAX);
    }

    fn add_planned(&self, count: usize) {
        let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
        state.counters.planned = state.counters.planned.saturating_add(count as u64);
    }

    async fn update_pending(&self) -> Result<()> {
        let pending = self
            .time_stage("queue", self.backend.pending_count())
            .await?;
        self.state
            .write()
            .unwrap_or_else(|e| e.into_inner())
            .pending = pending;
        Ok(())
    }

    async fn drain(&self, deadline: Instant) -> Result<()> {
        let mut seen = HashSet::new();
        for _ in 0..MAX_DRAIN_BATCHES {
            if self.backend.delivery_now() >= deadline {
                break;
            }
            let ready = self.time_stage("queue", self.backend.pending()).await?;
            if ready.is_empty() {
                break;
            }
            let identities: HashSet<String> = ready
                .iter()
                .map(|row| {
                    row.get("id")
                        .and_then(Value::as_str)
                        .map(str::to_owned)
                        .context("Invalid pending ecology identity")
                })
                .collect::<Result<_>>()?;
            if identities.iter().any(|id| seen.contains(id)) {
                break;
            }
            seen.extend(identities);
            let results = self.deliver(&ready).await?;
            if results.is_empty()
                || results.iter().any(|row| {
                    matches!(
                        row.get("status").and_then(Value::as_str),
                        Some("deferred" | "retry")
                    )
                })
            {
                break;
            }
        }
        Ok(())
    }

    async fn deliver(&self, rows: &[Value]) -> Result<Vec<Value>> {
        self.time_stage("queue", self.backend.assert_owner())
            .await?;
        let mut batch = Vec::new();
        let mut rejected = Vec::new();
        let mut encoded_size = empty_envelope_size()?;
        for row in rows.iter().take(MAX_PROPOSALS) {
            if !self
                .time_stage("delivery_validation", self.backend.validate_proposal(row))
                .await?
            {
                rejected.push(json!({"id": row.get("id").context("Missing proposal identity")?, "status":"stale"}));
                continue;
            }
            let candidate_size = protocol::json_bytes(row, MAX_BODY_BYTES)
                .ok()
                .and_then(|bytes| {
                    encoded_size
                        .checked_add(bytes.len())?
                        .checked_add(usize::from(!batch.is_empty()))
                });
            if !candidate_size.is_some_and(|size| size <= MAX_BODY_BYTES) {
                if batch.is_empty() {
                    bail!("Ecology proposal exceeds wire budget");
                }
                break;
            }
            encoded_size = candidate_size.expect("Candidate wire size was checked");
            batch.push(row.clone());
        }
        if !rejected.is_empty() {
            self.time_stage("queue", self.backend.acknowledge(&rejected))
                .await?;
            let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
            state.counters.stale = state.counters.stale.saturating_add(rejected.len() as u64);
        }
        if batch.is_empty() {
            return Ok(rejected);
        }
        let results = match self
            .time_stage("world_apply", self.backend.apply(&batch))
            .await
        {
            Ok(results) => results,
            Err(error) => {
                let retries = batch
                    .iter()
                    .map(|row| json!({"id":row["id"],"status":"retry"}))
                    .collect::<Vec<_>>();
                self.time_stage("queue", self.backend.acknowledge(&retries))
                    .await?;
                let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
                state.counters.retries = state.counters.retries.saturating_add(batch.len() as u64);
                return Err(error);
            }
        };
        self.time_stage("queue", self.backend.acknowledge(&results))
            .await?;
        {
            let mut state = self.state.write().unwrap_or_else(|e| e.into_inner());
            for row in &results {
                let counter = match row.get("status").and_then(Value::as_str) {
                    Some("stale") => &mut state.counters.stale,
                    Some("retry") => &mut state.counters.retries,
                    Some("deferred") => &mut state.counters.deferred,
                    Some("applied" | "duplicate") => &mut state.counters.delivered,
                    _ => bail!("Invalid ecology acknowledgement status"),
                };
                *counter = counter.saturating_add(1);
            }
        }
        rejected.extend(results);
        Ok(rejected)
    }

    pub fn status(&self) -> Value {
        let state = self.state.read().unwrap_or_else(|e| e.into_inner());
        let age = state.last_progress.elapsed().as_secs_f64();
        let (cpu, rss) = process_usage();
        let mut domains = self.backend.domains().to_vec();
        domains.sort_unstable();
        json!({
            "healthy":state.startup_complete && age <= 15.0_f64.max(self.interval.as_secs_f64()*3.0)
                && state.last_error.is_none() && state.domain_errors.is_empty() && state.pending < MAX_PENDING,
            "enabled":state.enabled,"progress_age_seconds":age,"last_error":state.last_error,
            "domain_errors":state.domain_errors,"pending":state.pending,"last_tick_seconds":state.last_tick_seconds,
            "delivery_attempts":state.retry_totals.get("attempts").unwrap_or(&Value::Null),
            "retry_exhausted":state.retry_totals.get("exhausted").unwrap_or(&Value::Null),
            "max_attempts":self.backend.max_attempts(),"counters":state.counters,"domains":domains,
            "cpu_cumulative_seconds":cpu,"peak_rss_bytes":rss,"stage_timings":state.stage_timings
        })
    }

    pub fn diagnostic_snapshot(&self) -> Value {
        let state = self.state.read().unwrap_or_else(|e| e.into_inner());
        json!({"authoritative":false,"snapshot":state.last_snapshot,
            "age_seconds":state.snapshot_at.map(|at| at.elapsed().as_secs_f64())})
    }

    pub async fn set_enabled(&self, enabled: bool) -> Result<()> {
        self.time_stage("queue", self.backend.set_enabled(enabled))
            .await
    }

    pub async fn query(&self, value: Value) -> Result<Value> {
        validate_query(&value)?;
        let permit = self
            .query_gate
            .clone()
            .try_acquire_owned()
            .map_err(|_| anyhow!("Ecology query already running"))?;
        let backend = self.backend.clone();
        // Timeout detaches at most this one task. The permit is held until its
        // real DB future completes, just like the previous one-worker executor.
        let task = tokio::spawn(async move {
            let _permit = permit;
            backend.query(&value).await
        });
        tokio::time::timeout(Duration::from_secs(2), task)
            .await
            .context("Ecology query timed out")?
            .context("Ecology query task failed")?
    }
}

fn proposal_rows(
    domain: &str,
    prepared: Vec<Value>,
    epoch: &str,
    limit: usize,
) -> Result<Vec<Value>> {
    if prepared.len() > limit {
        bail!("Ecology planner exceeded proposal budget");
    }
    let base_size = empty_envelope_size()?;
    prepared
        .into_iter()
        .map(|payload| {
            let row = proposal(domain, payload, epoch)?;
            let encoded = protocol::json_bytes(&row, MAX_BODY_BYTES)?;
            if encoded.len().saturating_add(base_size) > MAX_BODY_BYTES {
                bail!("Ecology proposal exceeds wire budget");
            }
            Ok(row)
        })
        .collect()
}

fn empty_envelope_size() -> Result<usize> {
    Ok(protocol::json_bytes(
        &json!({"schema_version":SCHEMA_VERSION,"proposals":[]}),
        MAX_BODY_BYTES,
    )?
    .len())
}

fn process_usage() -> (f64, u64) {
    // These are bounded OS counters, never a heap walk or forced collection.
    unsafe {
        let mut clock: libc::timespec = std::mem::zeroed();
        let mut usage: libc::rusage = std::mem::zeroed();
        let cpu = if libc::clock_gettime(libc::CLOCK_PROCESS_CPUTIME_ID, &mut clock) == 0 {
            clock.tv_sec as f64 + clock.tv_nsec as f64 / 1e9
        } else {
            0.0
        };
        let rss = if libc::getrusage(libc::RUSAGE_SELF, &mut usage) == 0 {
            let scale = if cfg!(target_os = "macos") { 1 } else { 1024 };
            (usage.ru_maxrss.max(0) as u64).saturating_mul(scale)
        } else {
            0
        };
        (cpu, rss)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn query_rejects_foreign_fields_floats_and_out_of_range_ids() {
        for query in [
            json!({}),
            json!({"kind":"weather","map_id":1.0,"instance_id":0}),
            json!({"kind":"weather","map_id":1,"instance_id":-1}),
            json!({"kind":"population","map_id":1,"instance_id":0,"region_id":0}),
            json!({"kind":"population","map_id":1,"instance_id":0,"authority":true}),
        ] {
            assert!(validate_query(&query).is_err(), "{query}");
        }
        assert!(
            validate_query(&json!({"kind":"population","map_id":1,"instance_id":i64::MAX})).is_ok()
        );
    }

    #[test]
    fn proposal_budget_and_individual_wire_size_are_checked() {
        assert!(proposal_rows("plants", vec![json!({}); 2], "epoch", 1).is_err());
        assert!(proposal_rows(
            "plants",
            vec![json!({"blob":"x".repeat(256*1024)})],
            "epoch",
            1
        )
        .is_err());
        let rows = proposal_rows(
            "plants",
            vec![json!({"kind":"growth_publish","resource_uid":12})],
            "epoch",
            1,
        )
        .unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["world_epoch"], "epoch");

        let empty = proposal_rows("plants", vec![json!({"blob":""})], "epoch", 1).unwrap();
        let overhead = protocol::json_bytes(
            &json!({"schema_version":SCHEMA_VERSION,"proposals":empty}),
            MAX_BODY_BYTES,
        )
        .unwrap()
        .len();
        let exact = proposal_rows(
            "plants",
            vec![json!({"blob":"x".repeat(MAX_BODY_BYTES-overhead)})],
            "epoch",
            1,
        )
        .unwrap();
        assert_eq!(
            protocol::json_bytes(
                &json!({"schema_version":SCHEMA_VERSION,"proposals":exact}),
                MAX_BODY_BYTES,
            )
            .unwrap()
            .len(),
            MAX_BODY_BYTES
        );
        assert!(proposal_rows(
            "plants",
            vec![json!({"blob":"x".repeat(MAX_BODY_BYTES-overhead+1)})],
            "epoch",
            1,
        )
        .is_err());
    }
}

#[cfg(test)]
#[path = "worker_tests.rs"]
mod scheduler_tests;
