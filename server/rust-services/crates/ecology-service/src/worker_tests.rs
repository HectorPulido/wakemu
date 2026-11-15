//! Scheduler parity cases migrated from the former Python transport harness.
//! All assertions drive Worker tick/drain/deliver, with only external effects injected.
use super::*;
use std::collections::VecDeque;
use std::sync::Mutex as StdMutex;
use tokio::sync::Notify;

struct QueryGate {
    entered: Notify,
    release: Notify,
}

struct Fixture {
    domains: Vec<&'static str>,
    interactive: bool,
    growth: bool,
    max_attempts: u32,
    owned: bool,
    enabled: bool,
    count: usize,
    growth_count: usize,
    pending: VecDeque<Vec<Value>>,
    repeated_pending: Vec<Value>,
    snapshot: Value,
    plans: BTreeMap<String, Vec<Value>>,
    fill_budget: HashSet<String>,
    broken: HashSet<String>,
    rejected_proposal_ids: HashSet<String>,
    interactive_plans: Vec<Value>,
    growth_plans: Vec<Value>,
    saves: Vec<(Vec<Value>, Vec<Value>)>,
    fail_save: Option<usize>,
    applied: Vec<Vec<Value>>,
    acknowledged: Vec<Vec<Value>>,
    status: &'static str,
    offline: bool,
    apply_delay: Duration,
    delivery_clock: Option<Instant>,
    advance_delivery_clock: Duration,
    captured: Vec<(String, Value, usize)>,
    events: Vec<String>,
    query_gate: Option<Arc<QueryGate>>,
}

