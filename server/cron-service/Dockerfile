FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir redis==5.3.1
COPY wakfu_server /app/wakfu_server
COPY cron-service/service.py cron-service/config.json /app/
ENV PYTHONUNBUFFERED=1
CMD ["python","service.py"]
