//! Bounded authenticated requests to World; unknown outcomes remain retryable.
use crate::protocol::{self, MAX_BODY_BYTES, MAX_RESPONSE_BYTES, SCHEMA_VERSION};
use anyhow::{ensure, Context as _, Result};
use serde_json::{json, Value};
use std::time::Duration;

#[derive(Clone)]
pub struct WorldClient {
    client: reqwest::Client,
    base: reqwest::Url,
    token: String,
}
impl WorldClient {
    pub fn new(base: &str, token: String) -> Result<Self> {
        let base = reqwest::Url::parse(base).context("Invalid ecology World URL")?;
        ensure!(
            matches!(base.scheme(), "http" | "https")
                && base.host_str().is_some()
                && base.query().is_none()
                && base.fragment().is_none(),
            "Invalid ecology World URL"
        );
        ensure!(
            !token.trim().is_empty() && token.len() <= 4096,
            "Invalid ecology credential"
        );
        Ok(Self {
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(2))
                .connect_timeout(Duration::from_secs(1))
                .redirect(reqwest::redirect::Policy::none())
                .build()?,
            base,
            token,
        })
    }
    async fn request(&self, path: &str, payload: Option<&Value>) -> Result<Value> {
        let url = format!("{}{path}", self.base.as_str().trim_end_matches('/'));
        let mut request = if let Some(payload) = payload {
            self.client
                .post(url)
                .header("Content-Type", "application/json")
                .body(protocol::json_bytes(payload, MAX_BODY_BYTES)?)
        } else {
            self.client.get(url)
        };
        request = request.bearer_auth(&self.token);
        let mut response = request
            .send()
            .await
            .context("Ecology World request failed")?
            .error_for_status()
            .context("Ecology World request rejected")?;
        if let Some(length) = response.content_length() {
            ensure!(
                length <= MAX_RESPONSE_BYTES as u64,
                "Ecology JSON exceeds byte limit"
            );
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .context("Ecology World response failed")?
        {
            ensure!(
                bytes.len().saturating_add(chunk.len()) <= MAX_RESPONSE_BYTES,
                "Ecology JSON exceeds byte limit"
            );
            bytes.extend_from_slice(&chunk);
        }
        let value = protocol::bounded_json(&bytes, MAX_RESPONSE_BYTES)?;
        ensure!(value.is_object(), "Ecology response must be an object");
        Ok(value)
    }
    pub async fn snapshot(&self) -> Result<Value> {
        let value = self.request("/internal/ecology/snapshot", None).await?;
        protocol::validate_snapshot(&value)?;
        Ok(value)
    }
    pub async fn apply(&self, rows: &[Value]) -> Result<Vec<Value>> {
        ensure!(
            rows.len() <= protocol::MAX_PROPOSALS,
            "Invalid ecology proposal count"
        );
        let envelope = json!({"schema_version":SCHEMA_VERSION,"proposals":rows});
        protocol::validate_proposals(&envelope)?;
        let response = self
            .request("/internal/ecology/apply", Some(&envelope))
            .await?;
        protocol::validate_results(rows, &response)
    }
}
