FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY protocol_codec.py ./
COPY wakfu_server ./wakfu_server
COPY shop-service/service.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "service.py"]
