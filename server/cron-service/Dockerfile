FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir redis==5.3.1 'psycopg[binary,pool]==3.2.10'
COPY wakfu_server /app/wakfu_server
COPY cron-service/service.py /app/
ENV PYTHONUNBUFFERED=1
CMD ["python","service.py"]
