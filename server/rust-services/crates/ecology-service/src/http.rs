//! Authenticated, bounded control surface compatible with the ecology worker.
use std::sync::Arc;
use std::time::Duration;

use axum::body::Bytes;
use axum::extract::{DefaultBodyLimit, Request, State};
use axum::http::{header, HeaderMap, Method, StatusCode, Uri};
use axum::middleware::{self, Next};
use axum::response::{IntoResponse, Response};
use axum::Router;
use serde_json::{json, Value};
use subtle::ConstantTimeEq;

use crate::protocol::{self, MAX_BODY_BYTES, MAX_RESPONSE_BYTES};
use crate::worker::{validate_query, Worker};

#[derive(Clone)]
struct HttpState {
    worker: Arc<Worker>,
}

#[derive(Clone)]
struct AuthState {
    expected: Arc<Vec<u8>>,
}

/// The control socket is private; every endpoint, including health, needs auth.
pub fn router(worker: Arc<Worker>, token: String) -> Router {
    let auth = AuthState {
        expected: Arc::new(format!("Bearer {token}").into_bytes()),
    };
    Router::new()
        .fallback(control)
        .with_state(HttpState { worker })
        .layer(DefaultBodyLimit::max(MAX_BODY_BYTES))
        .layer(middleware::from_fn_with_state(auth, authorize))
}

async fn authorize(State(auth): State<AuthState>, request: Request, next: Next) -> Response {
    let received = request
        .headers()
        .get(header::AUTHORIZATION)
        .map(|h| h.as_bytes())
        .unwrap_or_default();
    if !bool::from(received.ct_eq(auth.expected.as_slice())) {
        return reply(StatusCode::UNAUTHORIZED, json!({"error":"Unauthorized"}));
    }
    match tokio::time::timeout(Duration::from_secs(3), next.run(request)).await {
        Ok(response) => response,
        Err(_) => reply(
            StatusCode::SERVICE_UNAVAILABLE,
            json!({"error":"Ecology control unavailable"}),
        ),
    }
}

async fn control(
    State(state): State<HttpState>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Result<Bytes, axum::extract::rejection::BytesRejection>,
) -> Response {
    let body = match body {
        Ok(body) => body,
        Err(_) => return invalid_request(),
    };
    let path = uri
        .path_and_query()
        .map(|path| path.as_str())
        .unwrap_or("/");
    if method == Method::GET {
        return match path {
            "/health" | "/status" | "/metrics" => {
                let status = state.worker.status();
                let code = if path == "/health"
                    && status.get("healthy").and_then(Value::as_bool) != Some(true)
                {
                    StatusCode::SERVICE_UNAVAILABLE
                } else {
                    StatusCode::OK
                };
                reply(code, status)
            }
            "/query" => reply(StatusCode::OK, state.worker.diagnostic_snapshot()),
            _ => reply(StatusCode::NOT_FOUND, json!({"error":"Unknown endpoint"})),
        };
    }
    if method != Method::POST {
        return reply(StatusCode::NOT_FOUND, json!({"error":"Unknown endpoint"}));
    }
    let declared = match headers.get(header::CONTENT_LENGTH) {
        Some(value) => match value
            .to_str()
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
        {
            Some(length) if length <= MAX_BODY_BYTES => length,
            _ => return invalid_request(),
        },
        None if body.is_empty() => 0,
        None => return invalid_request(),
    };
    if declared != body.len() {
        return invalid_request();
    }
    let value: Value = match serde_json::from_slice(if body.is_empty() { b"{}" } else { &body }) {
        Ok(value) => value,
        Err(_) => return invalid_request(),
    };
    if path == "/query" {
        if validate_query(&value).is_err() {
            return invalid_request();
        }
        return match state.worker.query(value).await {
            Ok(value) => reply(StatusCode::OK, value),
            Err(_) => reply(
                StatusCode::SERVICE_UNAVAILABLE,
                json!({"error":"Ecology control unavailable"}),
            ),
        };
    }
    if value != json!({}) {
        return invalid_request();
    }
    if path != "/pause" && path != "/resume" {
        return reply(StatusCode::NOT_FOUND, json!({"error":"Unknown endpoint"}));
    }
    let enabled = path == "/resume";
    match state.worker.set_enabled(enabled).await {
        Ok(()) => reply(StatusCode::OK, json!({"enabled":enabled})),
        Err(_) => reply(
            StatusCode::SERVICE_UNAVAILABLE,
            json!({"error":"Ecology control unavailable"}),
        ),
    }
}

fn invalid_request() -> Response {
    reply(StatusCode::BAD_REQUEST, json!({"error":"Invalid request"}))
}

fn reply(status: StatusCode, value: Value) -> Response {
    let (status, body) = match protocol::json_bytes(&value, MAX_RESPONSE_BYTES) {
        Ok(body) => (status, body),
        Err(_) => (
            StatusCode::SERVICE_UNAVAILABLE,
            b"{\"error\":\"Ecology response unavailable\"}".to_vec(),
        ),
    };
    (
        status,
        [
            (header::CONTENT_TYPE, "application/json"),
            (header::CACHE_CONTROL, "no-store"),
        ],
        body,
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use http_body_util::BodyExt;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use tower::ServiceExt;

    #[tokio::test]
    async fn authentication_precedes_body_extraction_and_all_endpoint_work() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed = calls.clone();
        let app = Router::new()
            .fallback(move |body: Bytes| {
                let observed = observed.clone();
                async move {
                    observed.fetch_add(1, Ordering::SeqCst);
                    body
                }
            })
            .layer(DefaultBodyLimit::max(MAX_BODY_BYTES))
            .layer(middleware::from_fn_with_state(
                AuthState {
                    expected: Arc::new(b"Bearer test-secret".to_vec()),
                },
                authorize,
            ));
        for header in [
            None,
            Some("bearer test-secret"),
            Some("Bearer test-secret-extra"),
        ] {
            let mut request = axum::http::Request::builder().uri("/health");
            if let Some(header) = header {
                request = request.header(header::AUTHORIZATION, header);
            }
            let response = app
                .clone()
                .oneshot(
                    request
                        .body(Body::from(vec![0; MAX_BODY_BYTES + 1]))
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
            assert_eq!(response.headers()[header::CACHE_CONTROL], "no-store");
            assert_eq!(
                response.into_body().collect().await.unwrap().to_bytes(),
                "{\"error\":\"Unauthorized\"}"
            );
        }
        assert_eq!(calls.load(Ordering::SeqCst), 0);
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/health")
                    .header(header::AUTHORIZATION, "Bearer test-secret")
                    .body(Body::from("ok"))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn oversize_response_fails_bounded_without_returning_private_payload() {
        let response = reply(
            StatusCode::OK,
            json!({"private":"x".repeat(MAX_RESPONSE_BYTES)}),
        );
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(response.headers()[header::CACHE_CONTROL], "no-store");
    }
}
