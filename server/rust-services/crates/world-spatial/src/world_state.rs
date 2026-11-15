//! Single authoritative live membership and compact spatial state.
use crate::engine::NativeError;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};
use std::thread::ThreadId;

type Result<T> = std::result::Result<T, NativeError>;
pub(crate) type Scope = (i32, i64);

#[derive(Clone, Debug, PartialEq, Eq)]
struct Position {
    map: i32,
    instance: i64,
    x: i32,
    y: i32,
    z: i16,
    direction: u8,
}

#[derive(Clone, Debug)]
struct Actor {
    id: i64,
    account: i64,
    generation: String,
    peer: u64,
    binding: u64,
    revision: u64,
    order: u64,
    active: bool,
    pending: bool,
    ready: bool,
    position: Position,
}

impl Actor {
    fn scope(&self) -> Scope {
        (self.position.map, self.position.instance)
    }
    fn value(&self) -> Value {
        json!({"character_id":self.id,"account_id":self.account,"generation":self.generation,
            "peer_id":self.peer,"binding_id":self.binding,"revision":self.revision,
            "map_id":self.position.map,"instance_id":self.position.instance,
            "x":self.position.x,"y":self.position.y,"z":self.position.z,
            "direction":self.position.direction,"ecology_active":self.active,"pending":self.pending})
    }
}

struct PendingJoin {
    actor: Actor,
}
struct Reservation {
    owner: ThreadId,
    token: u64,
    depth: u64,
}

pub struct WorldState {
    capacity: usize,
    actors: HashMap<i64, Actor>,
    bindings: HashMap<u64, i64>,
    order: BTreeMap<u64, i64>,
    scopes: HashMap<Scope, BTreeMap<u64, i64>>,
    pending: HashMap<u64, PendingJoin>,
    pending_actors: HashMap<i64, u64>,
    presence: HashMap<Scope, u64>,
    empty: BTreeMap<Scope, u64>,
    reservations: HashMap<Scope, Reservation>,
    reservation_scopes: HashMap<u64, Scope>,
    binding_sequence: u64,
    token_sequence: u64,
    order_sequence: u64,
    presence_sequence: u64,
    empty_sequence: u64,
    ranch_sequence: u64,
}

fn invalid(message: impl Into<String>) -> NativeError {
    NativeError::new("invalid", message)
}
fn integer(v: &Value, name: &str) -> Result<i64> {
    v.get(name)
        .and_then(Value::as_i64)
        .ok_or_else(|| invalid(format!("Missing exact spatial {name}")))
}
fn unsigned(v: &Value, name: &str) -> Result<u64> {
    v.get(name)
        .and_then(Value::as_u64)
        .ok_or_else(|| invalid(format!("Missing exact spatial {name}")))
}
fn identity(v: &Value) -> Result<i64> {
    let id = v
        .get("id")
        .or_else(|| v.get("character_id"))
        .and_then(Value::as_i64)
        .ok_or_else(|| invalid("Missing spatial character identity"))?;
    if id <= 0 {
        return Err(invalid("Invalid spatial character identity"));
    }
    Ok(id)
}
fn generation(v: &Value) -> Result<String> {
    let s = v
        .get("generation")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("Missing spatial session generation"))?;
    if s.is_empty() || s.chars().count() > 512 {
        return Err(invalid("Invalid spatial session generation"));
    }
    Ok(s.to_owned())
}
fn scope(v: &Value) -> Result<Scope> {
    let map = i32::try_from(integer(v, "map_id")?).map_err(|_| invalid("Invalid spatial map"))?;
    let instance = integer(v, "instance_id")?;
    if map <= 0 || instance < 0 {
        return Err(invalid("Invalid spatial scope"));
    }
    Ok((map, instance))
}
fn position(v: &Value) -> Result<Position> {
    let (map, instance) = scope(v)?;
    let direction =
        u8::try_from(integer(v, "direction")?).map_err(|_| invalid("Invalid spatial direction"))?;
    if direction > 7 {
        return Err(invalid("Invalid spatial direction"));
    }
    Ok(Position {
        map,
        instance,
        x: i32::try_from(integer(v, "x")?).map_err(|_| invalid("Invalid spatial x"))?,
        y: i32::try_from(integer(v, "y")?).map_err(|_| invalid("Invalid spatial y"))?,
        z: i16::try_from(integer(v, "z")?).map_err(|_| invalid("Invalid spatial z"))?,
        direction,
    })
}
fn next(counter: &mut u64, name: &str) -> Result<u64> {
    *counter = counter
        .checked_add(1)
        .ok_or_else(|| NativeError::new("capacity", format!("Spatial {name} exhausted")))?;
    Ok(*counter)
}

