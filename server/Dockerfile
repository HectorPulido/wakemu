FROM rust:1.100-slim-bookworm AS spatial-builder
WORKDIR /builder/server/rust-services
COPY rust-services/Cargo.toml rust-services/Cargo.lock ./
COPY rust-services/crates ./crates
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/builder/server/rust-services/target \
    cargo build --release --locked --package wakemu-world-spatial --lib \
    && install -D target/release/libwakemu_world_spatial.so /out/libwakemu_world_spatial.so

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG CATALOG_REVISION
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=spatial-builder /out/libwakemu_world_spatial.so /usr/local/lib/wakemu/libwakemu_world_spatial.so
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY local_game_server.py protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY migrations ./migrations
COPY --from=database seeds ./database/seeds
COPY --from=database protocol/npc-dialogues.json.gz protocol/npc-observed-dialogue-edges.json.gz ./database/protocol/
COPY --from=database protocol/npc-objective-definitions.json.gz protocol/native_intergame_descriptors.json ./database/protocol/
# Ship the maintained Python helper collection together, including imports
# between installation tools. The build context excludes private/generated
# data and offline Java sources; installation data is supplied separately.
COPY tools ./tools
COPY docker-entrypoint.sh ./
ENV WAKFU_RUNTIME=/data \
    WAKFU_CATALOG_REVISION=${CATALOG_REVISION} \
    WAKFU_BIND_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 15556 15558 16337 18081
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
