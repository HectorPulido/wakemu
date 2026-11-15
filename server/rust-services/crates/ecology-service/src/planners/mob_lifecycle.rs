//! Durable active-zone clocks and seeded lifecycle decisions.
//! PostgreSQL owns cycle/incarnation identity; observations never charge offline time.
use crate::Context;
use anyhow::{anyhow, bail, ensure, Context as _, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use tokio_postgres::Transaction;

pub const BLOCK_SIZE: i64 = 32;
pub const MAX_FAILURES: i64 = 5;
pub const VERSION: i64 = 1;
const EXCLUSION: &str = "NOT EXISTS(SELECT 1 FROM environmental_owned_groups environmental_owned WHERE (environmental_owned.map_id,environmental_owned.world_instance_id,environmental_owned.group_id)=(g.map_id,g.instance_id,g.group_id))";
fn integer(v: &Value, key: &str) -> Result<i64> {
    v[key]
        .as_i64()
        .ok_or_else(|| anyhow!("Invalid lifecycle {key}"))
}
fn table(kind: &str) -> Result<&'static str> {
    match kind {
        "maturation" => Ok("monster_maturation_timers"),
        "reproduction" => Ok("monster_reproduction_timers"),
        _ => bail!("Invalid lifecycle kind"),
    }
}
fn challenge(instance: i64) -> bool {
    (576460752303423489..=648518346341351423).contains(&instance)
}
pub fn validate_policy(kind: &str, value: &Value) -> Result<()> {
    table(kind)?;
    let keys: &[&str] = if kind == "maturation" {
        &[
            "interval_ms",
            "base_probability",
            "stage_decay",
            "boss_probability",
        ]
    } else {
        &[
            "interval_ms",
            "birth_probability",
            "birth_stage_decay",
            "new_group_probability",
            "max_members",
            "max_zone_members",
            "max_zone_groups",
        ]
    };
    let o = value.as_object().context("Invalid lifecycle policy")?;
    ensure!(
        o.len() == keys.len() && keys.iter().all(|k| o.contains_key(*k)),
        "Invalid lifecycle policy fields"
    );
    ensure!(
        (1000..=86400000).contains(&integer(value, "interval_ms")?),
        "Invalid lifecycle interval"
    );
    let probabilities: &[&str] = if kind == "maturation" {
        &["base_probability", "stage_decay", "boss_probability"]
    } else {
        &[
            "birth_probability",
            "birth_stage_decay",
            "new_group_probability",
        ]
    };
    for k in probabilities {
        let n = value[*k]
            .as_f64()
            .context("Invalid lifecycle probability")?;
        ensure!(
            n.is_finite() && (0.0..=1.0).contains(&n),
            "Invalid lifecycle probability"
        );
    }
    if kind == "maturation" {
        ensure!(
            value["base_probability"].as_f64().unwrap()
                + value["boss_probability"].as_f64().unwrap()
                <= 1.0,
            "Maturation probabilities exceed one"
        );
    } else {
        ensure!(
            (1..=8).contains(&integer(value, "max_members")?),
            "Invalid reproduction roster limit"
        );
        for k in ["max_zone_members", "max_zone_groups"] {
            ensure!(
                (1..=100000).contains(&integer(value, k)?),
                "Invalid reproduction zone limit"
            );
        }
    }
    Ok(())
}
pub async fn policy(ctx: &Context, kind: &str) -> Result<Value> {
    table(kind)?;
    let db = ctx.db.get().await?;
    let key = format!("monster_{kind}");
    let row = db
        .query_opt("SELECT value FROM settings WHERE name=$1", &[&key])
        .await?
        .context("Missing lifecycle policy")?;
    let value: Value = row.get(0);
    validate_policy(kind, &value)?;
    Ok(value)
}
pub async fn dungeon_population(ctx: &Context, instance: i64) -> Result<bool> {
    if instance == 0 {
        return Ok(false);
    }
    if challenge(instance) {
        return Ok(true);
    }
    let db = ctx.db.get().await?;
    Ok(db
        .query_opt(
            "SELECT 1 FROM dungeon_instances WHERE instance_id=$1",
            &[&instance],
        )
        .await?
        .is_some())
}
fn hmac(key: &[u8], message: &[u8]) -> [u8; 32] {
    let mut block = [0u8; 64];
    if key.len() > 64 {
        block[..32].copy_from_slice(&Sha256::digest(key));
    } else {
        block[..key.len()].copy_from_slice(key);
    }
    let mut inner = [0x36u8; 64];
    let mut outer = [0x5cu8; 64];
    for i in 0..64 {
        inner[i] ^= block[i];
        outer[i] ^= block[i];
    }
    let mut hash = Sha256::new();
    hash.update(inner);
    hash.update(message);
    let digest = hash.finalize();
    let mut hash = Sha256::new();
    hash.update(outer);
    hash.update(digest);
    hash.finalize().into()
}
pub fn event(seed: &str, cycle: i64) -> Result<Value> {
    let key = hex::decode(seed).context("Invalid lifecycle seed")?;
    ensure!(key.len() == 32 && cycle >= 1, "Invalid lifecycle event");
    let digest = |label: &str| hmac(&key, format!("{VERSION}:{cycle}:{label}").as_bytes());
    let draw = |label: &str| {
        let d = digest(label);
        (u64::from_be_bytes(d[..8].try_into().unwrap()) >> 11) as f64 / (1u64 << 53) as f64
    };
    Ok(
        json!({"cycle":cycle,"draw":draw("draw"),"group_draw":draw("group"),"destination_draw":draw("destination"),"variant_seed":hex::encode(digest("variant")),"attempts":0}),
    )
}
fn py_list(cell: &[i64]) -> String {
    format!(
        "[{}]",
        cell.iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(", ")
    )
}
fn python_float(n: f64) -> String {
    // Python repr uses scientific form below 1e-4, including a signed two-digit exponent.
    let s = format!("{n:?}");
    if let Some((mantissa, exp)) = s.split_once('e') {
        let exponent: i32 = exp.parse().unwrap();
        return format!("{mantissa}e{exponent:+03}");
    }
    if n != 0.0 && n.abs() < 1e-4 {
        let digits = s.trim_start_matches("0.");
        let zeros = digits.bytes().take_while(|b| *b == b'0').count();
        let significant = &digits[zeros..];
        let mantissa = if significant.len() == 1 {
            significant.to_owned()
        } else {
            format!("{}.{}", &significant[..1], &significant[1..])
        };
        return format!("{mantissa}e-{:02}", zeros + 1);
    }
    s
}
pub fn choose(candidates: &[Value], decision: &Value) -> Result<Value> {
    let key = hex::decode(
        decision["variant_seed"]
            .as_str()
            .context("Missing lifecycle variant seed")?,
    )?;
    let mut ranked = Vec::new();
    for c in candidates {
        let identity = if c.is_object() {
            integer(c, "reference")?.to_string()
        } else {
            let a = c.as_array().context("Invalid lifecycle candidate")?;
            py_list(
                &a.iter()
                    .map(|v| v.as_i64().context("Invalid lifecycle candidate coordinate"))
                    .collect::<Result<Vec<_>>>()?,
            )
        };
        ranked.push((hmac(&key, identity.as_bytes()), c));
    }
    ranked
        .into_iter()
        .min_by_key(|p| p.0)
        .map(|p| p.1.clone())
        .context("Empty lifecycle candidate pool")
}
pub fn choose_destination(candidates: &[[i64; 3]], decision: &Value) -> Result<[i64; 3]> {
    let draw = decision["destination_draw"]
        .as_f64()
        .context("Missing destination draw")?;
    ensure!((0.0..1.0).contains(&draw), "Invalid destination draw");
    let key = python_float(draw);
    candidates
        .iter()
        .min_by_key(|cell| hmac(key.as_bytes(), py_list(&cell[..]).as_bytes()))
        .copied()
        .context("Empty lifecycle destination pool")
}
pub fn birth_probability(
    rank: i64,
    special: bool,
    configuration: &Value,
    size: usize,
) -> Result<f64> {
    validate_policy("reproduction", configuration)?;
    if special {
        return Ok(0.0);
    }
    ensure!(rank >= 0, "Invalid reproduction stage");
    let factor = if size < 4 {
        2.0
    } else if size == 4 {
        1.2
    } else {
        0.8
    };
    Ok((configuration["birth_probability"].as_f64().unwrap()
        * factor
        * configuration["birth_stage_decay"]
            .as_f64()
            .unwrap()
            .powf(rank as f64 / 2.0)
        / size.max(1) as f64)
        .min(1.0))
}
pub fn new_group_probability(size: usize, configuration: &Value) -> Result<f64> {
    validate_policy("reproduction", configuration)?;
    let b = configuration["new_group_probability"].as_f64().unwrap();
    if b == 0.0 || b == 1.0 {
        return Ok(b);
    }
    let odds = if size < 4 {
        0.08
    } else if size == 4 {
        0.55
    } else if size == 5 {
        0.90
    } else {
        0.98
    };
    Ok(odds * b / (odds * b + (1.0 - odds) * (1.0 - b)))
}
async fn load(
    db: &Transaction<'_>,
    map: i32,
    instance: i64,
    kind: &str,
    timers: &[Value],
    configuration: &Value,
) -> Result<()> {
    table(kind)?;
    let valid:HashSet<i64>=db.query("SELECT m.monster_id FROM combat_group_members m JOIN combat_groups g USING(map_id,instance_id,group_id) WHERE m.map_id=$1 AND m.instance_id=$2 AND g.status!='defeated' ORDER BY g.group_id,m.monster_id FOR SHARE OF g",&[&map,&instance]).await?.iter().map(|r|r.get(0)).collect();
    let ids: Vec<i64> = valid.iter().copied().collect();
    let rows=db.query("SELECT to_jsonb(p) FROM monster_life_plans p WHERE map_id=$1 AND instance_id=$2 AND kind=$3 AND monster_id=ANY($4) FOR UPDATE",&[&map,&instance,&kind,&ids]).await?;
    let rows: std::collections::HashMap<i64, Value> = rows
        .into_iter()
        .map(|r| {
            let v: Value = r.get(0);
            (v["monster_id"].as_i64().unwrap(), v)
        })
        .collect();
    let mut inserts = Vec::new();
    let mut updates = Vec::new();
    for timer in timers {
        let id = integer(timer, "monster_id")?;
        if !valid.contains(&id) {
            continue;
        }
        let cycle = integer(timer, "cycle")?.max(1);
        if let Some(row) = rows.get(&id) {
            if cycle >= integer(row, "block_start")? + BLOCK_SIZE {
                let seed = row["seed"].as_str().context("Invalid life plan seed")?;
                let events = (cycle..cycle + BLOCK_SIZE)
                    .map(|c| event(seed, c))
                    .collect::<Result<Vec<_>>>()?;
                updates.push(json!({"monster_id":id,"block_start":cycle,"events":events}));
            }
        } else {
            let seed = hex::encode(rand::random::<[u8; 32]>());
            let incarnation = hex::encode(rand::random::<[u8; 16]>());
            let events = (cycle..cycle + BLOCK_SIZE)
                .map(|c| event(&seed, c))
                .collect::<Result<Vec<_>>>()?;
            inserts.push(json!({"monster_id":id,"reference":integer(timer,"reference")?,"seed":seed,"incarnation":incarnation,"policy":configuration,"version":VERSION,"block_start":cycle,"events":events}));
        }
    }
    if !inserts.is_empty() {
        db.execute("INSERT INTO monster_life_plans(map_id,instance_id,kind,monster_id,reference,seed,incarnation,policy,version,block_start,events) SELECT $1,$2,$3,x.monster_id,x.reference,x.seed,x.incarnation,x.policy,x.version,x.block_start,x.events FROM jsonb_to_recordset($4) x(monster_id bigint,reference integer,seed text,incarnation text,policy jsonb,version integer,block_start bigint,events jsonb) ON CONFLICT DO NOTHING",&[&map,&instance,&kind,&json!(inserts)]).await?;
    }
    if !updates.is_empty() {
        db.execute("UPDATE monster_life_plans p SET block_start=x.block_start,events=x.events FROM jsonb_to_recordset($1) x(monster_id bigint,block_start bigint,events jsonb) WHERE p.map_id=$2 AND p.instance_id=$3 AND p.kind=$4 AND p.monster_id=x.monster_id",&[&json!(updates),&map,&instance,&kind]).await?;
    }
    Ok(())
}
pub async fn observe(
    ctx: &Context,
    map: i32,
    instance: i64,
    present: bool,
    generation: &str,
    now_ms: i64,
    excluded: &HashSet<i64>,
    kind: &str,
    eligible_refs: &HashSet<i32>,
    configuration: &Value,
) -> Result<Vec<Value>> {
    let table = table(kind)?;
    ensure!(
        now_ms >= 0 && !generation.is_empty(),
        "Invalid lifecycle observation"
    );
    if challenge(instance) || (kind == "reproduction" && dungeon_population(ctx, instance).await?) {
        return Ok(vec![]);
    }
    if present {
        validate_policy(kind, configuration)?;
    }
    let mut client = ctx.db.get().await?;
    let db = client.transaction().await?;
    if !present {
        db.execute(&format!("UPDATE {table} SET last_active_ms=NULL WHERE map_id=$1 AND instance_id=$2 AND last_active_ms IS NOT NULL"),&[&map,&instance]).await?;
        db.commit().await?;
        return Ok(vec![]);
    }
    db.execute(&format!("DELETE FROM {table} t USING environmental_owned_group_members m JOIN environmental_owned_groups o USING(instance_id,group_ordinal) WHERE o.map_id=$1 AND o.world_instance_id=$2 AND t.map_id=$1 AND t.instance_id=$2 AND t.monster_id=m.monster_id"),&[&map,&instance]).await?;
    let groups=db.query(&format!("SELECT to_jsonb(g) FROM combat_groups g WHERE map_id=$1 AND instance_id=$2 AND NOT EXISTS(SELECT 1 FROM objectives_public_hunts h WHERE h.map_id=g.map_id AND g.instance_id=0 AND h.group_id=g.group_id) AND {EXCLUSION} FOR UPDATE"),&[&map,&instance]).await?;
    let mut roster = Vec::new();
    let mut terminal = Vec::new();
    let mut initial = Vec::new();
    for row in groups {
        let group: Value = row.get(0);
        if group["status"] == "defeated" {
            continue;
        }
        for member in group["members"]
            .as_array()
            .context("Invalid lifecycle group roster")?
        {
            let id = integer(member, "id")?;
            let reference = i32::try_from(integer(member, "ref")?)?;
            if !eligible_refs.contains(&reference) {
                terminal.push(id);
            } else {
                initial.push(json!({"monster_id":id,"reference":reference}));
                roster.push((group.clone(), member.clone()));
            }
        }
    }
    if !terminal.is_empty() {
        db.execute(
            &format!(
                "DELETE FROM {table} WHERE map_id=$1 AND instance_id=$2 AND monster_id=ANY($3)"
            ),
            &[&map, &instance, &terminal],
        )
        .await?;
    }
    if initial.is_empty() {
        db.commit().await?;
        return Ok(vec![]);
    }
    let interval = integer(configuration, "interval_ms")?;
    db.execute(&format!("INSERT INTO {table}(map_id,instance_id,monster_id,reference,remaining_ms) SELECT $1,$2,x.monster_id,x.reference,$3 FROM jsonb_to_recordset($4) x(monster_id bigint,reference integer) ON CONFLICT DO NOTHING"),&[&map,&instance,&interval,&json!(initial)]).await?;
    let rows=db.query(&format!("SELECT to_jsonb(t) FROM {table} t WHERE map_id=$1 AND instance_id=$2 ORDER BY monster_id FOR UPDATE"),&[&map,&instance]).await?;
    let timers: std::collections::HashMap<i64, Value> = rows
        .into_iter()
        .map(|r| {
            let v: Value = r.get(0);
            (v["monster_id"].as_i64().unwrap(), v)
        })
        .collect();
    let mut updates = Vec::new();
    let mut due = Vec::new();
    for (group, member) in roster {
        let id = integer(&member, "id")?;
        let reference = integer(&member, "ref")?;
        let old = timers.get(&id).context("Lifecycle timer vanished")?;
        let mut update = old.clone();
        if integer(old, "reference")? != reference {
            update["reference"] = json!(reference);
            update["remaining_ms"] = json!(interval);
            update["last_active_ms"] = Value::Null;
            update["observer_generation"] = Value::Null;
            update["due"] = json!(false);
        } else if group["status"] != "available" || excluded.contains(&id) {
            update["last_active_ms"] = Value::Null;
        } else {
            let elapsed = if old["observer_generation"].as_str() == Some(generation) {
                old["last_active_ms"]
                    .as_i64()
                    .map_or(0, |last| now_ms.saturating_sub(last).max(0))
            } else {
                0
            };
            let remaining = integer(old, "remaining_ms")?.saturating_sub(elapsed).max(0);
            let newly_due =
                !old["due"].as_bool().context("Invalid timer due state")? && remaining == 0;
            let cycle = integer(old, "cycle")? + i64::from(newly_due);
            update["remaining_ms"] = json!(remaining);
            update["last_active_ms"] = json!(now_ms);
            update["observer_generation"] = json!(generation);
            update["due"] = json!(old["due"] == true || newly_due);
            update["cycle"] = json!(cycle);
            if newly_due {
                due.push(json!({"map_id":map,"instance_id":instance,"group_id":integer(&group,"group_id")?,"monster_id":id,"reference":reference,"cycle":cycle}));
            }
        }
        updates.push(update);
    }
    db.execute(&format!("UPDATE {table} t SET reference=x.reference,remaining_ms=x.remaining_ms,last_active_ms=x.last_active_ms,observer_generation=x.observer_generation,due=x.due,cycle=x.cycle FROM jsonb_to_recordset($1) x(monster_id bigint,reference integer,remaining_ms bigint,last_active_ms bigint,observer_generation text,due boolean,cycle bigint) WHERE t.map_id=$2 AND t.instance_id=$3 AND t.monster_id=x.monster_id"),&[&json!(updates),&map,&instance]).await?;
    load(&db, map, instance, kind, &updates, configuration).await?;
    db.commit().await?;
    Ok(due)
}
pub async fn pending(ctx: &Context, map: i32, instance: i64, kind: &str) -> Result<Vec<Value>> {
    let table = table(kind)?;
    if kind == "reproduction" && dungeon_population(ctx, instance).await? {
        return Ok(vec![]);
    }
    let db = ctx.db.get().await?;
    let extra = if kind == "reproduction" {
        format!(" AND {EXCLUSION}")
    } else {
        String::new()
    };
    let sql=format!("SELECT jsonb_build_object('map_id',t.map_id,'instance_id',t.instance_id,'monster_id',t.monster_id,'reference',t.reference,'cycle',t.cycle,'group_id',m.group_id) FROM {table} t JOIN combat_group_members m USING(map_id,instance_id,monster_id) JOIN combat_groups g USING(map_id,instance_id,group_id) WHERE t.map_id=$1 AND t.instance_id=$2 AND t.due AND g.status!='defeated'{extra} ORDER BY t.monster_id");
    Ok(db
        .query(&sql, &[&map, &instance])
        .await?
        .into_iter()
        .map(|r| r.get(0))
        .collect())
}
pub async fn attach(
    ctx: &Context,
    map: i32,
    instance: i64,
    kind: &str,
    tickets: &[Value],
    configuration: &Value,
) -> Result<Vec<Value>> {
    table(kind)?;
    if tickets.is_empty() {
        return Ok(vec![]);
    }
    let mut client = ctx.db.get().await?;
    let db = client.transaction().await?;
    load(&db, map, instance, kind, tickets, configuration).await?;
    let rows=db.query("SELECT p.monster_id,p.incarnation,p.policy,p.events->(x.cycle-p.block_start)::integer AS decision FROM monster_life_plans p JOIN jsonb_to_recordset($1) x(monster_id bigint,cycle bigint) USING(monster_id) WHERE p.map_id=$2 AND p.instance_id=$3 AND p.kind=$4 AND EXISTS(SELECT 1 FROM combat_group_members m JOIN combat_groups g USING(map_id,instance_id,group_id) WHERE m.map_id=p.map_id AND m.instance_id=p.instance_id AND m.monster_id=p.monster_id AND g.status!='defeated')",&[&json!(tickets),&map,&instance,&kind]).await?;
    let rows: std::collections::HashMap<i64, tokio_postgres::Row> =
        rows.into_iter().map(|row| (row.get(0), row)).collect();
    let mut result = Vec::new();
    for ticket in tickets {
        let id = integer(ticket, "monster_id")?;
        if let Some(row) = rows.get(&id) {
            let decision: Option<Value> = row.get(3);
            if let Some(decision) = decision {
                if integer(&decision, "attempts")? < MAX_FAILURES {
                    let mut value = ticket.clone();
                    value["plan_incarnation"] = json!(row.get::<_, String>(1));
                    value["plan_policy"] = row.get(2);
                    value["decision"] = decision;
                    result.push(value);
                }
            }
        }
    }
    db.commit().await?;
    Ok(result)
}
pub async fn unpublished(ctx: &Context, map: i32, instance: i64, kind: &str) -> Result<Vec<Value>> {
    table(kind)?;
    if kind == "reproduction" && dungeon_population(ctx, instance).await? {
        return Ok(vec![]);
    }
    let db = ctx.db.get().await?;
    Ok(db.query(&format!("SELECT to_jsonb(o)||jsonb_build_object('members',g.members,'status',g.status,'current_revision',g.revision) FROM monster_{kind}_outbox o JOIN combat_groups g USING(map_id,instance_id,group_id) WHERE o.map_id=$1 AND o.instance_id=$2 AND NOT o.published ORDER BY o.group_id,o.revision,o.monster_id,o.cycle"),&[&map,&instance]).await?.into_iter().map(|r|r.get(0)).collect())
}
pub async fn allocate_identity(ctx: &Context) -> Result<i64> {
    let mut client = ctx.db.get().await?;
    let db = client.transaction().await?;
    for _ in 0..1024 {
        let magnitude: i64 = db
            .query_one("SELECT nextval('lua_exact_npc_actor_ids')", &[])
            .await?
            .get(0);
        ensure!(
            ((1i64 << 50)..=((1i64 << 51) - 128)).contains(&magnitude),
            "Invalid Lua-exact NPC actor sequence"
        );
        if db
            .query_opt(
                "SELECT 1 FROM combat_group_members WHERE monster_id BETWEEN $1 AND $2 LIMIT 1",
                &[&(-(magnitude + 127)), &(-magnitude)],
            )
            .await?
            .is_none()
        {
            db.commit().await?;
            return Ok(-magnitude);
        }
    }
    bail!("Unable to reserve collision-free NPC actor block")
}
pub async fn resolve_noops(ctx: &Context, proposals: Vec<Value>) -> Result<Vec<Value>> {
    let mut remaining = Vec::new();
    let mut batches: [Vec<Value>; 2] = [vec![], vec![]];
    for mut p in proposals {
        let kind = p["kind"].as_str().unwrap_or("");
        let index = match kind {
            "maturation" => 0,
            "reproduction" => 1,
            _ => {
                remaining.push(p);
                continue;
            }
        };
        let noop = if index == 0 {
            p.get("grown").is_none_or(Value::is_null)
        } else {
            p.get("noop").and_then(Value::as_bool) == Some(true)
        };
        if !noop || p["ticket"].get("plan_incarnation").is_none() {
            if let Some(o) = p.as_object_mut() {
                o.remove("_noop_probability");
            }
            remaining.push(p);
            continue;
        }
        let mut row = p["ticket"].clone();
        row["members"] = p["expected_members"].clone();
        row["policy"] = p["configuration"].clone();
        row["draw"] = p["draw"].clone();
        row["interval_ms"] = p["configuration"]["interval_ms"].clone();
        row["probability"] = if index == 0 {
            json!(0.0)
        } else {
            let n = p["_noop_probability"]
                .as_f64()
                .context("Missing reproduction noop probability")?;
            ensure!(
                (0.0..=1.0).contains(&n) && p["draw"].as_f64().context("Invalid noop draw")? >= n,
                "Invalid reproduction noop probability"
            );
            json!(n)
        };
        batches[index].push(row);
    }
    for (index, rows) in batches.into_iter().enumerate() {
        if rows.is_empty() {
            continue;
        }
        let kind = if index == 0 {
            "maturation"
        } else {
            "reproduction"
        };
        let mut client = ctx.db.get().await?;
        let db = client.transaction().await?;
        let scopes: std::collections::BTreeSet<(i64, i64)> = rows
            .iter()
            .map(|r| Ok((integer(r, "map_id")?, integer(r, "instance_id")?)))
            .collect::<Result<_>>()?;
        for (map, instance) in scopes {
            let lock = format!("monster-population:{map}:{instance}");
            db.query_one(
                "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                &[&lock],
            )
            .await?;
        }
        let data = json!(rows);
        let definition="map_id integer,instance_id bigint,monster_id bigint,group_id bigint,reference integer,cycle bigint,plan_incarnation text,members jsonb,policy jsonb,draw double precision,probability double precision,interval_ms bigint";
        db.query(&format!("SELECT g.group_id FROM combat_groups g JOIN jsonb_to_recordset($1) x({definition}) USING(map_id,instance_id,group_id) ORDER BY g.map_id,g.instance_id,g.group_id FOR UPDATE OF g"),&[&data]).await?;
        let (columns, values) = if index == 0 {
            (
                "group_id,from_reference,to_reference,draw,policy",
                "x.group_id,x.reference,NULL,x.draw,x.policy || '{\"composition_model\":2}'::jsonb",
            )
        } else {
            ("parent_group_id,parent_reference,child_id,child_group_id,child,draw,probability,policy","x.group_id,x.reference,NULL,NULL,NULL,x.draw,x.probability,x.policy")
        };
        let sql=format!("WITH x AS (SELECT * FROM jsonb_to_recordset($1) x({definition})), inserted AS (INSERT INTO monster_{kind}_receipts(map_id,instance_id,monster_id,cycle,{columns}) SELECT x.map_id,x.instance_id,x.monster_id,x.cycle,{values} FROM x JOIN combat_groups g USING(map_id,instance_id,group_id) JOIN monster_life_plans p USING(map_id,instance_id,monster_id) JOIN monster_{kind}_timers t USING(map_id,instance_id,monster_id) WHERE g.status='available' AND g.members=x.members AND p.kind=$2 AND p.incarnation=x.plan_incarnation AND p.policy=x.policy AND (p.events->(x.cycle-p.block_start)::integer->>'draw')::double precision=x.draw AND t.due AND t.cycle=x.cycle AND t.reference=x.reference ON CONFLICT DO NOTHING RETURNING map_id,instance_id,monster_id,cycle) UPDATE monster_{kind}_timers t SET remaining_ms=x.interval_ms,last_active_ms=NULL,due=false FROM x JOIN inserted i USING(map_id,instance_id,monster_id,cycle) WHERE t.map_id=x.map_id AND t.instance_id=x.instance_id AND t.monster_id=x.monster_id");
        db.execute(&sql, &[&data, &kind]).await?;
        db.commit().await?;
    }
    Ok(remaining)
}