impl Fixture {
    fn new(domains: &[&'static str]) -> Self {
        Self {
            domains: domains.to_vec(),
            interactive: false,
            growth: false,
            max_attempts: 5,
            owned: true,
            enabled: true,
            count: 0,
            growth_count: 0,
            pending: VecDeque::new(),
            repeated_pending: vec![],
            snapshot: json!({"schema_version":1,"world_epoch":"boot-1","epoch":"boot-1","scopes":[],"mode":"external","now_ms":1000,"locations":[],"catalog_revision":"a".repeat(64),"compiled_catalog_generation":"b".repeat(64)}),
            plans: BTreeMap::new(),
            fill_budget: HashSet::new(),
            broken: HashSet::new(),
            rejected_proposal_ids: HashSet::new(),
            interactive_plans: vec![],
            growth_plans: vec![],
            saves: vec![],
            fail_save: None,
            applied: vec![],
            acknowledged: vec![],
            status: "applied",
            offline: false,
            apply_delay: Duration::ZERO,
            delivery_clock: None,
            advance_delivery_clock: Duration::ZERO,
            captured: vec![],
            events: vec![],
            query_gate: None,
        }
    }
}

struct FakeBackend {
    domains: Vec<&'static str>,
    interactive: bool,
    growth: bool,
    max_attempts: u32,
    data: Arc<StdMutex<Fixture>>,
}

impl WorkerBackend for FakeBackend {
    fn delivery_now(&self) -> Instant {
        self.data
            .lock()
            .unwrap()
            .delivery_clock
            .unwrap_or_else(Instant::now)
    }
    fn domains(&self) -> &[&'static str] {
        &self.domains
    }
    fn has_interactive(&self) -> bool {
        self.interactive
    }
    fn has_growth(&self) -> bool {
        self.growth
    }
    fn max_attempts(&self) -> u32 {
        self.max_attempts
    }
    fn verify_snapshot(&self, snapshot: &Value) -> Result<()> {
        self.data
            .lock()
            .unwrap()
            .events
            .push("verify_snapshot".into());
        protocol::catalog_publication(snapshot, &"a".repeat(64), Some(&"b".repeat(64)))?;
        Ok(())
    }
    async fn owns_database(&self) -> bool {
        self.data.lock().unwrap().owned
    }
    async fn acquire(&self) -> Result<()> {
        self.data.lock().unwrap().owned = true;
        Ok(())
    }
    async fn assert_owner(&self) -> Result<()> {
        let mut data = self.data.lock().unwrap();
        data.events.push("assert_owner".into());
        if !data.owned {
            bail!("Lost owner")
        }
        Ok(())
    }
    async fn close(&self) -> Result<()> {
        self.data.lock().unwrap().owned = false;
        Ok(())
    }
    async fn enabled(&self) -> Result<bool> {
        Ok(self.data.lock().unwrap().enabled)
    }
    async fn set_enabled(&self, value: bool) -> Result<()> {
        self.data.lock().unwrap().enabled = value;
        Ok(())
    }
    async fn expire_exhausted(&self) -> Result<u64> {
        self.data.lock().unwrap().events.push("expire".into());
        Ok(0)
    }
    async fn retry_stats(&self) -> Result<Value> {
        Ok(json!({"attempts":0,"exhausted":0}))
    }
    async fn queue_summary(&self) -> Result<Vec<Value>> {
        Ok(vec![])
    }
    async fn dirty(&self) -> Result<Vec<Value>> {
        Ok(vec![json!({"map_id":1,"instance_id":0,"revision":3})])
    }
    async fn save(&self, rows: &[Value], dirty: &[Value]) -> Result<Value> {
        let mut data = self.data.lock().unwrap();
        data.events.push("save".into());
        data.saves.push((rows.to_vec(), dirty.to_vec()));
        if data.fail_save == Some(data.saves.len()) {
            bail!("Unavailable database")
        }
        Ok(json!({}))
    }
    async fn pending_count(&self) -> Result<usize> {
        let mut data = self.data.lock().unwrap();
        data.events.push("pending_count".into());
        Ok(data.count)
    }
    async fn growth_pending_count(&self) -> Result<usize> {
        Ok(self.data.lock().unwrap().growth_count)
    }
    async fn pending(&self) -> Result<Vec<Value>> {
        let mut data = self.data.lock().unwrap();
        data.events.push("pending".into());
        Ok(data
            .pending
            .pop_front()
            .unwrap_or_else(|| data.repeated_pending.clone()))
    }
    async fn acknowledge(&self, rows: &[Value]) -> Result<()> {
        let mut data = self.data.lock().unwrap();
        data.events.push("acknowledge".into());
        data.acknowledged.push(rows.to_vec());
        Ok(())
    }
    async fn query(&self, _value: &Value) -> Result<Value> {
        let gate = {
            let mut data = self.data.lock().unwrap();
            data.events.push("query".into());
            data.query_gate.clone()
        };
        if let Some(gate) = gate {
            gate.entered.notify_one();
            gate.release.notified().await;
        }
        Ok(json!({"authoritative":true}))
    }
    async fn snapshot(&self) -> Result<Value> {
        let mut data = self.data.lock().unwrap();
        data.events.push("snapshot".into());
        Ok(data.snapshot.clone())
    }
    async fn apply(&self, rows: &[Value]) -> Result<Vec<Value>> {
        let (delay, status, offline) = {
            let mut data = self.data.lock().unwrap();
            data.events.push("apply".into());
            data.applied.push(rows.to_vec());
            if let Some(now) = data.delivery_clock {
                data.delivery_clock = Some(now + data.advance_delivery_clock);
            }
            (data.apply_delay, data.status, data.offline)
        };
        if !delay.is_zero() {
            tokio::time::sleep(delay).await;
        }
        if offline {
            bail!("Unknown HTTP outcome")
        }
        Ok(rows
            .iter()
            .map(|row| json!({"id":row["id"],"status":status}))
            .collect())
    }
    async fn prepare(&self, domain: &str, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
        let mut data = self.data.lock().unwrap();
        let name = if snapshot["reserve_monster_births"] == true {
            "growth"
        } else {
            domain
        };
        data.events.push(format!("prepare:{name}"));
        data.captured
            .push((name.to_owned(), snapshot.clone(), limit));
        if data.broken.contains(name) {
            bail!("Private internal planning context")
        }
        if name == "growth" {
            return Ok(data.growth_plans.clone());
        }
        if data.fill_budget.contains(domain) {
            return Ok((0..limit).map(|n| json!({"n":n})).collect());
        }
        Ok(data.plans.get(domain).cloned().unwrap_or_default())
    }
    async fn prepare_interactive(&self, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
        let mut data = self.data.lock().unwrap();
        data.events.push("interactive".into());
        data.captured
            .push(("interactive".into(), snapshot.clone(), limit));
        Ok(data.interactive_plans.clone())
    }
    async fn validate_proposal(&self, row: &Value) -> Result<bool> {
        Ok(!self
            .data
            .lock()
            .unwrap()
            .rejected_proposal_ids
            .contains(row.get("id").and_then(Value::as_str).unwrap_or("")))
    }
    async fn wander_interval(&self) -> Result<f64> {
        Ok(5.0)
    }
}

fn create(fixture: Fixture) -> (Worker<FakeBackend>, Arc<StdMutex<Fixture>>) {
    let backend = FakeBackend {
        domains: fixture.domains.clone(),
        interactive: fixture.interactive,
        growth: fixture.growth,
        max_attempts: fixture.max_attempts,
        data: Arc::new(StdMutex::new(fixture)),
    };
    let data = backend.data.clone();
    (
        Worker::with_backend(backend, Duration::from_secs(1)).unwrap(),
        data,
    )
}
fn row(sequence: usize) -> Value {
    proposal("mobs", json!({"sequence":sequence}), "boot-1").unwrap()
}
fn occurrences(data: &Fixture, event: &str) -> usize {
    data.events
        .iter()
        .filter(|seen| seen.as_str() == event)
        .count()
}

#[tokio::test]
async fn drain_processes_distinct_batches_and_bounds_persistent_producer() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.pending = (0..20).map(|n| vec![row(n)]).collect();
    let (worker, data) = create(fixture);
    worker
        .drain(Instant::now() + Duration::from_secs(10))
        .await
        .unwrap();
    let data = data.lock().unwrap();
    assert_eq!(data.applied.len(), 16);
    assert_eq!(data.acknowledged.len(), 16);
}

