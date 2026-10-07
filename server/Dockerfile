FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY local_game_server.py protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY protocol ./protocol
COPY migrations ./migrations
COPY tools/migrate_postgres.py tools/manage_permissions.py tools/plan_initial_monster_habitat.py tools/generate_initial_monster_population.py ./tools/
COPY docker-entrypoint.sh ./
ENV WAKFU_RUNTIME=/data \
    WAKFU_CAPTURE_PATH=/fixtures/frames.jsonl WAKFU_BIND_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 15556 15558 18081
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
