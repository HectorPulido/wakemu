FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY migrations ./migrations
COPY tools/migrate_postgres.py ./tools/migrate_postgres.py
COPY admin-service/service.py ./service.py
COPY admin-service/static ./static
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
CMD ["python", "service.py"]