#[tokio::test]
async fn drain_stops_on_admission_delay_retry_and_repeated_ids() {
    for status in ["deferred", "retry", "applied"] {
        let mut fixture = Fixture::new(&["plants"]);
        fixture.status = status;
        fixture.repeated_pending = vec![row(1)];
        let (worker, data) = create(fixture);
        worker
            .drain(Instant::now() + Duration::from_secs(1))
            .await
            .unwrap();
        let data = data.lock().unwrap();
        assert_eq!(data.applied.len(), 1);
        assert!(occurrences(&data, "pending") <= 2);
    }
}

#[tokio::test]
async fn drain_checks_time_budget_before_second_network_call() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.pending = (0..3).map(|n| vec![row(n)]).collect();
    let started = Instant::now();
    fixture.delivery_clock = Some(started);
    fixture.advance_delivery_clock = Duration::from_millis(201);
    let (worker, data) = create(fixture);
    worker
        .drain(started + Duration::from_millis(200))
        .await
        .unwrap();
    let data = data.lock().unwrap();
    assert_eq!(data.applied.len(), 1);
    assert_eq!(occurrences(&data, "pending"), 1);
}

#[tokio::test]
async fn durable_delivery_precedes_new_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.pending = vec![vec![row(2)], vec![], vec![]].into();
    fixture.status = "duplicate";
    fixture
        .plans
        .insert("plants".into(), vec![json!({"uid":1})]);
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(data.applied, vec![vec![row(2)]]);
    let (rows, dirty) = data.saves.last().unwrap();
    assert_eq!(rows[0]["payload"], json!({"uid":1}));
    assert_eq!(dirty[0]["revision"], 3);
    assert!(
        data.events.iter().position(|e| e == "apply")
            < data.events.iter().position(|e| e == "prepare:plants")
    );
    assert_eq!(worker.status()["counters"]["delivered"], 1);
}

