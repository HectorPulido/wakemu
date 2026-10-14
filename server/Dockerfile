FROM python:3.12-slim
ARG CATALOG_REVISION
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY local_game_server.py protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY migrations ./migrations
COPY protocol/npc-dialogues.json.gz protocol/npc-observed-dialogue-edges.json.gz ./protocol/
COPY protocol/npc-objective-definitions.json.gz protocol/native_intergame_descriptors.json ./protocol/
COPY tools/migrate_postgres.py tools/import_native_catalogs.py tools/manage_permissions.py tools/plan_initial_monster_habitat.py tools/generate_initial_monster_population.py tools/equip_test_finisher.py tools/performance_report.py ./tools/
COPY tools/prepare_geometry_artifacts.py tools/prepare_los_artifacts.py ./tools/
COPY tools/retire_cron.py ./tools/
COPY docker-entrypoint.sh ./
ENV WAKFU_RUNTIME=/data \
    WAKFU_CATALOG_REVISION=${CATALOG_REVISION} \
    WAKFU_BIND_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 15556 15558 16337 18081
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
