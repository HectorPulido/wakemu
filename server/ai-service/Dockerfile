ARG WORLD_IMAGE=wakfu-world-catalog-source:current
FROM ${WORLD_IMAGE} AS authoritative_world
FROM python:3.12-slim
ARG CATALOG_REVISION
WORKDIR /app
RUN pip install --no-cache-dir 'psycopg[binary,pool]==3.2.10' 'redis==5.3.1'
COPY --from=authoritative_world /app /native/server
COPY . /app
RUN mkdir -p /native/server/ai-service /native/server/protocol \
    && cp -a /app/. /native/server/ai-service/ \
    && python3 -m wakfu_ai.context.catalog_bootstrap --source-only --root /native/server --store /var/lib/wakfu-ai-context > /native/catalog-manifest.json
ENV PYTHONUNBUFFERED=1 WAKFU_AI_BIND=0.0.0.0 WAKFU_AI_PORT=8090 WAKFU_AI_CONTEXT_ROOT=/var/lib/wakfu-ai-context WAKFU_CATALOG_REVISION=${CATALOG_REVISION}
EXPOSE 8090
CMD ["sh", "-c", "PYTHONPATH=/native/server:/app python3 -m wakfu_ai.context.catalog_bootstrap --root /native/server --store /var/lib/wakfu-ai-context > /native/catalog-manifest.json && exec python3 -m wakfu_ai"]