#[tokio::test]
async fn delivery_splits_combined_body_and_only_acknowledges_sent_prefix() {
    let (worker, data) = create(Fixture::new(&["plants"]));
    let rows = (1..=2)
        .map(|id| {
            proposal(
                "plants",
                json!({"uid":id,"data":"x".repeat(MAX_BODY_BYTES/2)}),
                "boot",
            )
            .unwrap()
        })
        .collect::<Vec<_>>();
    assert!(protocol::json_bytes(
        &json!({"schema_version":1,"proposals":rows}),
        MAX_BODY_BYTES
    )
    .is_err());
    worker.deliver(&rows).await.unwrap();
    assert_eq!(data.lock().unwrap().applied, vec![rows[..1].to_vec()]);
    worker.deliver(&rows[1..]).await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(data.applied[1], rows[1..]);
    assert_eq!(data.acknowledged.len(), 2);
    assert_eq!(worker.status()["counters"]["delivered"], 2);
}

#[tokio::test]
async fn http_timeout_is_durably_counted_and_expiry_precedes_capacity_check() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.offline = true;
    fixture.count = MAX_PENDING;
    let (worker, data) = create(fixture);
    let pending = row(991);
    assert!(worker.deliver(&[pending.clone()]).await.is_err());
    assert_eq!(
        data.lock().unwrap().acknowledged,
        vec![vec![json!({"id":pending["id"],"status":"retry"})]]
    );
    assert_eq!(worker.status()["counters"]["retries"], 1);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert!(
        data.events.iter().position(|e| e == "expire")
            < data.events.iter().position(|e| e == "pending_count")
    );
    assert_eq!(occurrences(&data, "snapshot"), 0);
}

#[test]
fn retry_limit_and_domain_configuration_are_bounded_before_effects() {
    for invalid in [0, 101] {
        let mut fixture = Fixture::new(&["plants"]);
        fixture.max_attempts = invalid;
        let backend = FakeBackend {
            domains: vec!["plants"],
            interactive: false,
            growth: false,
            max_attempts: invalid,
            data: Arc::new(StdMutex::new(fixture)),
        };
        assert!(Worker::with_backend(backend, Duration::from_secs(1)).is_err());
    }
    for domains in [vec![], vec!["unknown"], vec!["plants", "plants"]] {
        let backend = FakeBackend {
            domains: domains.clone(),
            interactive: false,
            growth: false,
            max_attempts: 3,
            data: Arc::new(StdMutex::new(Fixture::new(&domains))),
        };
        assert!(Worker::with_backend(backend, Duration::from_secs(1)).is_err());
    }
}

#[tokio::test]
async fn domain_failure_keeps_other_domains_and_does_not_ack_dirty() {
    let mut fixture = Fixture::new(&["plants", "mobs"]);
    fixture.broken.insert("plants".into());
    fixture.plans.insert("mobs".into(), vec![json!({"id":5})]);
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    let (rows, dirty) = data.saves.last().unwrap();
    assert_eq!(rows[0]["domain"], "mobs");
    assert!(dirty.is_empty());
    assert_eq!(
        worker.status()["domain_errors"]["plants"],
        "EcologyPlanningError"
    );
    assert!(!worker.status().to_string().contains("Private"));
}

#[tokio::test]
async fn offline_apply_keeps_pending_and_prevents_new_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.offline = true;
    fixture.repeated_pending = vec![row(7)];
    let (worker, data) = create(fixture);
    assert!(worker.tick().await.is_err());
    let data = data.lock().unwrap();
    assert_eq!(data.saves, vec![(vec![], vec![])]);
    assert_eq!(data.acknowledged[0][0]["status"], "retry");
    assert!(!data.events.iter().any(|e| e.starts_with("prepare:")));
    assert_eq!(occurrences(&data, "snapshot"), 0);
}

#[tokio::test]
async fn saturated_background_still_delivers_reserved_seed_growth() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.count = MAX_PENDING;
    fixture.growth = true;
    let growth = json!({"kind":"resource_growth","world_epoch":"boot-1","expected":{"resource_uid":7,"stage":1},"member":{"id":-7}});
    let proposal = proposal("plants", growth.clone(), "boot-1").unwrap();
    fixture.growth_plans = vec![growth];
    fixture.pending = vec![vec![], vec![proposal.clone()]].into();
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    let captured = data
        .captured
        .iter()
        .find(|(name, _, _)| name == "growth")
        .unwrap();
    assert_eq!(captured.2, 4);
    assert_eq!(captured.1["skip_interactive"], true);
    assert_eq!(data.applied, vec![vec![proposal]]);
    assert_eq!(occurrences(&data, "prepare:plants"), 0);
}

