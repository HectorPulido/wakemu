FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG CATALOG_REVISION
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY local_game_server.py protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY migrations ./migrations
COPY seeds ./seeds
COPY protocol/npc-dialogues.json.gz protocol/npc-observed-dialogue-edges.json.gz ./protocol/
COPY protocol/npc-objective-definitions.json.gz protocol/native_intergame_descriptors.json ./protocol/
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
