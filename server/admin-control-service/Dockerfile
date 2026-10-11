FROM docker:27-cli AS docker_cli
FROM python:3.12-slim
WORKDIR /app
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
RUN pip install --no-cache-dir 'psycopg[binary]==3.2.10'
COPY wakfu_server/admin_control.py ./wakfu_server/admin_control.py
COPY admin-control-service/service.py ./service.py
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["python", "service.py"]
