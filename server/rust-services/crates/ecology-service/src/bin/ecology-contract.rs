//! Offline compatibility harness: no connections, clocks, or game mutations.
use std::io::{self, BufRead};
use anyhow::{bail, Result};
use serde_json::{json, Value};
use wakemu_ecology::{identity, protocol};

fn evaluate(request:&Value)->Result<Value> {
    let value=&request["value"];
    Ok(match request["operation"].as_str().unwrap_or("") {
        "canonical"=>json!(String::from_utf8(identity::canonical_bytes(value)?)?),
        "proposal"=>protocol::proposal(request["domain"].as_str().unwrap_or(""),request["payload"].clone(),request["epoch"].as_str().unwrap_or(""))?,
        "identity"=>json!(identity::proposal_identity(value)?),
        "split_bulk"=>json!(identity::split_bulk_proposals(value.as_array().ok_or_else(||anyhow::anyhow!("Expected rows"))?)?),
        "filter_failed"=>identity::filter_failed_bulk(value,&request["exhausted"].as_array().ok_or_else(||anyhow::anyhow!("Expected exhausted IDs"))?.iter().map(|v|v.as_str().unwrap_or("").to_owned()).collect())?.unwrap_or(Value::Null),
        "merge_bulk"=>identity::merge_bulk_payload(&request["original"],&request["fresh"] )?,
        "refresh_stale"=>identity::refresh_stale_decision(&request["original"],&request["fresh"] )?,
        "validate_query"=>{protocol::validate_query(value)?;json!(true)},
        _=>bail!("Unknown offline ecology operation"),
    })
}
fn main(){for line in io::stdin().lock().lines(){match line {Ok(line)=>{let result=serde_json::from_str(&line).map_err(anyhow::Error::from).and_then(|request|evaluate(&request));let response=match result {Ok(value)=>json!({"result":value}),Err(error)=>json!({"error":error.to_string()})};println!("{}",response);},Err(_)=>break}}}
