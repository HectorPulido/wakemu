FROM python:3.12-slim
WORKDIR /app
COPY server.py planner.py ./
ENV PYTHONUNBUFFERED=1 WAKFU_AI_BIND=0.0.0.0 WAKFU_AI_PORT=8090
EXPOSE 8090
CMD ["python3", "server.py"]
