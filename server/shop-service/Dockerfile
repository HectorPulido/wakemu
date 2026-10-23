FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY shop-service/service.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "service.py"]