#[tokio::test]
async fn reserved_birth_lane_keeps_ambient_flora_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.growth = true;
    fixture.growth_count = 16;
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(occurrences(&data, "prepare:growth"), 0);
    let (_, snapshot, _) = data
        .captured
        .iter()
        .find(|(name, _, _)| name == "plants")
        .unwrap();
    assert_eq!(snapshot["skip_monster_births"], true);
}

#[tokio::test]
async fn reserved_growth_stops_at_its_own_pending_limit() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.growth = true;
    fixture.growth_count = 16;
    fixture.count = MAX_PENDING;
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert!(data.captured.is_empty());
    assert!(data.applied.is_empty());
}

#[tokio::test]
async fn saturated_background_still_admits_reserved_player_planting() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.interactive = true;
    fixture.count = MAX_PENDING;
    let intent = json!({"kind":"planting_begin","world_epoch":"boot-1","intent_id":"player"});
    fixture.interactive_plans = vec![intent.clone()];
    let row = proposal("plants", intent, "boot-1").unwrap();
    fixture.pending = vec![vec![], vec![row.clone()]].into();
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(occurrences(&data, "interactive"), 1);
    assert_eq!(data.captured[0].2, 4);
    assert_eq!(data.applied, vec![vec![row]]);
    assert_eq!(data.acknowledged.len(), 1);
    assert_eq!(occurrences(&data, "prepare:plants"), 0);
}

#[tokio::test]
async fn reserved_interactive_suppresses_duplicate_background_intent_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.interactive = true;
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    let (_, snapshot, _) = data
        .captured
        .iter()
        .find(|(name, _, _)| name == "plants")
        .unwrap();
    assert_eq!(snapshot["skip_interactive"], true);
}

#[tokio::test]
async fn pending_cap_and_pause_skip_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.count = MAX_PENDING;
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    assert_eq!(occurrences(&data.lock().unwrap(), "snapshot"), 0);
    {
        let mut data = data.lock().unwrap();
        data.enabled = false;
        data.events.clear();
    }
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(occurrences(&data, "snapshot"), 0);
    assert!(data.captured.is_empty());
    assert_eq!(worker.status()["enabled"], false);
}

#[tokio::test]
async fn domain_budget_rotation_avoids_starvation() {
    let mut fixture = Fixture::new(&["plants", "mobs"]);
    fixture.fill_budget.insert("plants".into());
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    assert_eq!(occurrences(&data.lock().unwrap(), "prepare:mobs"), 0);
    assert!(data.lock().unwrap().saves.last().unwrap().1.is_empty());
    worker.state.write().unwrap().counters.ticks = 1;
    worker.tick().await.unwrap();
    assert_eq!(occurrences(&data.lock().unwrap(), "prepare:mobs"), 1);
}

#[tokio::test]
async fn stale_world_mode_and_lost_owner_stop_planning() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture.snapshot["mode"] = "inline".into();
    let (worker, data) = create(fixture);
    assert!(worker.tick().await.is_err());
    assert!(data.lock().unwrap().captured.is_empty());
    {
        let mut data = data.lock().unwrap();
        data.owned = false;
        data.events.clear();
    }
    assert!(worker.tick().await.is_err());
    let data = data.lock().unwrap();
    assert_eq!(occurrences(&data, "snapshot"), 0);
}