impl WorldState {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity,
            actors: HashMap::new(),
            bindings: HashMap::new(),
            order: BTreeMap::new(),
            scopes: HashMap::new(),
            pending: HashMap::new(),
            pending_actors: HashMap::new(),
            presence: HashMap::new(),
            empty: BTreeMap::new(),
            reservations: HashMap::new(),
            reservation_scopes: HashMap::new(),
            binding_sequence: 0,
            token_sequence: 0,
            order_sequence: 0,
            presence_sequence: 0,
            empty_sequence: 0,
            ranch_sequence: 0,
        }
    }

    fn rows(&self, location: Option<Scope>) -> Vec<&Actor> {
        let order = location
            .and_then(|s| self.scopes.get(&s))
            .unwrap_or(&self.order);
        if location.is_some_and(|s| !self.scopes.contains_key(&s)) {
            return Vec::new();
        }
        order
            .values()
            .filter_map(|id| self.actors.get(id))
            .collect()
    }

    fn audience_rows(&self, location: Scope) -> Vec<&Actor> {
        let mut rows = self.rows(Some(location));
        rows.extend(
            self.pending
                .values()
                .map(|p| &p.actor)
                .filter(|a| a.ready && a.scope() == location),
        );
        rows.sort_by_key(|a| a.order);
        rows
    }

    pub(crate) fn adopt_public_position(
        &mut self,
        account: i64,
        generation: &str,
        id: i64,
        value: &Value,
    ) {
        let Some(actor) = self.actors.get_mut(&id) else {
            return;
        };
        if actor.account != account || actor.generation != generation {
            return;
        }
        let Ok(p) = position(value) else { return };
        if actor.scope() != (p.map, p.instance) || (p.instance > 0 && matches!(p.map, 9 | 1440)) {
            return;
        }
        if actor.position != p {
            actor.position = p;
            actor.revision = actor.revision.saturating_add(1);
        }
    }

    fn matches_actor(&self, actor: &Actor, request: &Value) -> bool {
        for (name, actual) in [
            ("generation", json!(actor.generation)),
            ("peer_id", json!(actor.peer)),
            ("account_id", json!(actor.account)),
            ("binding_id", json!(actor.binding)),
            ("revision", json!(actor.revision)),
            ("ecology_active", json!(actor.active)),
        ] {
            if request
                .get(name)
                .is_some_and(|v| !v.is_null() && v != &actual)
            {
                return false;
            }
        }
        true
    }

    fn remove_actor(&mut self, id: i64) -> Result<Option<Actor>> {
        let Some(actor) = self.actors.get(&id).cloned() else {
            return Ok(None);
        };
        let location = actor.scope();
        let last = self.scopes.get(&location).is_some_and(|s| s.len() == 1);
        let empty_generation = if last && location.1 == 0 {
            Some(next(&mut self.empty_sequence, "empty episode")?)
        } else {
            None
        };
        self.actors.remove(&id);
        self.bindings.remove(&actor.binding);
        self.order.remove(&actor.order);
        if let Some(members) = self.scopes.get_mut(&location) {
            members.remove(&actor.order);
            if members.is_empty() {
                self.scopes.remove(&location);
            }
        }
        if !self.rows(Some(location)).iter().any(|a| a.active) {
            self.presence.remove(&location);
        }
        if let Some(generation) = empty_generation {
            self.empty.insert(location, generation);
        }
        Ok(Some(actor))
    }

    pub(crate) fn actor_scope(&self, id: i64) -> Option<Scope> {
        self.actors.get(&id).map(Actor::scope)
    }

    /// A reservation is logical transaction admission, never a held engine mutex.
    pub(crate) fn reserved_by_other(&self, location: Scope, owner: ThreadId) -> bool {
        self.reservations
            .get(&location)
            .is_some_and(|r| r.owner != owner)
    }

    pub(crate) fn requested_scopes(&self, op: &str, a: &Value) -> Vec<Scope> {
        match op {
            "world.scope_acquire" => scope(a).ok().into_iter().collect(),
            "world.join_prepare" => {
                let mut scopes = scope(&a["character"]).ok().into_iter().collect::<Vec<_>>();
                if let Ok(id) = identity(&a["character"]) {
                    if let Some(s) = self.actor_scope(id) {
                        scopes.push(s)
                    }
                }
                scopes
            }
            "world.join_commit" | "world.join_abort" | "world.join_ready" => a["token"]
                .as_u64()
                .and_then(|t| self.pending.get(&t))
                .map(|p| vec![p.actor.scope()])
                .unwrap_or_default(),
            "world.update" | "world.leave" | "world.deactivate_ecology" => {
                let id = identity(a).or_else(|_| identity(&a["character"])).ok();
                let mut scopes = id
                    .and_then(|id| self.actor_scope(id))
                    .into_iter()
                    .collect::<Vec<_>>();
                if op == "world.update" {
                    if let Ok(s) = scope(&a["character"]) {
                        scopes.push(s)
                    }
                }
                scopes
            }
            _ => Vec::new(),
        }
    }

    pub fn call(&mut self, op: &str, a: &Value, owner: ThreadId) -> Result<Value> {
        match op {
            "world.join_prepare"=>{
                let c=&a["character"];let id=identity(c)?;let account=integer(c,"account_id")?;
                if account<=0{return Err(invalid("Invalid spatial account identity"));}
                let generation=generation(a)?;let peer=unsigned(a,"peer_id")?;let p=position(c)?;
                if peer==0{return Err(invalid("Invalid spatial peer identity"));}
                if !self.actors.contains_key(&id) && !self.pending_actors.contains_key(&id)
                    && self.actors.len()+self.pending.len()>=self.capacity {return Err(NativeError::new("capacity","Spatial actor capacity reached"));}
                let token=next(&mut self.token_sequence,"join token")?;let binding=next(&mut self.binding_sequence,"binding")?;
                let order=next(&mut self.order_sequence,"registration order")?;
                let previous=self.remove_actor(id)?;
                let leave_recipients=previous.as_ref().map(|r|self.audience_rows(r.scope()).into_iter().map(Actor::value).collect::<Vec<_>>()).unwrap_or_default();
                if let Some(old)=self.pending_actors.remove(&id) {if let Some(p)=self.pending.remove(&old){self.bindings.remove(&p.actor.binding);}}
                let actor=Actor{id,account,generation,peer,binding,revision:1,order,active:true,pending:true,ready:false,position:p};
                let others:Vec<Value>=Vec::new();let row=actor.value();
                self.bindings.insert(actor.binding,id);self.pending.insert(token,PendingJoin{actor});self.pending_actors.insert(id,token);
                Ok(json!({"token":token,"row":row,"previous":previous.map(|p|p.value()),"leave_recipients":leave_recipients,"others":others}))
            },
            "world.join_ready"=>{
                let token=unsigned(a,"token")?;
                let pending=self.pending.get_mut(&token).ok_or_else(||NativeError::new("stale","Spatial join token is no longer current"))?;
                pending.actor.ready=true;
                let location=pending.actor.scope();let id=pending.actor.id;let row=pending.actor.value();
                let others=self.audience_rows(location).into_iter().filter(|r|r.id!=id).map(Actor::value).collect::<Vec<_>>();
                Ok(json!({"row":row,"others":others}))
            },
            "world.join_commit"=>{
                let token=unsigned(a,"token")?;
                let p=self.pending.get(&token).ok_or_else(||NativeError::new("stale","Spatial join token is no longer current"))?;
                if self.pending_actors.get(&p.actor.id)!=Some(&token) {return Err(NativeError::new("stale","Spatial join token was replaced"));}
                if !p.actor.ready{return Err(invalid("Spatial join binding is not ready"));}
                let location=p.actor.scope();
                let order=p.actor.order;
                let presence=if self.presence.contains_key(&location){None}else{Some(next(&mut self.presence_sequence,"presence episode")?)};
                let mut actor=self.pending.remove(&token).unwrap().actor;
                self.pending_actors.remove(&actor.id);actor.order=order;actor.pending=false;
                self.scopes.entry(location).or_default().insert(order,actor.id);self.order.insert(order,actor.id);
                self.empty.remove(&location);if let Some(generation)=presence{self.presence.insert(location,generation);}
                let value=actor.value();self.actors.insert(actor.id,actor);Ok(value)
            },
            "world.join_abort"=>{
                let token=unsigned(a,"token")?;
                let removed=self.pending.remove(&token);
                if let Some(p)=&removed {self.bindings.remove(&p.actor.binding);if self.pending_actors.get(&p.actor.id)==Some(&token){self.pending_actors.remove(&p.actor.id);}}
                let recipients=removed.as_ref().map(|p|self.audience_rows(p.actor.scope()).into_iter().map(Actor::value).collect::<Vec<_>>()).unwrap_or_default();
                Ok(json!({"removed":removed.map(|p|p.actor.value()),"recipients":recipients}))
            },
            "world.delivery_state"=>{
                let binding=unsigned(a,"binding_id")?;
                let row=self.bindings.get(&binding).and_then(|id| {
                    self.actors.get(id).filter(|r|r.binding==binding).or_else(||self.pending_actors.get(id).and_then(|token|self.pending.get(token)).map(|p|&p.actor).filter(|r|r.ready && r.binding==binding))
                }).map(Actor::value).unwrap_or(Value::Null);
                Ok(row)
            },
            "world.get"=>{
                let id=identity(a)?;
                Ok(self.actors.get(&id).filter(|r|self.matches_actor(r,a)).map(Actor::value).unwrap_or(Value::Null))
            },
            "world.list"|"world.snapshot"=>Ok(json!(self.rows(None).into_iter().map(Actor::value).collect::<Vec<_>>())),
            "world.matches"=>{
                let id=identity(a)?;
                let matches=self.actors.get(&id).is_some_and(|r|self.matches_actor(r,a) && {
                    let p=&a["position"];let row=r.value();
                    ["map_id","instance_id","x","y","z","direction"].iter().all(|key|p.get(*key).is_none_or(|v|v==&row[*key]))
                });Ok(json!(matches))
            },
            "world.leave"=>{
                let id=identity(a)?;let generation=generation(a)?;
                if !self.actors.get(&id).is_some_and(|r|r.generation==generation){return Ok(json!({"removed":null,"recipients":[]}));}
                let removed=self.remove_actor(id)?.unwrap();
                let recipients=self.audience_rows(removed.scope()).into_iter().map(Actor::value).collect::<Vec<_>>();
                Ok(json!({"removed":removed.value(),"recipients":recipients}))
            },
            "world.update"=>{
                let id=identity(a).or_else(|_|identity(&a["character"]))?;let generation=generation(a)?;
                let position=position(&a["character"])?;
                let existing=self.actors.get(&id).ok_or_else(||NativeError::new("stale","Character is no longer in this world session"))?;
                if existing.generation!=generation || !self.matches_actor(existing,a)
                    || a["character"].get("account_id").is_some_and(|v|v.as_i64()!=Some(existing.account)) {
                    return Err(NativeError::new("stale","Character is no longer in this world session"));
                }
                if existing.scope()!=(position.map,position.instance){return Err(invalid("Map transition requires leave/join"));}
                let existing=self.actors.get_mut(&id).unwrap();
                if existing.position!=position {existing.revision=existing.revision.checked_add(1).ok_or_else(||NativeError::new("capacity","Spatial actor revision exhausted"))?;existing.position=position;}
                Ok(existing.value())
            },
            "world.capture"=>{
                let location=scope(a)?;let excluded=a.get("exclude_sessions").and_then(Value::as_array);
                let rows=self.audience_rows(location).into_iter().filter(|r|{
                    !a.get("exclude_generation").is_some_and(|v|v==&json!(r.generation))
                    && !a.get("exclude_character_id").is_some_and(|v|v.as_i64()==Some(r.id))
                    && a.get("only_character_id").is_none_or(|v|v.is_null() || v.as_i64()==Some(r.id))
                    && !excluded.is_some_and(|xs|xs.iter().any(|s|s.as_array().is_some_and(|v|v.len()==2 && v[0].as_i64()==Some(r.id) && v[1]==r.generation)))
                }).map(Actor::value).collect::<Vec<_>>();Ok(json!(rows))
            },
            "world.deactivate_ecology"=>{
                let id=identity(a)?;let generation=generation(a)?;
                let Some(actor)=self.actors.get_mut(&id).filter(|r|r.generation==generation) else{return Ok(json!(false))};
                actor.active=false;let location=actor.scope();
                if !self.rows(Some(location)).iter().any(|r|r.active){self.presence.remove(&location);}
                Ok(json!(true))
            },
            "world.ecology_snapshot"|"world.registered_scope_snapshot"=>{
                let location=if a.get("map_id").is_some_and(|v| !v.is_null()){Some(scope(a)?)}else{None};
                let rows=self.rows(location).into_iter().filter(|r|op=="world.registered_scope_snapshot" || r.active).map(|r|json!({"id":r.id,"account_id":r.account,"generation":r.generation,
                    "map_id":r.position.map,"instance_id":r.position.instance,"x":r.position.x,"y":r.position.y,"z":r.position.z,
                    "direction":r.position.direction,"presence_generation":self.presence.get(&r.scope())})).collect::<Vec<_>>();Ok(json!(rows))
            },
            "world.scope_presence"=>Ok(self.presence.get(&scope(a)?).map(|v|json!(v)).unwrap_or(Value::Null)),
            "world.empty_scope_generation"=>Ok(self.empty.get(&scope(a)?).map(|v|json!(v)).unwrap_or(Value::Null)),
            "world.empty_scope_snapshot"=>Ok(json!(self.empty.iter().map(|((map,instance),generation)|json!({"map_id":map,"instance_id":instance,"empty_generation":generation})).collect::<Vec<_>>())),
            "world.try_scope_positions"|"world.try_positions"=>{
                let location=scope(a)?;
                let expected=a.get("presence_generation").or_else(||a.get("expected_presence")).and_then(Value::as_u64);
                if self.reserved_by_other(location,owner) || expected.is_none() || self.presence.get(&location).copied()!=expected {return Ok(Value::Null);}
                Ok(json!(self.rows(Some(location)).into_iter().map(|r|[i64::from(r.position.x),i64::from(r.position.y),i64::from(r.position.z)]).collect::<Vec<_>>()))
            },
            "world.ranch_refresh"=>{
                let location=scope(a)?;let ids=self.rows(Some(location)).into_iter().filter(|r|!a.get("exclude_generation").is_some_and(|v|v==&json!(r.generation))).map(|r|r.id).collect::<Vec<_>>();
                let mut result=Vec::with_capacity(ids.len());
                for id in ids {let nonce=next(&mut self.ranch_sequence,"Ranch scene refresh")?;result.push(json!({"row":self.actors[&id].value(),"nonce":nonce}));}Ok(json!(result))
            },
            "world.scope_acquire"=>{
                let location=scope(a)?;
                if let Some(r)=self.reservations.get_mut(&location){
                    if r.owner!=owner{return Err(NativeError::new("busy","Spatial scope has an active transaction"));}
                    r.depth=r.depth.checked_add(1).ok_or_else(||NativeError::new("capacity","Spatial scope reservation exhausted"))?;
                    return Ok(json!({"token":r.token}));
                }
                let token=next(&mut self.token_sequence,"scope token")?;
                self.reservations.insert(location,Reservation{owner,token,depth:1});self.reservation_scopes.insert(token,location);Ok(json!({"token":token}))
            },
            "world.scope_release"=>{
                let token=unsigned(a,"token")?;
                let Some(location)=self.reservation_scopes.get(&token).copied() else{return Ok(json!(false))};
                let r=self.reservations.get_mut(&location).unwrap();
                if r.owner!=owner{return Err(NativeError::new("stale","Spatial scope reservation belongs to another thread"));}
                r.depth-=1;if r.depth==0{self.reservations.remove(&location);self.reservation_scopes.remove(&token);}Ok(json!(true))
            },
            "world.stats"=>Ok(json!({"actors":self.actors.len(),"scopes":self.scopes.len(),"pending_joins":self.pending.len(),"scope_reservations":self.reservations.len(),"capacity":self.capacity})),
            _=>Err(invalid(format!("Unknown native world operation: {op}"))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn actor(id: i64, generation: &str, map: i32, instance: i64) -> Value {
        json!({"generation":generation,"peer_id":id+100,"character":{"id":id,"account_id":id,"map_id":map,"instance_id":instance,"x":0,"y":0,"z":0,"direction":0}})
    }
    fn call(s: &mut WorldState, op: &str, args: Value) -> Value {
        s.call(op, &args, std::thread::current().id()).unwrap()
    }
    fn join(s: &mut WorldState, id: i64, generation: &str, map: i32, instance: i64) -> Value {
        let p = call(
            s,
            "world.join_prepare",
            actor(id, generation, map, instance),
        );
        call(s, "world.join_ready", json!({"token":p["token"]}));
        call(s, "world.join_commit", json!({"token":p["token"]}))
    }
    #[test]
    fn presence_waits_for_registration_and_replacement_invalidates_old_lease() {
        let mut s = WorldState::new(10);
        let p = call(&mut s, "world.join_prepare", actor(7, "old", 527, 0));
        assert!(call(
            &mut s,
            "world.scope_presence",
            json!({"map_id":527,"instance_id":0})
        )
        .is_null());
        call(&mut s, "world.join_ready", json!({"token":p["token"]}));
        call(&mut s, "world.join_commit", json!({"token":p["token"]}));
        let old = call(
            &mut s,
            "world.scope_presence",
            json!({"map_id":527,"instance_id":0}),
        );
        join(&mut s, 7, "new", 527, 0);
        assert_ne!(
            old,
            call(
                &mut s,
                "world.scope_presence",
                json!({"map_id":527,"instance_id":0})
            )
        );
        assert!(
            call(&mut s, "world.leave", json!({"id":7,"generation":"old"}))["removed"].is_null()
        );
        assert_eq!(
            call(&mut s, "world.get", json!({"id":7}))["generation"],
            "new"
        );
    }
    #[test]
    fn capture_preserves_registration_order_scope_and_exact_exclusions() {
        let mut s = WorldState::new(10);
        join(&mut s, 9, "same", 527, 0);
        join(&mut s, 2, "same", 527, 0);
        join(&mut s, 5, "other", 527, 0);
        join(&mut s, 8, "private", 527, 1);
        let ids = |v: Value| {
            v.as_array()
                .unwrap()
                .iter()
                .map(|r| r["character_id"].as_i64().unwrap())
                .collect::<Vec<_>>()
        };
        assert_eq!(
            ids(call(
                &mut s,
                "world.capture",
                json!({"map_id":527,"instance_id":0})
            )),
            vec![9, 2, 5]
        );
        assert_eq!(
            ids(call(
                &mut s,
                "world.capture",
                json!({"map_id":527,"instance_id":0,"exclude_sessions":[[9,"same"]]})
            )),
            vec![2, 5]
        );
        assert_eq!(
            ids(call(
                &mut s,
                "world.capture",
                json!({"map_id":527,"instance_id":0,"exclude_generation":"same"})
            )),
            vec![5]
        );
    }
    #[test]
    fn deactivation_and_private_departure_never_create_empty_public_episode() {
        let mut s = WorldState::new(10);
        join(&mut s, 1, "one", 527, 0);
        join(&mut s, 2, "two", 527, 0);
        call(
            &mut s,
            "world.deactivate_ecology",
            json!({"id":1,"generation":"one"}),
        );
        call(
            &mut s,
            "world.deactivate_ecology",
            json!({"id":2,"generation":"two"}),
        );
        assert!(call(
            &mut s,
            "world.scope_presence",
            json!({"map_id":527,"instance_id":0})
        )
        .is_null());
        assert_eq!(
            call(&mut s, "world.empty_scope_snapshot", json!({})),
            json!([])
        );
        call(&mut s, "world.leave", json!({"id":1,"generation":"one"}));
        call(&mut s, "world.leave", json!({"id":2,"generation":"two"}));
        assert_eq!(
            call(&mut s, "world.empty_scope_snapshot", json!({}))
                .as_array()
                .unwrap()
                .len(),
            1
        );
        join(&mut s, 3, "private", 527, 99);
        call(
            &mut s,
            "world.leave",
            json!({"id":3,"generation":"private"}),
        );
        assert_eq!(
            call(&mut s, "world.empty_scope_snapshot", json!({}))
                .as_array()
                .unwrap()
                .len(),
            1
        );
    }
    #[test]
    fn move_requires_current_lease_and_scope_and_keeps_metadata_handle() {
        let mut s = WorldState::new(10);
        let initial = join(&mut s, 1, "one", 527, 0);
        let mut request = actor(1, "one", 527, 0);
        request["id"] = json!(1);
        request["character"]["x"] = json!(7);
        let moved = call(&mut s, "world.update", request.clone());
        assert_eq!(moved["binding_id"], initial["binding_id"]);
        assert_eq!(moved["x"], 7);
        request["character"]["map_id"] = json!(9);
        assert!(s
            .call("world.update", &request, std::thread::current().id())
            .is_err());
        request["character"]["map_id"] = json!(527);
        request["generation"] = json!("old");
        assert!(s
            .call("world.update", &request, std::thread::current().id())
            .is_err());
    }
    #[test]
    fn overlapping_joins_observe_pending_peers_without_publishing_presence() {
        let mut s = WorldState::new(10);
        let a = call(&mut s, "world.join_prepare", actor(9, "a", 527, 0));
        let b = call(&mut s, "world.join_prepare", actor(2, "b", 527, 0));
        assert_eq!(b["others"], json!([]));
        assert!(call(
            &mut s,
            "world.delivery_state",
            json!({"binding_id":a["row"]["binding_id"]})
        )
        .is_null());
        assert_eq!(
            call(
                &mut s,
                "world.capture",
                json!({"map_id":527,"instance_id":0})
            ),
            json!([])
        );
        assert!(s
            .call(
                "world.join_commit",
                &json!({"token":a["token"]}),
                std::thread::current().id()
            )
            .is_err());
        call(&mut s, "world.join_ready", json!({"token":a["token"]}));
        let ready = call(&mut s, "world.join_ready", json!({"token":b["token"]}));
        assert_eq!(
            call(
                &mut s,
                "world.delivery_state",
                json!({"binding_id":a["row"]["binding_id"]})
            )["pending"],
            true
        );
        assert_eq!(ready["others"][0]["character_id"], 9);
        assert_eq!(call(&mut s, "world.list", json!({})), json!([]));
        assert!(call(
            &mut s,
            "world.scope_presence",
            json!({"map_id":527,"instance_id":0})
        )
        .is_null());
        call(&mut s, "world.join_commit", json!({"token":b["token"]}));
        call(&mut s, "world.join_commit", json!({"token":a["token"]}));
        assert_eq!(
            call(
                &mut s,
                "world.delivery_state",
                json!({"binding_id":a["row"]["binding_id"]})
            )["pending"],
            false
        );
        let rows = call(&mut s, "world.list", json!({}));
        assert_eq!(rows[0]["character_id"], 9);
        assert_eq!(rows[1]["character_id"], 2);
    }
    #[test]
    fn inactive_registered_actor_still_blocks_ecological_placement() {
        let mut s = WorldState::new(10);
        join(&mut s, 1, "a", 527, 0);
        join(&mut s, 2, "b", 527, 0);
        call(
            &mut s,
            "world.deactivate_ecology",
            json!({"id":1,"generation":"a"}),
        );
        let episode = call(
            &mut s,
            "world.scope_presence",
            json!({"map_id":527,"instance_id":0}),
        );
        let cells = call(
            &mut s,
            "world.try_scope_positions",
            json!({"map_id":527,"instance_id":0,"presence_generation":episode}),
        );
        assert_eq!(cells.as_array().unwrap().len(), 2);
        assert!(call(&mut s, "world.get", json!({"id":1,"ecology_active":true})).is_null());
        assert_eq!(
            call(
                &mut s,
                "world.registered_scope_snapshot",
                json!({"map_id":527,"instance_id":0})
            )
            .as_array()
            .unwrap()
            .len(),
            2
        );
    }
    #[test]
    fn scope_reservations_reenter_and_leave_unrelated_scopes_available() {
        let mut s = WorldState::new(10);
        let a = call(
            &mut s,
            "world.scope_acquire",
            json!({"map_id":527,"instance_id":0}),
        );
        let b = call(
            &mut s,
            "world.scope_acquire",
            json!({"map_id":527,"instance_id":0}),
        );
        assert_eq!(a, b);
        let other = std::thread::spawn(|| std::thread::current().id())
            .join()
            .unwrap();
        assert!(s.reserved_by_other((527, 0), other));
        assert!(!s.reserved_by_other((527, 1), other));
        call(&mut s, "world.scope_release", json!({"token":a["token"]}));
        assert!(s.reserved_by_other((527, 0), other));
        call(&mut s, "world.scope_release", json!({"token":a["token"]}));
        assert!(!s.reserved_by_other((527, 0), other));
    }
}
