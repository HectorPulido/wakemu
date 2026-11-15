FROM rust:1.100-slim-bookworm AS builder
WORKDIR /builder/server/rust-services

COPY rust-services/Cargo.toml rust-services/Cargo.lock ./
COPY rust-services/crates ./crates
# Preserve the source-relative paths used by include_bytes! for versioned assets.
COPY wakfu_server/items/native_ranch_building_footprints.json /builder/server/wakfu_server/items/
COPY wakfu_server/items/native_ranch_biome_topology.json /builder/server/wakfu_server/items/
COPY wakfu_server/items/native_ranch_building_definitions.json /builder/server/wakfu_server/items/
COPY wakfu_server/maps/interior-base-partition-geometry.json /builder/server/wakfu_server/maps/
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/builder/server/rust-services/target \
    cargo build --release --locked --package wakemu-ecology --bin wakemu-ecology \
    && install -D target/release/wakemu-ecology /out/wakemu-ecology

FROM debian:bookworm-slim AS runtime
ARG CATALOG_REVISION
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 wakemu \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin wakemu
COPY --from=builder /out/wakemu-ecology /usr/local/bin/wakemu-ecology
ENV WAKFU_CATALOG_REVISION=${CATALOG_REVISION}
USER 1000:1000
EXPOSE 8093
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=3 CMD ["/usr/local/bin/wakemu-ecology", "--health-check"]
CMD ["/usr/local/bin/wakemu-ecology"]
