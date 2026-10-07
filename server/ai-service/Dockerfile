ARG WORLD_IMAGE=wakfu-world-catalog-source:current
FROM ${WORLD_IMAGE} AS authoritative_world
FROM python:3.12-slim
WORKDIR /app
COPY --from=authoritative_world /app /native/server
COPY . /app
RUN mkdir -p /native/server/ai-service \
    && cp -a /app/. /native/server/ai-service/ \
    && python3 catalog_bootstrap.py --root /native/server --store /var/lib/wakfu-ai-context > /native/catalog-manifest.json
ENV PYTHONUNBUFFERED=1 WAKFU_AI_BIND=0.0.0.0 WAKFU_AI_PORT=8090 WAKFU_AI_CONTEXT_ROOT=/var/lib/wakfu-ai-context
EXPOSE 8090
CMD ["python3", "server.py"]
