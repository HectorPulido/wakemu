FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY protocol/monster-encyclopedia.json.gz ./protocol/
COPY protocol/aptitude-rules.json protocol/aptitude-effects.json ./protocol/
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY local_game_server.py protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY migrations ./migrations
COPY tools/migrate_postgres.py tools/manage_permissions.py ./tools/
COPY protocol/item-equipment-rules.json ./protocol/
COPY protocol/item-equipment-effects.json ./protocol/
COPY protocol/rii-test-arena.json ./protocol/
COPY protocol/combat-maps ./protocol/combat-maps
COPY protocol/forced-transitions ./protocol/forced-transitions
COPY protocol/combat-los ./protocol/combat-los
COPY protocol/seed-actions.json protocol/plant-resources.json protocol/ecology-regions.json ./protocol/
COPY protocol/planting-grounds.json protocol/profession-actions.json ./protocol/
COPY protocol/planting-maps ./protocol/planting-maps
COPY protocol/item-stack-rules.json ./protocol/
COPY protocol/native-generic-teleporters.json ./protocol/
COPY protocol/iop4785-combat.json protocol/iop4780-combat.json ./protocol/
COPY protocol/item-action-rules.json ./protocol/
COPY protocol/item-healing-rules.json ./protocol/
COPY protocol/inventory-bag-rules.json ./protocol/
COPY protocol/entity-layouts.json protocol/entity-defaults.json protocol/spells.json protocol/world-maps.json protocol/level-xp.json protocol/haven-bag-models.json protocol/haven-bag-furniture-templates.json protocol/base-health.json protocol/monsters.json protocol/spell-costs.json protocol/combat-spell-rules.json protocol/amakna-test-arena.json protocol/amakna-combat-los.json protocol/unarmed-combat.json protocol/xelor754-combat.json protocol/native-transports.json protocol/native-transport-objects.json protocol/native-map-objects.json protocol/interactive-actions.json protocol/content-manifest.json ./protocol/
COPY docker-entrypoint.sh ./
ENV WAKFU_RUNTIME=/data \
    WAKFU_CAPTURE_PATH=/fixtures/frames.jsonl WAKFU_BIND_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 15556 15558 18081
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
