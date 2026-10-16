FROM python:3.12-slim
ARG CATALOG_REVISION
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY wakfu_server ./wakfu_server
COPY protocol_codec.py ./protocol_codec.py
COPY objectives-service/service.py ./service.py
COPY objectives-service/static ./static
ENV PYTHONUNBUFFERED=1 WAKFU_CATALOG_REVISION=${CATALOG_REVISION}
EXPOSE 8094
CMD ["python", "service.py"]