#[tokio::test]
async fn previous_locations_and_wander_cadence_follow_successful_mobs_passes() {
    let mut fixture = Fixture::new(&["mobs"]);
    fixture.snapshot["locations"] = json!([[527, 0]]);
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    assert_eq!(
        data.lock().unwrap().captured.last().unwrap().1["allow_wander"],
        true
    );
    {
        let mut data = data.lock().unwrap();
        data.snapshot["locations"] = json!([[528, 0]]);
        data.snapshot["now_ms"] = 2000.into();
    }
    worker.tick().await.unwrap();
    {
        let data = data.lock().unwrap();
        let snapshot = &data.captured.last().unwrap().1;
        assert_eq!(snapshot["previous_locations"], json!([[527, 0]]));
        assert_eq!(snapshot["allow_wander"], false);
    }
    data.lock().unwrap().snapshot["now_ms"] = 6000.into();
    worker.tick().await.unwrap();
    assert_eq!(
        data.lock().unwrap().captured.last().unwrap().1["allow_wander"],
        true
    );
}

#[tokio::test]
async fn failed_durable_save_does_not_advance_mobs_snapshot_clock() {
    let mut fixture = Fixture::new(&["mobs"]);
    fixture.fail_save = Some(2);
    fixture.snapshot["locations"] = json!([[527, 0]]);
    let (worker, data) = create(fixture);
    assert!(worker.tick().await.is_err());
    assert_eq!(occurrences(&data.lock().unwrap(), "prepare:mobs"), 1);
    let state = worker.state.read().unwrap();
    assert_eq!(state.last_mobs_now_ms, None);
    assert_eq!(state.last_locations, json!([]));
}

#[tokio::test]
async fn query_is_single_flight_and_releases_gate_after_real_completion() {
    let gate = Arc::new(QueryGate {
        entered: Notify::new(),
        release: Notify::new(),
    });
    let mut fixture = Fixture::new(&["plants"]);
    fixture.query_gate = Some(gate.clone());
    let (worker, data) = create(fixture);
    let worker = Arc::new(worker);
    let owner = worker.clone();
    let request = json!({"kind":"population","map_id":527,"instance_id":0});
    let first_request = request.clone();
    let first = tokio::spawn(async move { owner.query(first_request).await });
    gate.entered.notified().await;
    assert!(worker.query(request.clone()).await.is_err());
    gate.release.notify_one();
    assert_eq!(first.await.unwrap().unwrap()["authoritative"], true);
    data.lock().unwrap().query_gate = None;
    assert_eq!(worker.query(request).await.unwrap()["authoritative"], true);
}

#[tokio::test]
async fn new_proposals_are_saved_before_same_tick_delivery() {
    let mut fixture = Fixture::new(&["plants"]);
    fixture
        .plans
        .insert("plants".into(), vec![json!({"uid":1})]);
    let prepared = proposal("plants", json!({"uid":1}), "boot-1").unwrap();
    fixture.pending = vec![vec![], vec![prepared.clone()], vec![]].into();
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    let data = data.lock().unwrap();
    assert_eq!(data.applied, vec![vec![prepared.clone()]]);
    assert_eq!(data.acknowledged.len(), 1);
    assert_eq!(data.saves.last().unwrap().0, vec![prepared]);
    let apply = data.events.iter().position(|e| e == "apply").unwrap();
    let save = data.events[..apply]
        .iter()
        .rposition(|e| e == "save")
        .unwrap();
    assert!(save < apply);
}

#[tokio::test]
async fn changed_world_publication_stops_native_planning_without_guessing_latest() {
    let mut fixture = Fixture::new(&["mobs"]);
    fixture.snapshot["compiled_catalog_generation"] = "c".repeat(64).into();
    let (worker, data) = create(fixture);
    assert!(worker.tick().await.is_err());
    let data = data.lock().unwrap();
    assert!(data.captured.is_empty());
    assert_eq!(occurrences(&data, "verify_snapshot"), 1);
}

#[tokio::test]
async fn rejected_old_home_work_is_acknowledged_stale_without_world_delivery() {
    // World tests retain the actual native edge/home checks. This verifies the
    // scheduler obeys their rejection before making any World HTTP request.
    for flag in [None, Some("dispersal"), Some("overlap_escape")] {
        let mut fixture = Fixture::new(&["mobs"]);
        fixture.rejected_proposal_ids.insert("queued-home".into());
        let (worker, data) = create(fixture);
        let mut movement = json!({
            "group_id":17,
            "expected_members":[{"id":-1,"ref":4,"level":10,"x":0,"y":0,"z":0}],
            "moved_members":[{"id":-1,"ref":4,"level":10,"x":1,"y":0,"z":0}],
            "packets":[]
        });
        if let Some(flag) = flag {
            movement[flag] = true.into();
        }
        let queued = json!({
            "id":"queued-home", "domain":"mobs", "world_epoch":"birth-home",
            "payload":{"kind":"wander_bulk", "scope":[999999,0],
                "world_epoch":"birth-home", "moves":[movement]}
        });
        let expected = vec![json!({"id":"queued-home","status":"stale"})];
        assert_eq!(worker.deliver(&[queued]).await.unwrap(), expected);
        let data = data.lock().unwrap();
        assert!(data.applied.is_empty());
        assert_eq!(data.acknowledged, vec![expected]);
        assert_eq!(worker.status()["counters"]["stale"], 1);
    }
}

#[tokio::test]
async fn stage_metrics_cover_actual_work_and_failures_with_fixed_private_free_labels() {
    let mut fixture = Fixture::new(&DOMAINS);
    fixture.interactive = true;
    fixture.growth = true;
    fixture.snapshot["players"] = json!([{"private":"never-retain-player-payload"}]);
    let (worker, data) = create(fixture);
    worker.tick().await.unwrap();
    for stage in [
        "plants",
        "mobs",
        "weather",
        "population",
        "bonuses",
        "interactive",
        "reserved_growth",
        "world_snapshot",
        "queue",
    ] {
        let value = worker.status();
        let timing = &value["stage_timings"][stage];
        assert!(
            timing["count"].as_u64().is_some_and(|count| count > 0),
            "{stage}"
        );
        assert!(timing["last_ms"].as_f64().unwrap() >= 0.0);
        assert!(timing["max_ms"].as_f64().unwrap() >= timing["last_ms"].as_f64().unwrap());
        assert!(timing["total_ms"].as_f64().unwrap() >= timing["max_ms"].as_f64().unwrap());
    }
    data.lock().unwrap().broken.insert("plants".into());
    worker.tick().await.unwrap();
    let status = worker.status();
    assert_eq!(status["stage_timings"]["plants"]["count"], 2);
    assert_eq!(status["domain_errors"]["plants"], "EcologyPlanningError");
    worker.record_stage("untrusted-player-id", Duration::from_secs(1));
    let status = worker.status();
    assert!(status["stage_timings"].as_object().unwrap().len() <= STAGE_KEYS.len());
    assert!(status["stage_timings"].get("untrusted-player-id").is_none());
    assert!(!status.to_string().contains("never-retain-player-payload"));
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn stage_measurement_does_not_hold_status_lock_while_awaiting_backend() {
    let (worker, _) = create(Fixture::new(&["mobs"]));
    let worker = Arc::new(worker);
    let entered = Arc::new(Notify::new());
    let release = Arc::new(Notify::new());
    let measured_worker = worker.clone();
    let started = entered.clone();
    let complete = release.clone();
    let measured = tokio::spawn(async move {
        measured_worker
            .time_stage("mobs", async move {
                started.notify_one();
                complete.notified().await;
                Err::<(), _>(anyhow!("Private backend details must not enter metrics"))
            })
            .await
    });
    entered.notified().await;
    let status_worker = worker.clone();
    let status = tokio::time::timeout(
        Duration::from_secs(1),
        tokio::task::spawn_blocking(move || status_worker.status()),
    )
    .await;
    // Release before checking the timeout so a regressed lock cannot strand a
    // blocking test thread during runtime shutdown.
    release.notify_one();
    assert!(measured.await.unwrap().is_err());
    assert!(status.unwrap().unwrap()["stage_timings"]
        .get("mobs")
        .is_none());
    let timing = &worker.status()["stage_timings"]["mobs"];
    assert_eq!(timing["count"], 1);
    assert!(timing["last_ms"].as_f64().unwrap() >= 0.0);
}
